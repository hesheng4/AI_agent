"""Coordinator API — 能力地图 · 工作流模板 · 意图路由 · 多 Agent 编排 · 运行记录恢复"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.agents.coordinator import get_coordinator_agent
from app.agents.coordinator.planner import WORKFLOW_TEMPLATES
from app.api.deps import get_current_user
from app.config import get_settings
from app.core.events import event_bus
from app.core.runs import (
    RUN_FAILED,
    RUN_RUNNING,
    RunRecorder,
    claim_run_for_resume,
    compute_resume_sets,
    finalize_run,
    get_run,
    list_run_summaries,
    plan_signature,
    record_is_stale,
)
from app.core.workflows import get_workflow, workflow_to_execution_plan
from app.models.user import User

router = APIRouter(tags=["coordinator"])
_agent = get_coordinator_agent()


class RouteRequest(BaseModel):
    task: str = Field(default="", description="自然语言意图，用于识别目标 agent")
    content: str = Field(default="")


class OrchestrateRequest(RouteRequest):
    task_id: str | None = Field(
        default=None,
        description="任务 ID。传入则事件发布到该 id（供前端先建 WS 连接再发起编排）；"
        "缺省由协调器生成并在响应 task_id 中返回",
    )
    workflow_template: str | None = Field(
        default=None,
        description="工作流模板 id（如 write_from_scratch / revise）。"
        "提供时按模板步骤逐步编排，缺省走意图路由",
    )
    save_artifact: bool = Field(
        default=False,
        description="编排完成后把最终结果保存为产出物（结果持久化，可随时重新导出）",
    )

    @field_validator("workflow_template")
    @classmethod
    def _validate_workflow_template(cls, v: str | None) -> str | None:
        if v is not None and v not in WORKFLOW_TEMPLATES:
            raise ValueError(
                f"未知工作流模板: {v!r}，可用: {sorted(WORKFLOW_TEMPLATES)}"
            )
        return v


class OrchestrateResponse(BaseModel):
    task_id: str
    trace_id: str
    result: dict[str, Any]


class RouteResponse(BaseModel):
    result: dict[str, Any]


@router.get("/capability-map", response_model=RouteResponse)
async def capability_map(user: User = Depends(get_current_user)) -> RouteResponse:
    """返回 16 skill 能力地图"""
    return RouteResponse(result=_agent.capability_map())


@router.get("/workflow-templates", response_model=RouteResponse)
async def workflow_templates(user: User = Depends(get_current_user)) -> RouteResponse:
    """返回 4 条工作流模板"""
    return RouteResponse(result=_agent.workflow_templates())


@router.post("/route", response_model=RouteResponse)
async def route_request(
    req: RouteRequest, user: User = Depends(get_current_user)
) -> RouteResponse:
    """意图识别 → 单 agent 路由"""
    result = await _agent.process_simple(
        {
            **req.model_dump(),
            "_user_api_key": user.api_key,
            "_user_api_base_url": user.api_base_url,
            "_user_api_model": user.api_model,
        }
    )
    return RouteResponse(result=result)


@router.post("/orchestrate", response_model=OrchestrateResponse)
async def orchestrate_request(
    req: OrchestrateRequest, user: User = Depends(get_current_user)
) -> OrchestrateResponse:
    """多 Agent 编排 — 完整 process()：关键词规划 + 上游补全 + 拓扑分层并行

    与 /route（单 Agent）互补。执行期间事件发布到 task_id 对应的
    event_bus 队列，前端可先连 /ws/tasks/{task_id} 观察实时进度；
    响应同时携带最终结果（双通道）。
    """
    final = await _agent.process(
        {
            **req.model_dump(exclude={"task_id"}),
            "_task_id": req.task_id,
            "_user_id": user.id,
            "_user_api_key": user.api_key,
            "_user_api_base_url": user.api_base_url,
            "_user_api_model": user.api_model,
        }
    )
    return OrchestrateResponse(
        task_id=final["task_id"], trace_id=final["trace_id"], result=final
    )


# ---------------------------------------------------------------------------
# E6: 运行记录（checkpoint）与恢复
# ---------------------------------------------------------------------------


class ResumeResponse(BaseModel):
    task_id: str
    run_id: str
    result: dict[str, Any]


@router.get("/runs")
async def list_runs(user: User = Depends(get_current_user)) -> dict[str, Any]:
    """列出当前用户的 run 记录摘要（新→旧，不含结果载荷）"""
    return {"runs": list_run_summaries(str(user.id))}


@router.get("/runs/{run_id}")
async def get_run_detail(
    run_id: str, user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """查看 run 记录全量（含每步状态/结果载荷/错误证据）"""
    record = get_run(str(user.id), run_id)
    if not record:
        raise HTTPException(404, "run 记录不存在")
    return record


@router.post("/runs/{run_id}/resume", response_model=ResumeResponse)
async def resume_run(
    run_id: str, user: User = Depends(get_current_user)
) -> ResumeResponse:
    """从失败步恢复 run：重执行 failed/pending 及其传递下游，跳过已完成步

    守卫链：ownership（get_run 按 user 定位）→ 仅 failed 可恢复 →
    计划签名比对（漂移 409）→ failed→running 原子接管（并发 409）。
    凭据不落盘：每次 resume 注入当前用户最新 API 配置。
    """
    user_id = str(user.id)
    record = get_run(user_id, run_id)
    if not record:
        raise HTTPException(404, "run 记录不存在")

    # 状态守卫：failed 可恢复；running 仅在超期无活动（疑似进程中断）时
    # 可接管（E6 v2）；其余状态拒绝
    stale_after = float(get_settings().RUN_STALE_AFTER)
    allow_stale_running = False
    status = record.get("status")
    if status == RUN_RUNNING:
        if not record_is_stale(record, stale_after):
            raise HTTPException(409, "run 仍在进行中（近期有步进），请稍后重试")
        allow_stale_running = True
    elif status != RUN_FAILED:
        raise HTTPException(409, f"run 状态为 {status!r}，仅 failed 状态可恢复")

    source = record.get("source") or {}
    kind = source.get("kind")
    if kind == "template":
        template_id = source.get("template_id")
        if template_id not in WORKFLOW_TEMPLATES:
            raise HTTPException(409, f"模板 {template_id!r} 已不存在，无法恢复")
        frozen = dict(record.get("request") or {})
        frozen["workflow_template"] = template_id
        plan = _agent.planner.decompose_task(frozen, [])
        fail_fast = True
    elif kind == "workflow":
        wf = get_workflow(user_id, source.get("workflow_id", ""))
        if not wf:
            raise HTTPException(409, "源工作流已删除，无法恢复；请发起新 run")
        try:
            plan = workflow_to_execution_plan(wf)
        except ValueError as e:
            raise HTTPException(409, f"源工作流 DAG 已变更且非法: {e}")
        fail_fast = False
    else:
        raise HTTPException(409, f"未知 run 来源: {kind!r}")

    if plan_signature(plan) != record.get("plan_signature"):
        raise HTTPException(409, "工作流/模板计划已变更，无法恢复；请发起新 run")

    task_id = event_bus.new_task_id()
    for t in plan:
        t["request"].update(
            {
                "_user_api_key": user.api_key,
                "_user_api_base_url": user.api_base_url,
                "_user_api_model": user.api_model,
            }
        )
        t["_task_id"] = task_id
        t["_trace_id"] = task_id

    rerun_agents, completed_entries = compute_resume_sets(record)
    if not claim_run_for_resume(
        user_id,
        run_id,
        task_id,
        allow_stale_running=allow_stale_running,
        stale_after=stale_after,
    ):
        raise HTTPException(409, "run 正在被其他恢复流程接管，请稍后重试")

    try:
        results = await _agent._execute_plan_parallel(
            plan,
            task_id,
            fail_fast=fail_fast,
            run_recorder=RunRecorder(user_id, run_id),
            completed_results=completed_entries,
        )
        final = _agent._integrate_results(results, fail_fast=fail_fast)
        run_status = "failed" if final.get("failed_agents") else "succeeded"
        finalize_run(user_id, run_id, status=run_status, error=final.get("error", ""))
    except Exception:
        finalize_run(user_id, run_id, status=RUN_FAILED, error="恢复执行异常中止")
        raise

    return ResumeResponse(task_id=task_id, run_id=run_id, result=final)

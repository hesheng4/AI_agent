"""Coordinator API endpoints — 能力地图 + 工作流模板 + 意图路由 + 多 Agent 编排"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from app.agents.coordinator import get_coordinator_agent
from app.agents.coordinator.planner import WORKFLOW_TEMPLATES
from app.api.deps import get_current_user
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
async def capability_map(user: User = Depends(get_current_user)):
    """返回 16 skill 能力地图"""
    return RouteResponse(result=_agent.capability_map())


@router.get("/workflow-templates", response_model=RouteResponse)
async def workflow_templates(user: User = Depends(get_current_user)):
    """返回 4 条工作流模板"""
    return RouteResponse(result=_agent.workflow_templates())


@router.post("/route", response_model=RouteResponse)
async def route_request(req: RouteRequest, user: User = Depends(get_current_user)):
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
):
    """多 Agent 编排 — 完整 process()：关键词规划 + 上游补全 + 拓扑分层并行

    与 /route（单 Agent）互补。执行期间事件发布到 task_id 对应的
    event_bus 队列，前端可先连 /ws/tasks/{task_id} 观察实时进度；
    响应同时携带最终结果（双通道）。
    """
    final = await _agent.process(
        {
            **req.model_dump(exclude={"task_id"}),
            "_task_id": req.task_id,
            "_user_api_key": user.api_key,
            "_user_api_base_url": user.api_base_url,
            "_user_api_model": user.api_model,
        }
    )
    return OrchestrateResponse(
        task_id=final["task_id"], trace_id=final["trace_id"], result=final
    )

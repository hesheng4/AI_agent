"""E5: 工作流 API — CRUD + 执行自定义 DAG"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.agents.coordinator import get_coordinator_agent
from app.api.deps import get_current_user
from app.core.runs import create_run, finalize_run
from app.core.workflows import (
    create_workflow,
    delete_workflow,
    get_workflow,
    list_workflows,
    update_workflow,
    workflow_to_execution_plan,
)
from app.models.user import User

router = APIRouter(tags=["workflows"])
_coordinator = get_coordinator_agent()


class WorkflowNode(BaseModel):
    id: str
    agent: str
    task: str = ""
    label: str = ""


class WorkflowEdge(BaseModel):
    source: str
    target: str


class CreateWorkflowRequest(BaseModel):
    name: str = Field(default="Untitled Workflow", max_length=100)
    description: str = Field(default="", max_length=500)
    nodes: list[WorkflowNode] = Field(default_factory=list)
    edges: list[WorkflowEdge] = Field(default_factory=list)


class UpdateWorkflowRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    nodes: list[WorkflowNode] | None = None
    edges: list[WorkflowEdge] | None = None


class RunWorkflowRequest(BaseModel):
    workflow_id: str
    input_data: dict[str, Any] = Field(default_factory=dict)


@router.get("/")
async def list_all(user: User = Depends(get_current_user)):
    return {"workflows": list_workflows(user.id)}


@router.get("/{workflow_id}")
async def get_one(workflow_id: str, user: User = Depends(get_current_user)):
    wf = get_workflow(user.id, workflow_id)
    if not wf or wf.get("created_by") != user.id:
        raise HTTPException(404, "工作流不存在")
    return wf


@router.post("/")
async def create(req: CreateWorkflowRequest, user: User = Depends(get_current_user)):
    # req.model_dump() 已将 nodes/edges 序列化为 dict 列表，无需二次转换 (T1)
    return create_workflow(user.id, req.model_dump())


@router.put("/{workflow_id}")
async def update(
    workflow_id: str, req: UpdateWorkflowRequest, user: User = Depends(get_current_user)
):
    # 仅保留非 None 字段；model_dump() 已序列化 nodes/edges (T2)
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    result = update_workflow(user.id, workflow_id, data)
    if not result:
        raise HTTPException(404, "工作流不存在")
    return result


@router.delete("/{workflow_id}")
async def delete(workflow_id: str, user: User = Depends(get_current_user)):
    if not delete_workflow(user.id, workflow_id):
        raise HTTPException(404, "工作流不存在")
    return {"status": "deleted"}


@router.post("/{workflow_id}/run")
async def run(workflow_id: str, user: User = Depends(get_current_user)):
    """执行自定义工作流 DAG"""
    wf = get_workflow(user.id, workflow_id)
    if not wf or wf.get("created_by") != user.id:
        raise HTTPException(404, "工作流不存在")

    # W4: workflow_to_execution_plan 会抛 ValueError (自环/循环依赖/R2 重复 agent)
    try:
        execution_plan = workflow_to_execution_plan(wf)
    except ValueError as e:
        raise HTTPException(400, f"工作流 DAG 非法: {e}")
    if not execution_plan:
        raise HTTPException(400, "工作流为空，无节点可执行")
    # 注入用户 API 配置
    for task in execution_plan:
        task["request"]["_user_api_key"] = user.api_key
        task["request"]["_user_api_base_url"] = user.api_base_url
        task["request"]["_user_api_model"] = user.api_model

    # 复用 coordinator 的 DAG 调度引擎
    # E6: 创建 run 记录（checkpoint），失败后可经 /coordinator/runs/{id}/resume 恢复
    user_id = str(user.id)
    recorder = create_run(
        user_id=user_id,
        source={
            "kind": "workflow",
            "workflow_id": workflow_id,
            "name": wf.get("name", ""),
        },
        request={},
        execution_plan=execution_plan,
    )
    results = await _coordinator._execute_plan_parallel(
        execution_plan, run_recorder=recorder
    )
    final = _coordinator._integrate_results(results)
    run_status = "failed" if final.get("failed_agents") else "succeeded"
    finalize_run(
        user_id, recorder.run_id, status=run_status, error=final.get("error", "")
    )
    return {
        "status": final.get("status", "done"),
        "run_id": recorder.run_id,
        "results": final,
    }

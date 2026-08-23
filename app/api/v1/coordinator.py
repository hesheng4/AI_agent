"""Coordinator API endpoints — 能力地图 + 工作流模板 + 意图路由"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agents.coordinator import get_coordinator_agent
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(tags=["coordinator"])
_agent = get_coordinator_agent()


class RouteRequest(BaseModel):
    task: str = Field(default="", description="自然语言意图，用于识别目标 agent")
    content: str = Field(default="")


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

"""E10: Agent 生成 API — 自然语言描述 → 代码骨架生成 + 确认写入"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import enforce_api_rate_limit, get_current_user
from app.core.agent_generator import confirm_generation, generate_agent
from app.models.user import User

router = APIRouter(tags=["agents"])


class GenerateRequest(BaseModel):
    description: str = Field(
        ..., min_length=10, max_length=2000, description="自然语言描述 Agent 功能"
    )
    name_hint: str | None = Field(
        default=None, min_length=2, max_length=40, description="目录名 hint"
    )


class GenerateResponse(BaseModel):
    session_id: str
    agent_name: str
    class_name: str
    agent_py: str
    manifest_yaml: str
    api_route_py: str
    frontend_page_tsx: str
    frontend_api_ts: str
    planner_entry: dict[str, Any]


class ConfirmRequest(BaseModel):
    session_id: str = Field(..., min_length=1)


class ConfirmResponse(BaseModel):
    status: str
    agent_name: str
    files: list[str]


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    req: GenerateRequest,
    user: User = Depends(enforce_api_rate_limit),
) -> GenerateResponse:
    """LLM 根据自然语言描述生成 Agent 代码骨架（预览，不写入）

    enforce_api_rate_limit：本端点是 LLM 大段代码生成，原挂 platform 域
    绕过了套餐限流与配额强制，这里显式补挂（P1 缺口）。
    """
    result = await generate_agent(req.description, req.name_hint)
    d = result.to_dict()
    return GenerateResponse(**d)


@router.post("/confirm", response_model=ConfirmResponse)
async def confirm(
    req: ConfirmRequest, user: User = Depends(get_current_user)
) -> ConfirmResponse:
    """用户确认后写入正式目录"""
    result = await confirm_generation(req.session_id)
    return ConfirmResponse(**result)

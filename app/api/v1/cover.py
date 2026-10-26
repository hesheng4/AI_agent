"""Cover letter API endpoints"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agents.cover import get_cover_agent
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(tags=["cover"])
_agent = get_cover_agent()


class CoverRequest(BaseModel):
    # task 取值须与 agent 实际实现的三个 handler 一致
    task: str = Field(default="draft", description="draft|audit|presubmission")
    # draft / presubmission 用：论文标题
    title: str = Field(default="", description="draft/presubmission 用")
    # draft / presubmission 用：摘要
    abstract: str = Field(default="", description="draft/presubmission 用")
    # draft 用：关键结果
    key_result: str = Field(default="", description="draft 用")
    # draft 用：显著性陈述
    significance: str = Field(default="", description="draft 用")
    # audit 用：待审计的投稿信正文
    content: str = Field(default="", description="audit 用")
    journal: str = Field(default="nature")
    letter_type: str = Field(default="full")


class CoverResponse(BaseModel):
    result: dict[str, Any]


@router.post("/", response_model=CoverResponse)
async def cover_endpoint(
    req: CoverRequest, user: User = Depends(get_current_user)
) -> CoverResponse:
    result = await _agent.process(
        {
            **req.model_dump(),
            "_user_api_key": user.api_key,
            "_user_api_base_url": user.api_base_url,
            "_user_api_model": user.api_model,
        }
    )
    return CoverResponse(result=result)

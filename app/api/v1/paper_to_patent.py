"""Nature-Paper-to-Patent API: 论文→中国发明专利"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.config import get_settings
from app.models.user import User
from app.utils.logger import get_logger

logger = get_logger("api.paper_to_patent")
router = APIRouter()
settings = get_settings()


class PatentDraftRequest(BaseModel):
    content: str = Field(
        ...,
        min_length=100,
        max_length=settings.MAX_CONTENT_LENGTH,
        description="论文内容",
    )
    task_mode: str = Field(
        default="full_draft",
        description="任务模式: full_draft/claims_only/audit",
    )
    invention_type: str = Field(
        default="algorithm",
        description="发明类型: algorithm/apparatus/process/mixed",
    )


@router.post("/draft")
async def draft_patent(
    request: PatentDraftRequest, current_user: User = Depends(get_current_user)
):
    """论文→中国发明专利草稿"""
    from app.agents.paper_to_patent.agent import PaperToPatentAgent

    logger.info(f"用户 {current_user.id} 生成专利草稿: {request.invention_type}")
    agent = PaperToPatentAgent()
    return await agent.process(
        {
            "content": request.content,
            "task_mode": request.task_mode,
            "invention_type": request.invention_type,
        }
    )

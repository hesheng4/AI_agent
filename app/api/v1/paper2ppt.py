"""Nature-Paper2PPT API: 论文→PPTX"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.config import get_settings
from app.models.user import User
from app.utils.logger import get_logger

logger = get_logger("api.paper2ppt")
router = APIRouter()
settings = get_settings()


class Paper2PPTRequest(BaseModel):
    content: str = Field(
        ...,
        min_length=100,
        max_length=settings.MAX_CONTENT_LENGTH,
        description="论文内容",
    )
    paper_type: str = Field(
        default="auto",
        description=(
            "论文类型: auto/discovery/methods/resource/clinical/materials/review"
        ),
    )


@router.post("/generate")
async def generate_ppt(
    request: Paper2PPTRequest, current_user: User = Depends(get_current_user)
):
    """论文→Nature风格中文PPTX"""
    from app.agents.paper2ppt.agent import Paper2PPTAgent

    logger.info(f"用户 {current_user.id} 生成PPT: {request.paper_type}")
    agent = Paper2PPTAgent()
    return await agent.process(
        {
            "content": request.content,
            "paper_type": request.paper_type,
        }
    )

"""Nature-Reader API: 全文中英对照 Markdown Reader"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.config import get_settings
from app.models.user import User
from app.utils.logger import get_logger

logger = get_logger("api.reader")
router = APIRouter()
settings = get_settings()


class ReadFullRequest(BaseModel):
    content: str = Field(
        ...,
        min_length=50,
        max_length=settings.MAX_CONTENT_LENGTH,
        description="论文全文内容",
    )
    source_format: str = Field(
        default="auto",
        description="源格式: auto/pdf-text/scanned-pdf/html/doi-arxiv/pasted-text",
    )
    journal: str = Field(
        default="generic", description="期刊: nature/nat-comms/generic"
    )
    language: str = Field(default="zh-to-en", description="语言方向: zh-to-en/en")


class ReadFullResponse(BaseModel):
    paper_md: str
    source_map: str
    terminology_ledger: str
    translation_notes: str
    stats: dict[str, Any]


@router.post("/read-full", response_model=ReadFullResponse)
async def read_full(
    request: ReadFullRequest, current_user: User = Depends(get_current_user)
) -> ReadFullResponse:
    """全文中英对照 Markdown Reader"""
    from app.agents.reader.agent import ReaderAgent

    logger.info(f"用户 {current_user.id} 全文阅读: {request.source_format}")
    agent = ReaderAgent()
    result = await agent.process(
        {
            "content": request.content,
            "source_format": request.source_format,
            "journal": request.journal,
            "language": request.language,
        }
    )
    return ReadFullResponse(**result)

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agents.citation import get_citation_agent
from app.api.deps import get_current_user
from app.config import get_settings
from app.models.user import User
from app.utils.logger import get_logger

logger = get_logger("api.citation")
router = APIRouter()
settings = get_settings()


# ─────────────────────────────────────────────
# 请求模型
# ─────────────────────────────────────────────


class AddCitationsRequest(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        max_length=settings.MAX_CONTENT_LENGTH,
        description="论文内容",
    )
    journal_scope: str = Field(
        default="general", description="期刊范围: nature/science/cell/general"
    )


class VerifyCitationsRequest(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        max_length=settings.MAX_CONTENT_LENGTH,
        description="论文内容",
    )
    references: list[str] | None = Field(default=None, description="参考文献列表")


class FormatReferencesRequest(BaseModel):
    references: list[str] = Field(..., min_length=1, description="参考文献列表")
    # 默认 nature，与 agent 默认与 prompts 全篇 Nature 格式对齐
    style: str = Field(
        default="nature",
        description="格式风格: nature/apa/mla/chicago/ieee/vancouver/harvard/gbt7714",
    )


# ─────────────────────────────────────────────
# 响应模型
# ─────────────────────────────────────────────


class AddCitationsResponse(BaseModel):
    status: str
    segments: str
    claims: str
    citations: str
    annotated_text: str
    journal_scope: str


class VerifyCitationsResponse(BaseModel):
    status: str
    verification: str
    total_references: int
    # P0-1: 外部实查（CrossRef/OpenAlex）结果，向后兼容（旧字段不变，新字段可选）
    verified_count: int = 0
    suspicious_count: int = 0
    per_reference: list[dict[str, Any]] = Field(default_factory=list)


class FormatReferencesResponse(BaseModel):
    status: str
    formatted_references: str
    style: str
    total_references: int


# ─────────────────────────────────────────────
# API 路由
# ─────────────────────────────────────────────


@router.post("/add", response_model=AddCitationsResponse)
async def add_citations(
    request: AddCitationsRequest, current_user: User = Depends(get_current_user)
) -> AddCitationsResponse:
    """为文本添加引用"""
    logger.info(f"用户 {current_user.id} 添加引用: 期刊范围={request.journal_scope}")

    agent = get_citation_agent()
    result = await agent.process(
        {
            "task": "add-citations",
            "content": request.content,
            "journal_scope": request.journal_scope,
        }
    )

    return AddCitationsResponse(
        status="success",
        segments=result.get("segments", ""),
        claims=result.get("claims", ""),
        citations=result.get("citations", ""),
        annotated_text=result.get("annotated_text", ""),
        journal_scope=result.get("journal_scope", "general"),
    )


@router.post("/verify", response_model=VerifyCitationsResponse)
async def verify_citations(
    request: VerifyCitationsRequest, current_user: User = Depends(get_current_user)
) -> VerifyCitationsResponse:
    """验证引用匹配度"""
    logger.info(f"用户 {current_user.id} 验证引用")

    agent = get_citation_agent()
    result = await agent.process(
        {
            "task": "verify-citations",
            "content": request.content,
            "references": request.references or [],
        }
    )

    return VerifyCitationsResponse(
        status="success",
        verification=result.get("verification", ""),
        total_references=result.get("total_references", 0),
        verified_count=result.get("verified_count", 0),
        suspicious_count=result.get("suspicious_count", 0),
        per_reference=result.get("per_reference", []),
    )


@router.post("/format", response_model=FormatReferencesResponse)
async def format_references(
    request: FormatReferencesRequest, current_user: User = Depends(get_current_user)
) -> FormatReferencesResponse:
    """格式化参考文献"""
    logger.info(f"用户 {current_user.id} 格式化引用: 风格={request.style}")

    agent = get_citation_agent()
    result = await agent.process(
        {
            "task": "format-references",
            "references": request.references,
            "style": request.style,
        }
    )

    return FormatReferencesResponse(
        status="success",
        formatted_references=result.get("formatted_references", ""),
        style=result.get("style", "nature"),
        total_references=result.get("total_references", 0),
    )

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agents.response.agent import ResponseAgent
from app.api.deps import get_current_user
from app.config import get_settings
from app.models.user import User
from app.utils.logger import get_logger

logger = get_logger("api.response")
router = APIRouter()
settings = get_settings()


# ─────────────────────────────────────────────
# 请求模型
# ─────────────────────────────────────────────


class DraftResponseRequest(BaseModel):
    reviewer_comments: list[str] = Field(
        default_factory=list, description="审稿意见列表（与 review_result 二选一）"
    )
    review_result: dict[str, Any] | None = Field(
        default=None,
        description="reviewer 结构化审稿结果（B3 串联），自动派生审稿意见",
    )
    decision_type: str = Field(
        default="major", description="决策类型: minor/major/revise-and-resubmit"
    )
    manuscript_content: str | None = Field(
        default=None, max_length=settings.MAX_CONTENT_LENGTH, description="稿件内容"
    )
    user_notes: str | None = Field(
        default=None, max_length=settings.MAX_CONTENT_LENGTH, description="作者备注"
    )


class AuditResponseRequest(BaseModel):
    response_content: str = Field(
        ...,
        min_length=1,
        max_length=settings.MAX_CONTENT_LENGTH,
        description="回复内容",
    )
    reviewer_comments: list[str] | None = Field(default=None, description="原审稿意见")


class ReviseResponseRequest(BaseModel):
    response_content: str = Field(
        ...,
        min_length=1,
        max_length=settings.MAX_CONTENT_LENGTH,
        description="当前回复内容",
    )
    feedback: str = Field(
        ...,
        min_length=1,
        max_length=settings.MAX_CONTENT_LENGTH,
        description="修改反馈",
    )
    reviewer_comments: list[str] | None = Field(default=None, description="原审稿意见")


# ─────────────────────────────────────────────
# 响应模型
# ─────────────────────────────────────────────


class DraftResponseResponse(BaseModel):
    status: str
    classification: str
    response_letter: str
    decision_type: str
    total_comments: int


class AuditResponseResponse(BaseModel):
    status: str
    audit_result: str
    total_comments: int


class ReviseResponseResponse(BaseModel):
    status: str
    revised_response: str
    feedback_applied: str


# ─────────────────────────────────────────────
# API 路由
# ─────────────────────────────────────────────


@router.post("/draft", response_model=DraftResponseResponse)
async def draft_response(
    request: DraftResponseRequest, current_user: User = Depends(get_current_user)
) -> DraftResponseResponse:
    """起草审稿回复信"""
    logger.info(
        f"用户 {current_user.id} 起草回复: 决策={request.decision_type}, "
        f"意见数={len(request.reviewer_comments)}"
    )

    agent = ResponseAgent()
    result = await agent.process(
        {
            "task": "draft",
            "reviewer_comments": request.reviewer_comments,
            "review_result": request.review_result,
            "decision_type": request.decision_type,
            "manuscript_content": request.manuscript_content or "",
            "user_notes": request.user_notes or "",
        }
    )

    return DraftResponseResponse(
        status="success",
        classification=result.get("classification", ""),
        response_letter=result.get("response_letter", ""),
        decision_type=result.get("decision_type", "major"),
        total_comments=result.get("total_comments", 0),
    )


@router.post("/audit", response_model=AuditResponseResponse)
async def audit_response(
    request: AuditResponseRequest, current_user: User = Depends(get_current_user)
) -> AuditResponseResponse:
    """审计审稿回复的完整性和语气"""
    logger.info(f"用户 {current_user.id} 审计回复")

    agent = ResponseAgent()
    result = await agent.process(
        {
            "task": "audit",
            "response_content": request.response_content,
            "reviewer_comments": request.reviewer_comments or [],
        }
    )

    return AuditResponseResponse(
        status="success",
        audit_result=result.get("audit_result", ""),
        total_comments=result.get("total_comments", 0),
    )


@router.post("/revise", response_model=ReviseResponseResponse)
async def revise_response(
    request: ReviseResponseRequest, current_user: User = Depends(get_current_user)
) -> ReviseResponseResponse:
    """修改审稿回复"""
    logger.info(f"用户 {current_user.id} 修改回复")

    agent = ResponseAgent()
    result = await agent.process(
        {
            "task": "revise",
            "response_content": request.response_content,
            "feedback": request.feedback,
            "reviewer_comments": request.reviewer_comments or [],
        }
    )

    return ReviseResponseResponse(
        status="success",
        revised_response=result.get("revised_response", ""),
        feedback_applied=result.get("feedback_applied", ""),
    )

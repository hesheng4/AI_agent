from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.config import get_settings
from app.models.user import User
from app.services.review_loop import (
    DEFAULT_MAX_ROUNDS,
    DEFAULT_TARGET_SCORE,
    ReviewLoopService,
)
from app.utils.logger import get_logger

logger = get_logger("api.review_loop")
router = APIRouter()
settings = get_settings()


# ─────────────────────────────────────────────
# 请求 / 响应模型
# ─────────────────────────────────────────────


class ReviewLoopRequest(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        max_length=settings.MAX_CONTENT_LENGTH,
        description="稿件内容",
    )
    paper_type: str = Field(default="research", description="论文类型")
    max_rounds: int = Field(
        default=DEFAULT_MAX_ROUNDS, ge=1, le=10, description="最大迭代轮数（1-10）"
    )
    target_score: float = Field(
        default=DEFAULT_TARGET_SCORE,
        ge=0.0,
        le=10.0,
        description="达标分数阈值（0-10）",
    )


class ReviewLoopRound(BaseModel):
    round: int
    score: float | None
    axes: dict[str, Any] = Field(default_factory=dict)
    suggestion_count: int = 0
    change_summary: str = ""


class ReviewLoopResponse(BaseModel):
    status: str
    final_content: str
    total_rounds: int
    converged: bool
    stop_reason: str
    target_score: float
    max_rounds: int
    rounds: list[ReviewLoopRound] = Field(default_factory=list)


# ─────────────────────────────────────────────
# API 路由
# ─────────────────────────────────────────────


@router.post("/run", response_model=ReviewLoopResponse)
async def run_review_loop(
    request: ReviewLoopRequest, current_user: User = Depends(get_current_user)
) -> ReviewLoopResponse:
    """审稿→修改→再审稿自动迭代闭环（H1，AI-Scientist 借鉴）"""
    logger.info(
        f"用户 {current_user.id} 启动审稿迭代: 类型={request.paper_type}, "
        f"最大轮数={request.max_rounds}, 目标分数={request.target_score}"
    )

    service = ReviewLoopService()
    result = await service.run(
        content=request.content,
        paper_type=request.paper_type,
        max_rounds=request.max_rounds,
        target_score=request.target_score,
    )

    return ReviewLoopResponse(
        status="success",
        final_content=result.get("final_content", ""),
        total_rounds=result.get("total_rounds", 0),
        converged=result.get("converged", False),
        stop_reason=result.get("stop_reason", "max_rounds"),
        target_score=result.get("target_score", request.target_score),
        max_rounds=result.get("max_rounds", request.max_rounds),
        rounds=result.get("rounds", []),
    )

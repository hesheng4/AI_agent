from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agents.reviewer.agent import ReviewerAgent
from app.api.deps import get_current_user
from app.config import get_settings
from app.models.user import User
from app.utils.logger import get_logger

logger = get_logger("api.reviewer")
router = APIRouter()
settings = get_settings()


# ─────────────────────────────────────────────
# 请求模型
# ─────────────────────────────────────────────


class AssessRequest(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        max_length=settings.MAX_CONTENT_LENGTH,
        description="稿件内容",
    )
    paper_type: str = Field(default="research", description="论文类型")
    input_scope: str = Field(default="full manuscript", description="输入范围")


class QuickCheckRequest(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        max_length=settings.MAX_CONTENT_LENGTH,
        description="稿件内容",
    )
    paper_type: str = Field(default="research", description="论文类型")


# ─────────────────────────────────────────────
# 响应模型
# ─────────────────────────────────────────────


class AssessResponse(BaseModel):
    status: str
    fact_base: str
    review_result: str
    paper_type: str
    input_scope: str
    strengths: list[dict] = Field(
        default_factory=list, description="结构化优点清单（B3）"
    )
    improvement_suggestions: list[dict] = Field(
        default_factory=list, description="结构化改进建议清单（B3）"
    )


class QuickCheckResponse(BaseModel):
    status: str
    quick_check: str
    paper_type: str


# ─────────────────────────────────────────────
# API 路由
# ─────────────────────────────────────────────


@router.post("/assess", response_model=AssessResponse)
async def assess_manuscript(
    request: AssessRequest, current_user: User = Depends(get_current_user)
):
    """模拟 Nature 风格审稿（3审稿人 + 交叉综述）"""
    logger.info(f"用户 {current_user.id} 模拟审稿: 类型={request.paper_type}")

    agent = ReviewerAgent()
    result = await agent.process(
        {
            "task": "assess",
            "content": request.content,
            "paper_type": request.paper_type,
            "input_scope": request.input_scope,
        }
    )

    return AssessResponse(
        status="success",
        fact_base=result.get("fact_base", ""),
        review_result=result.get("review_result", ""),
        paper_type=result.get("paper_type", "research"),
        input_scope=result.get("input_scope", "full manuscript"),
        strengths=result.get("strengths", []),
        improvement_suggestions=result.get("improvement_suggestions", []),
    )


@router.post("/quick-check", response_model=QuickCheckResponse)
async def quick_check_manuscript(
    request: QuickCheckRequest, current_user: User = Depends(get_current_user)
):
    """快速预审检查"""
    logger.info(f"用户 {current_user.id} 快速预审")

    agent = ReviewerAgent()
    result = await agent.process(
        {
            "task": "quick-check",
            "content": request.content,
            "paper_type": request.paper_type,
        }
    )

    return QuickCheckResponse(
        status="success",
        quick_check=result.get("quick_check", ""),
        paper_type=result.get("paper_type", "research"),
    )

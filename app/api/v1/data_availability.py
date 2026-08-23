from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agents.data_agent import get_data_availability_agent
from app.api.deps import get_current_user
from app.models.user import User
from app.utils.logger import get_logger

logger = get_logger("api.data_availability")
router = APIRouter()


# ─────────────────────────────────────────────
# 请求模型
# ─────────────────────────────────────────────


class GenerateStatementRequest(BaseModel):
    data_description: str = Field(..., min_length=1, description="数据描述")
    repository_type: str | None = Field(default=None, description="仓库类型")
    restrictions: str | None = Field(default=None, description="访问限制")
    journal: str = Field(default="nature", description="期刊格式")


class AuditStatementRequest(BaseModel):
    statement: str = Field(..., min_length=1, description="数据可用性声明")


class SelectRepositoryRequest(BaseModel):
    data_type: str = Field(..., min_length=1, description="数据类型")
    data_size: str | None = Field(default=None, description="数据大小")
    access_control: str = Field(default="open", description="访问控制: open/restricted")


# ─────────────────────────────────────────────
# 响应模型
# ─────────────────────────────────────────────


class GenerateStatementResponse(BaseModel):
    status: str
    statement: str
    journal: str
    has_restrictions: bool


class AuditStatementResponse(BaseModel):
    status: str
    audit_result: str
    fair_compliance: str


class SelectRepositoryResponse(BaseModel):
    status: str
    recommendation: str
    data_type: str
    access_control: str


# ─────────────────────────────────────────────
# API 路由
# ─────────────────────────────────────────────


@router.post("/generate-statement", response_model=GenerateStatementResponse)
async def generate_statement(
    request: GenerateStatementRequest, current_user: User = Depends(get_current_user)
):
    """生成数据可用性声明"""
    logger.info(f"用户 {current_user.id} 生成数据可用性声明")

    agent = get_data_availability_agent()
    result = await agent.process(
        {
            "task": "generate-statement",
            "data_description": request.data_description,
            "repository_type": request.repository_type or "",
            "restrictions": request.restrictions or "",
            "journal": request.journal,
        }
    )

    return GenerateStatementResponse(
        status="success",
        statement=result.get("statement", ""),
        journal=result.get("journal", "nature"),
        has_restrictions=result.get("has_restrictions", False),
    )


@router.post("/audit-statement", response_model=AuditStatementResponse)
async def audit_statement(
    request: AuditStatementRequest, current_user: User = Depends(get_current_user)
):
    """审计数据可用性声明的 FAIR 合规性"""
    logger.info(f"用户 {current_user.id} 审计数据可用性声明")

    agent = get_data_availability_agent()
    result = await agent.process(
        {"task": "audit-statement", "statement": request.statement}
    )

    return AuditStatementResponse(
        status="success",
        audit_result=result.get("audit_result", ""),
        fair_compliance=result.get("fair_compliance", "pending_review"),
    )


@router.post("/select-repository", response_model=SelectRepositoryResponse)
async def select_repository(
    request: SelectRepositoryRequest, current_user: User = Depends(get_current_user)
):
    """推荐数据仓库"""
    logger.info(f"用户 {current_user.id} 推荐数据仓库: 类型={request.data_type}")

    agent = get_data_availability_agent()
    result = await agent.process(
        {
            "task": "select-repository",
            "data_type": request.data_type,
            "data_size": request.data_size or "",
            "access_control": request.access_control,
        }
    )

    return SelectRepositoryResponse(
        status="success",
        recommendation=result.get("recommendation", ""),
        data_type=result.get("data_type", ""),
        access_control=result.get("access_control", "open"),
    )

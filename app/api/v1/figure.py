"""Nature-Figure API: 论文级 Figure Contract + 期刊导出"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.models.user import User
from app.utils.logger import get_logger

logger = get_logger("api.figure")
router = APIRouter()


class FigureContractRequest(BaseModel):
    conclusion: str = Field(..., description="图表核心结论")
    evidence_chain: list[str] = Field(default=[], description="证据链")
    archetype: str = Field(
        default="comparison",
        description=(
            "图原型: comparison/distribution/correlation/time_series/"
            "composition/spatial/network"
        ),
    )
    journal: str = Field(
        default="generic", description="期刊: nature/nat-comms/generic"
    )
    backend: str = Field(default="python", description="后端: python/r")


class FigureQARequest(BaseModel):
    contract: dict[str, Any] = Field(..., description="Figure Contract")


@router.post("/contract")
async def create_contract(
    request: FigureContractRequest, current_user: User = Depends(get_current_user)
):
    """创建 Figure Contract"""
    from app.agents.figure.agent import FigureAgent

    agent = FigureAgent()
    return await agent.process(
        {
            "task": "create_contract",
            "conclusion": request.conclusion,
            "evidence_chain": request.evidence_chain,
            "archetype": request.archetype,
            "journal": request.journal,
            "backend": request.backend,
        }
    )


@router.post("/apply-style")
async def apply_style(
    journal: str = "generic",
    current_user: User = Depends(get_current_user),
):
    """应用期刊级 matplotlib 样式"""
    from app.agents.figure.agent import FigureAgent

    agent = FigureAgent()
    return await agent.process({"task": "apply_style", "journal": journal})


@router.post("/qa")
async def qa_check(
    request: FigureQARequest, current_user: User = Depends(get_current_user)
):
    """Figure QA 检查"""
    from app.agents.figure.agent import FigureAgent

    agent = FigureAgent()
    return await agent.process({"task": "qa", "contract": request.contract})

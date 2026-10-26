from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agents.experiment import get_experiment_agent
from app.agents.experiment.tools import ExperimentTools
from app.api.deps import get_current_user
from app.models.user import User
from app.utils.logger import get_logger

logger = get_logger("api.experiment")
router = APIRouter()


# 请求模型
class DesignRequest(BaseModel):
    research_goal: str = Field(..., min_length=1, description="研究目标")
    variables: list[str] = Field(default=[], description="变量列表")
    design_type: str = Field(
        default="between",
        description="设计类型: between/within/mixed/factorial/repeated",
    )


class OptimizeRequest(BaseModel):
    historical_data: list[dict[str, Any]] = Field(..., description="历史数据")
    target_metric: str = Field(default="score", description="目标指标")


class PredictRequest(BaseModel):
    params: dict[str, Any] = Field(..., description="参数")
    historical_data: list[dict[str, Any]] = Field(..., description="历史数据")


class PowerAnalysisRequest(BaseModel):
    effect_size: float = Field(..., ge=0.01, le=2.0, description="效应量")
    alpha: float = Field(default=0.05, description="显著性水平")
    power: float = Field(default=0.8, description="统计功效")


# 响应模型
class DesignResponse(BaseModel):
    status: str
    plan: dict[str, Any]
    optimized_plan: str


class OptimizeResponse(BaseModel):
    status: str
    result: dict[str, Any]
    explanation: str


class PredictResponse(BaseModel):
    status: str
    prediction: dict[str, Any]
    explanation: str


class PowerAnalysisResponse(BaseModel):
    status: str
    result: dict[str, Any]


class StatisticalTestResponse(BaseModel):
    status: str
    recommendation: dict[str, Any]


class StatisticalTestRequest(BaseModel):
    """统计检验推荐请求体（替代原来的 dict[str, Any]）"""

    variable_type: str = Field(
        default="continuous", description="变量类型: continuous/categorical/ordinal"
    )
    group_count: int = Field(default=2, ge=1, le=20, description="组数")
    paired: bool = Field(default=False, description="是否配对样本")


@router.post("/design", response_model=DesignResponse)
async def design_experiment(
    request: DesignRequest, current_user: User = Depends(get_current_user)
) -> DesignResponse:
    """设计实验方案"""
    logger.info(f"用户 {current_user.id} 设计实验: {request.research_goal}")

    agent = get_experiment_agent()
    result = await agent.process(
        {
            "task": "design",
            "research_goal": request.research_goal,
            "variables": request.variables,
            "design_type": request.design_type,
        }
    )

    return DesignResponse(
        status="success",
        plan=result.get("plan", {}),
        optimized_plan=result.get("optimized_plan", ""),
    )


@router.post("/optimize", response_model=OptimizeResponse)
async def optimize_parameters(
    request: OptimizeRequest, current_user: User = Depends(get_current_user)
) -> OptimizeResponse:
    """参数优化"""
    logger.info(f"用户 {current_user.id} 优化参数")

    agent = get_experiment_agent()
    result = await agent.process(
        {
            "task": "optimize",
            "historical_data": request.historical_data,
            "target_metric": request.target_metric,
        }
    )

    return OptimizeResponse(
        status="success",
        result=result.get("result", {}),
        explanation=result.get("explanation", ""),
    )


@router.post("/predict", response_model=PredictResponse)
async def predict_result(
    request: PredictRequest, current_user: User = Depends(get_current_user)
) -> PredictResponse:
    """结果预测"""
    logger.info(f"用户 {current_user.id} 预测结果")

    agent = get_experiment_agent()
    result = await agent.process(
        {
            "task": "predict",
            "params": request.params,
            "historical_data": request.historical_data,
        }
    )

    return PredictResponse(
        status="success",
        prediction=result.get("prediction", {}),
        explanation=result.get("explanation", ""),
    )


@router.post("/power-analysis", response_model=PowerAnalysisResponse)
async def power_analysis(
    request: PowerAnalysisRequest, current_user: User = Depends(get_current_user)
) -> PowerAnalysisResponse:
    """功效分析"""
    logger.info(f"用户 {current_user.id} 功效分析")

    tools = ExperimentTools()
    result = tools.calculate_power_analysis(
        effect_size=request.effect_size, alpha=request.alpha, power=request.power
    )

    return PowerAnalysisResponse(status="success", result=result)


@router.post("/statistical-test", response_model=StatisticalTestResponse)
async def recommend_statistical_test(
    request: StatisticalTestRequest, current_user: User = Depends(get_current_user)
) -> StatisticalTestResponse:
    """推荐统计检验方法"""
    logger.info(f"用户 {current_user.id} 获取统计检验推荐")

    tools = ExperimentTools()
    result = tools.select_statistical_test(
        variable_type=request.variable_type,
        group_count=request.group_count,
        paired=request.paired,
    )

    return StatisticalTestResponse(status="success", recommendation=result)

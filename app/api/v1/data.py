from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agents.data import get_data_agent
from app.api.deps import get_current_user
from app.models.user import User
from app.utils.logger import get_logger

logger = get_logger("api.data")
router = APIRouter()


# 请求模型
class AnalyzeRequest(BaseModel):
    data: list[dict[str, Any]] = Field(..., description="数据列表")
    analysis_type: str = Field(
        default="descriptive",
        description="分析类型: descriptive/correlation/outlier/group",
    )
    group_col: str | None = Field(default=None, description="分组列名（group分析需要）")
    value_col: str | None = Field(default=None, description="值列名（group分析需要）")


class VisualizeRequest(BaseModel):
    data: list[dict[str, Any]] = Field(..., description="数据列表")
    chart_type: str = Field(default="bar", description="图表类型: bar/line/pie/scatter")


class UploadRequest(BaseModel):
    data: list[dict[str, Any]] = Field(..., description="数据列表")
    filename: str = Field(default="data.csv", description="文件名")


# 响应模型
class AnalyzeResponse(BaseModel):
    status: str
    results: dict[str, Any]
    explanation: str
    data_shape: list[int]
    analysis_type: str


class VisualizeResponse(BaseModel):
    status: str
    chart_type: str
    columns: list[str]
    dtypes: dict[str, str]
    recommendation: str


class UploadResponse(BaseModel):
    status: str
    filename: str
    summary: dict[str, Any]


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_data(
    request: AnalyzeRequest, current_user: User = Depends(get_current_user)
) -> AnalyzeResponse:
    """数据分析"""
    logger.info(f"用户 {current_user.id} 执行分析: {request.analysis_type}")

    agent = get_data_agent()
    result = await agent.process(
        {
            "task": "analyze",
            "data": request.data,
            "analysis_type": request.analysis_type,
            "group_col": request.group_col,
            "value_col": request.value_col,
        }
    )

    return AnalyzeResponse(**result)


@router.post("/visualize", response_model=VisualizeResponse)
async def visualize_data(
    request: VisualizeRequest, current_user: User = Depends(get_current_user)
) -> VisualizeResponse:
    """可视化建议"""
    logger.info(f"用户 {current_user.id} 请求可视化: {request.chart_type}")

    agent = get_data_agent()
    result = await agent.process(
        {"task": "visualize", "data": request.data, "chart_type": request.chart_type}
    )

    return VisualizeResponse(**result)


@router.post("/upload", response_model=UploadResponse)
async def upload_data(
    request: UploadRequest, current_user: User = Depends(get_current_user)
) -> UploadResponse:
    """上传数据"""
    logger.info(f"用户 {current_user.id} 上传数据: {request.filename}")

    agent = get_data_agent()
    result = await agent.process(
        {"task": "upload", "data": request.data, "filename": request.filename}
    )

    return UploadResponse(**result)

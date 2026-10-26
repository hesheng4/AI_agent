"""Agent 产出物 API（credibility-convergence v1 步骤 6）

能力面：创建 → 列表（按 agent 筛选）→ 重新导出（payload 透传）→ 删除。
所有端点严格 user_id 隔离；保存非 LLM 操作，不挂套餐限流。
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services.artifact_service import (
    ArtifactError,
    ArtifactService,
)

router = APIRouter()
artifact_service = ArtifactService()


def _map_artifact_error(exc: ArtifactError) -> HTTPException:
    """把服务层异常映射为 HTTPException"""
    return HTTPException(status_code=exc.status_code, detail=exc.message)


class ArtifactCreateRequest(BaseModel):
    agent: str = Field(..., min_length=1, max_length=64, description="产出 agent 名")
    title: str = Field(..., min_length=1, max_length=200, description="标题")
    payload: dict[str, Any] = Field(..., description="Agent 结构化产出")


class ArtifactResponse(BaseModel):
    id: str
    agent: str
    title: str
    payload: dict[str, Any]
    created_at: str | None


@router.post("/", response_model=ArtifactResponse)
async def create_artifact(
    request: ArtifactCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArtifactResponse:
    """保存 Agent 产出物"""
    data = await artifact_service.create_artifact(
        db,
        current_user.id,
        agent=request.agent,
        title=request.title,
        payload=request.payload,
    )
    return ArtifactResponse(**data)


@router.get("/", response_model=list[ArtifactResponse])
async def list_artifacts(
    agent: str | None = Query(default=None, description="按 agent 名筛选"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ArtifactResponse]:
    """列出当前用户的产出物（按创建时间倒序）"""
    items = await artifact_service.list_artifacts(
        db, current_user.id, agent=agent, limit=limit, offset=offset
    )
    return [ArtifactResponse(**d) for d in items]


@router.get("/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(
    artifact_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArtifactResponse:
    """单条读取（重新导出 payload 用）"""
    try:
        data = await artifact_service.get_artifact(db, current_user.id, artifact_id)
    except ArtifactError as e:
        raise _map_artifact_error(e) from e
    return ArtifactResponse(**data)


@router.delete("/{artifact_id}")
async def delete_artifact(
    artifact_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """删除产出物"""
    try:
        await artifact_service.delete_artifact(db, current_user.id, artifact_id)
    except ArtifactError as e:
        raise _map_artifact_error(e) from e
    return {"status": "success", "message": "已删除"}

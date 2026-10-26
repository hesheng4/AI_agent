"""分享链接 API（credibility-convergence v1 步骤 7）

owner 侧：创建（明文 token 只返回一次）/ 列表 / 撤销。
接收方侧：必须登录；预览快照；fork 深拷贝到自己的文献库。
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services.share_service import (
    ShareError,
    ShareService,
)

router = APIRouter()
share_service = ShareService()


def _map_share_error(exc: ShareError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


class ShareCreateRequest(BaseModel):
    resource_type: str = Field(..., description="library | artifact")
    resource_id: str | None = Field(
        default=None, description="artifact 分享必填；library 分享忽略"
    )
    ttl_days: int | None = Field(
        default=7, ge=1, le=365, description="有效期天数；null = 永久"
    )


class ShareCreateResponse(BaseModel):
    id: str
    resource_type: str
    resource_id: str
    token: str  # 明文 token 仅在此响应中出现一次
    expires_at: str | None


class ShareItemResponse(BaseModel):
    id: str
    resource_type: str
    resource_id: str
    expires_at: str | None
    revoked: bool
    created_at: str | None


class SharedLibraryResponse(BaseModel):
    resource_type: str
    owner: str
    paper_count: int
    papers: list[dict[str, Any]]
    categories: list[str]
    tags: list[str]
    citation_count: int


class ForkResponse(BaseModel):
    papers_added: int
    papers_skipped: int
    categories_created: int
    tags_created: int
    notes_copied: int
    citations_copied: int
    citations_skipped: int


@router.post("/", response_model=ShareCreateResponse)
async def create_share(
    request: ShareCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ShareCreateResponse:
    """创建分享链接（明文 token 只返回这一次）"""
    try:
        data = await share_service.create_share(
            db,
            current_user,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            ttl_days=request.ttl_days,
        )
    except ShareError as e:
        raise _map_share_error(e) from e
    return ShareCreateResponse(**data)


@router.get("/", response_model=list[ShareItemResponse])
async def list_shares(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ShareItemResponse]:
    """列出我创建的分享"""
    items = await share_service.list_shares(db, current_user.id)
    return [ShareItemResponse(**d) for d in items]


@router.delete("/{share_id}")
async def revoke_share(
    share_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """撤销分享（仅 owner）"""
    try:
        await share_service.revoke_share(db, current_user.id, share_id)
    except ShareError as e:
        raise _map_share_error(e) from e
    return {"status": "success", "message": "已撤销"}


@router.get("/by-token/{token}")
async def get_shared_resource(
    token: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """按 token 预览分享内容（接收方须登录，不静默降级为公开）"""
    try:
        share = await share_service.resolve_share(db, token)
        if share.resource_type == "library":
            return await share_service.get_shared_library(db, share)
        return await share_service.get_shared_artifact(db, share)
    except ShareError as e:
        raise _map_share_error(e) from e


@router.post("/by-token/{token}/fork", response_model=ForkResponse)
async def fork_shared_library(
    token: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ForkResponse:
    """把分享的文献库深拷贝到我的文献库"""
    try:
        share = await share_service.resolve_share(db, token)
        stats = await share_service.fork_library(db, share, current_user.id)
    except ShareError as e:
        raise _map_share_error(e) from e
    return ForkResponse(**stats)

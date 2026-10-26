"""ShareService — 分享链接 + fork 深拷贝（credibility-convergence v1 步骤 7）

安全纪律（契约 §2，对齐 refresh token）：
- token 复用 auth.py 的 secrets.token_urlsafe(32)；DB 只存 sha256 哈希，
  明文仅在创建响应中返回一次
- TTL 默认 7 天，可为永久（ttl_days=None）；显式撤销 DELETE /shares/{id}
- 接收方必须登录（路由层 get_current_user），不静默降级为公开

fork 语义（契约决策 #8，golden 门禁 G8）：
- 全量深拷贝：文献 + 分类/标签按名字重建 + 笔记 + 引用关系
- tag usage_count 与 category paper_count 必须复用 LibraryService.add_* /
  create_* 逐条写入保证计数正确（不得 bulk insert）
- 引用关系按 paper_id 映射重连；两端任一被跳过（接收方已收藏同名外部
  paper_id）则该条引用跳过
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shares import ShareLink
from app.models.user import User
from app.services.library_service import (
    CitationAlreadyExistsError,
    LibraryService,
    PaperAlreadyExistsError,
)
from app.utils.logger import get_logger

logger = get_logger("services.shares")

# 分享默认有效期（天）；ttl_days=None 表示永久
DEFAULT_SHARE_TTL_DAYS = 7
# 本轮支持的资源类型（契约：只实现 library 与 artifact 两类）
_SHAREABLE_TYPES = ("library", "artifact")


class ShareError(Exception):
    """Share 服务层异常基类（保留 status_code 供路由层映射）"""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ShareNotFoundError(ShareError):
    def __init__(self, message: str = "分享不存在"):
        super().__init__(message, status_code=404)


class ShareInvalidError(ShareError):
    def __init__(self, message: str = "分享链接无效或已过期"):
        super().__init__(message, status_code=410)


class ShareForbiddenError(ShareError):
    def __init__(self, message: str = "无权操作该分享"):
        super().__init__(message, status_code=403)


def hash_token(token: str) -> str:
    """明文 token -> sha256 hex（DB 只存哈希）"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def share_to_dict(s: ShareLink, *, include_owner: bool = False) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": s.id,
        "resource_type": s.resource_type,
        "resource_id": s.resource_id,
        "expires_at": str(s.expires_at) if s.expires_at else None,
        "revoked": bool(s.revoked),
        "created_at": str(s.created_at) if s.created_at else None,
    }
    if include_owner:
        d["owner_id"] = s.owner_id
    return d


class ShareService:
    """分享链接创建/解析/撤销 + library fork"""

    def __init__(self) -> None:
        self.library = LibraryService()

    # ---------- 创建 / 管理（owner 侧） ----------

    async def create_share(
        self,
        db: AsyncSession,
        owner: User,
        *,
        resource_type: str,
        resource_id: str | None = None,
        ttl_days: int | None = DEFAULT_SHARE_TTL_DAYS,
    ) -> dict[str, Any]:
        """创建分享链接。明文 token 仅在本返回值中出现一次。

        library 分享的 resource_id 固定为 owner.id（当前无 workspace 概念，
        整库即分享对象）；artifact 分享的 resource_id 必须属于 owner。
        """
        if resource_type not in _SHAREABLE_TYPES:
            raise ShareError(f"不支持的分享类型: {resource_type}")

        if resource_type == "library":
            rid = owner.id
        else:
            if not resource_id:
                raise ShareError("artifact 分享必须提供 resource_id")
            artifact = await self._find_artifact(db, owner.id, resource_id)
            if artifact is None:
                raise ShareNotFoundError("产出物不存在或不属于当前用户")
            rid = resource_id

        token = secrets.token_urlsafe(32)
        expires_at = (
            datetime.now(UTC) + timedelta(days=ttl_days)
            if ttl_days is not None
            else None
        )
        share = ShareLink(
            id=str(uuid.uuid4()),
            owner_id=owner.id,
            resource_type=resource_type,
            resource_id=rid,
            token_hash=hash_token(token),
            expires_at=expires_at,
        )
        db.add(share)
        await db.commit()
        await db.refresh(share)
        logger.info(f"用户 {owner.id} 创建分享: type={resource_type}, ttl={ttl_days}")
        return {**share_to_dict(share), "token": token}

    async def list_shares(
        self, db: AsyncSession, owner_id: str
    ) -> list[dict[str, Any]]:
        result = await db.execute(
            select(ShareLink)
            .where(ShareLink.owner_id == owner_id)
            .order_by(ShareLink.created_at.desc())
        )
        return [share_to_dict(s) for s in result.scalars().all()]

    async def revoke_share(
        self, db: AsyncSession, owner_id: str, share_id: str
    ) -> None:
        share = await self._find_owned(db, owner_id, share_id)
        if share is None:
            raise ShareNotFoundError()
        share.revoked = 1
        await db.commit()
        logger.info(f"用户 {owner_id} 撤销分享: {share_id}")

    # ---------- 解析（接收方侧） ----------

    async def resolve_share(self, db: AsyncSession, token: str) -> ShareLink:
        """按明文 token 解析有效分享：哈希匹配 + 未撤销 + 未过期"""
        result = await db.execute(
            select(ShareLink).where(ShareLink.token_hash == hash_token(token))
        )
        share = result.scalar_one_or_none()
        if share is None or share.revoked:
            raise ShareNotFoundError()
        if share.expires_at is not None:
            expires = share.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=UTC)
            if datetime.now(UTC) >= expires:
                raise ShareInvalidError()
        return share

    async def get_shared_library(
        self, db: AsyncSession, share: ShareLink
    ) -> dict[str, Any]:
        """library 分享预览：接收方 fork 前看到的整库快照"""
        if share.resource_type != "library":
            raise ShareError("该分享不是文献库分享")
        owner_id = share.owner_id
        owner = await db.get(User, owner_id)
        owner_name = owner.username if owner else owner_id
        papers = await self.library.papers.list_papers(db, owner_id, limit=100000)
        categories = await self.library.categories.list_categories(db, owner_id)
        tags = await self.library.tags.list_tags(db, owner_id)
        citations = await self.library.citations.list_citations(
            db, owner_id, limit=100000
        )
        return {
            "resource_type": "library",
            "owner": owner_name,
            "paper_count": len(papers),
            "papers": [
                {
                    "title": p["title"],
                    "year": p["year"],
                    "journal": p["journal"],
                    "tags": p["tags"],
                    "category": p["category"],
                }
                for p in papers
            ],
            "categories": [c["name"] for c in categories],
            "tags": [t["name"] for t in tags],
            "citation_count": len(citations),
        }

    async def fork_library(
        self, db: AsyncSession, share: ShareLink, recipient_id: str
    ) -> dict[str, Any]:
        """把 owner 的整库深拷贝到接收方（可独立演化的完整库）。

        计数正确性：分类/标签先按名字重建，文献复用 papers.add_paper
        逐条写入（内部同步 usage_count/paper_count），笔记与引用随后重连。
        """
        if share.resource_type != "library":
            raise ShareError("该分享不是文献库分享")
        if share.owner_id == recipient_id:
            raise ShareError("不能 fork 自己的文献库")

        # commit 会使 ORM 对象过期（expire_on_commit=True），后续任何
        # share.owner_id 访问都会触发同步 IO（MissingGreenlet）。
        # 先把标量捕获到局部变量，全程只用局部值。
        owner_id = share.owner_id

        # 1. 分类按名字重建（uncategorized 不是真实记录，跳过；重名跳过）
        categories_created = 0
        for c in await self.library.categories.list_categories(db, owner_id):
            if c["name"] == "uncategorized":
                continue
            try:
                await self.library.categories.create_category(
                    db, recipient_id, name=c["name"], color=c.get("color") or "#6366f1"
                )
                categories_created += 1
            except Exception:  # noqa: BLE001 — 重名分类视为已存在，跳过
                await db.rollback()

        # 2. 标签按名字重建（零引用标签也保留；add_paper 随后调整 usage_count）
        tags_created = 0
        for t in await self.library.tags.list_tags(db, owner_id):
            try:
                await self.library.tags.create_tag(
                    db, recipient_id, name=t["name"], color=t.get("color") or "#10b981"
                )
                tags_created += 1
            except Exception:  # noqa: BLE001 — 重名标签视为已存在，跳过
                await db.rollback()

        # 3. 文献逐条 add_paper（计数同步内建于该方法）
        papers_added = papers_skipped = 0
        id_map: dict[str, str | None] = {}
        source_papers = await self.library.papers.list_papers(
            db, owner_id, limit=100000
        )
        for p in source_papers:
            try:
                new_paper = await self.library.papers.add_paper(
                    db,
                    recipient_id,
                    paper_id=p["paper_id"],
                    title=p["title"],
                    authors=p.get("authors") or [],
                    abstract=p.get("abstract"),
                    year=p.get("year"),
                    journal=p.get("journal"),
                    url=p.get("url"),
                    source=p.get("source"),
                    tags=p.get("tags") or [],
                    category=p.get("category"),
                    notes=p.get("notes"),
                )
                id_map[p["id"]] = new_paper["id"]
                papers_added += 1
            except PaperAlreadyExistsError:
                await db.rollback()
                id_map[p["id"]] = None
                papers_skipped += 1

        # 4. 笔记随文献拷贝
        notes_copied = 0
        for p in source_papers:
            new_id = id_map.get(p["id"])
            if not new_id:
                continue
            for n in await self.library.notes.list_notes(db, owner_id, p["id"]):
                await self.library.notes.create_note(
                    db,
                    recipient_id,
                    paper_id=new_id,
                    content=n["content"],
                    note_type=n.get("note_type") or "general",
                    page_range=n.get("page_range"),
                )
                notes_copied += 1

        # 5. 引用关系按 paper_id 映射重连（两端均映射成功才重建）
        citations_copied = citations_skipped = 0
        source_citations = await self.library.citations.list_citations(
            db, owner_id, limit=100000
        )
        for c in source_citations:
            new_citing = id_map.get(c["citing_paper_id"])
            new_cited = id_map.get(c["cited_paper_id"])
            if not new_citing or not new_cited:
                citations_skipped += 1
                continue
            try:
                await self.library.citations.add_citation(
                    db,
                    recipient_id,
                    citing_paper_id=new_citing,
                    cited_paper_id=new_cited,
                    weight=c.get("weight") or 1,
                    source=c.get("source") or "manual",
                )
                citations_copied += 1
            except CitationAlreadyExistsError:
                await db.rollback()
                citations_skipped += 1

        logger.info(
            f"用户 {recipient_id} fork 库 {owner_id}: "
            f"papers={papers_added}+{papers_skipped} skipped, "
            f"notes={notes_copied}, citations={citations_copied}"
        )
        return {
            "papers_added": papers_added,
            "papers_skipped": papers_skipped,
            "categories_created": categories_created,
            "tags_created": tags_created,
            "notes_copied": notes_copied,
            "citations_copied": citations_copied,
            "citations_skipped": citations_skipped,
        }

    async def get_shared_artifact(
        self, db: AsyncSession, share: ShareLink
    ) -> dict[str, Any]:
        """artifact 分享预览：只读 payload"""
        if share.resource_type != "artifact":
            raise ShareError("该分享不是产出物分享")
        artifact = await self._find_artifact(db, share.owner_id, share.resource_id)
        if artifact is None:
            raise ShareNotFoundError("产出物已被删除")
        owner = await db.get(User, share.owner_id)
        return {
            "resource_type": "artifact",
            "owner": owner.username if owner else share.owner_id,
            "artifact": artifact,
        }

    # ---------- 内部 ----------

    async def _find_owned(
        self, db: AsyncSession, owner_id: str, share_id: str
    ) -> ShareLink | None:
        result = await db.execute(
            select(ShareLink).where(
                ShareLink.owner_id == owner_id, ShareLink.id == share_id
            )
        )
        return result.scalar_one_or_none()

    async def _find_artifact(
        self, db: AsyncSession, owner_id: str, artifact_id: str
    ) -> Any:
        from app.models.artifacts import AgentArtifact

        result = await db.execute(
            select(AgentArtifact).where(
                AgentArtifact.user_id == owner_id, AgentArtifact.id == artifact_id
            )
        )
        return result.scalar_one_or_none()

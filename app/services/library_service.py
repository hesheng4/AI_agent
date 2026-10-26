"""统一 LibraryService - 痛点 1 的完整状态同步

把原本散落在 app/api/v1/library.py 路由层的业务逻辑抽到服务层，
集中处理文献收藏/分类/标签/引用关系/阅读笔记之间的状态同步：

- add_paper: 创建收藏 + 自动维护 tag.usage_count + category.paper_count
- update_paper: 字段更新 + tags 变更 diff 同步 usage_count
  + category 变更同步 paper_count
- delete_paper: 删除收藏 + 级联清理 notes/citations + 回收 tag/category 计数
- delete_category: 把该分类下 papers 改为 uncategorized
- delete_tag: 从所有 papers 的 tags 列表移除该标签
- add_citation: 自动从 PaperCollection 回填 citing/cited_title
- CitationService._build_network: 消除 8 处网络分析路由的重复加载代码

服务层方法自行管理事务（commit），与原路由层语义保持一致；
路由层只负责参数解析、鉴权与响应序列化。
"""

import uuid
from typing import Any, cast

from sqlalchemy import CursorResult, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.library import (
    CitationRelation,
    PaperCategory,
    PaperCollection,
    PaperTag,
    ReadingNote,
)
from app.services.citation_network import CitationNetwork
from app.utils.logger import get_logger

logger = get_logger("services.library")


# ========== 异常 ==========


class LibraryError(Exception):
    """Library 服务层异常基类

    注：未继承 AppException 以保留 status_code 属性供 _map_library_error 使用。
    业务代码可捕获 LibraryError 或通过 library.py 路由层映射为 HTTPException。
    """

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class PaperNotFoundError(LibraryError):
    def __init__(self, message: str = "文献不存在"):
        super().__init__(message, status_code=404)


class PaperAlreadyExistsError(LibraryError):
    def __init__(self, message: str = "文献已收藏"):
        super().__init__(message, status_code=400)


class CategoryNotFoundError(LibraryError):
    def __init__(self, message: str = "分类不存在"):
        super().__init__(message, status_code=404)


class TagNotFoundError(LibraryError):
    def __init__(self, message: str = "标签不存在"):
        super().__init__(message, status_code=404)


class CitationNotFoundError(LibraryError):
    def __init__(self, message: str = "引用关系不存在"):
        super().__init__(message, status_code=404)


class CitationAlreadyExistsError(LibraryError):
    def __init__(self, message: str = "引用关系已存在"):
        super().__init__(message, status_code=400)


class NoteNotFoundError(LibraryError):
    def __init__(self, message: str = "笔记不存在"):
        super().__init__(message, status_code=404)


# ========== 响应序列化辅助 ==========


def paper_to_dict(p: PaperCollection) -> dict[str, Any]:
    """PaperCollection -> 响应 dict（与原 PaperResponse 字段一致）"""
    return {
        "id": p.id,
        "paper_id": p.paper_id,
        "title": p.title,
        "authors": p.authors or [],
        "abstract": p.abstract,
        "year": p.year,
        "journal": p.journal,
        "url": p.url,
        "source": p.source,
        "tags": p.tags or [],
        "category": p.category,
        "notes": p.notes,
        "rating": p.rating,
        "is_favorite": p.is_favorite or 0,
        "created_at": str(p.created_at) if p.created_at else None,
    }


def category_to_dict(c: PaperCategory) -> dict[str, Any]:
    return {
        "id": c.id,
        "name": c.name,
        "description": c.description,
        "color": c.color,
        "parent_id": c.parent_id,
        "paper_count": c.paper_count or 0,
    }


def tag_to_dict(t: PaperTag) -> dict[str, Any]:
    return {
        "id": t.id,
        "name": t.name,
        "color": t.color,
        "usage_count": t.usage_count or 0,
    }


def citation_to_dict(c: CitationRelation) -> dict[str, Any]:
    return {
        "id": c.id,
        "citing_paper_id": c.citing_paper_id,
        "cited_paper_id": c.cited_paper_id,
        "citing_title": c.citing_title,
        "cited_title": c.cited_title,
        "weight": c.weight or 1,
        "source": c.source or "manual",
        "created_at": str(c.created_at) if c.created_at else None,
    }


def note_to_dict(n: ReadingNote) -> dict[str, Any]:
    return {
        "id": n.id,
        "paper_id": n.paper_id,
        "content": n.content,
        "note_type": n.note_type or "general",
        "page_range": n.page_range,
        "created_at": str(n.created_at) if n.created_at else None,
        "updated_at": str(n.updated_at) if n.updated_at else None,
    }


# ========== PaperService ==========


class PaperService:
    """文献收藏服务 - 维护与 tag/category 的状态同步"""

    async def add_paper(
        self,
        db: AsyncSession,
        user_id: str,
        *,
        paper_id: str,
        title: str,
        authors: list[str] | None = None,
        abstract: str | None = None,
        year: int | None = None,
        journal: str | None = None,
        url: str | None = None,
        source: str | None = None,
        tags: list[str] | None = None,
        category: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """添加文献到收藏，同步 tag.usage_count 与 category.paper_count"""
        # 1. 检查是否已收藏（业务层校验，DB 唯一约束作为兜底）
        existing = await db.execute(
            select(PaperCollection).where(
                PaperCollection.user_id == user_id, PaperCollection.paper_id == paper_id
            )
        )
        if existing.scalar_one_or_none():
            raise PaperAlreadyExistsError()

        try:
            # 2. 创建收藏
            paper = PaperCollection(
                id=str(uuid.uuid4()),
                user_id=user_id,
                paper_id=paper_id,
                title=title,
                authors=authors or [],
                abstract=abstract,
                year=year,
                journal=journal,
                url=url,
                source=source,
                tags=tags or [],
                category=category or "uncategorized",
                notes=notes,
            )
            db.add(paper)
            await db.flush()  # 拿到 id，但未提交

            # 3. 同步 tag usage_count
            tag_service = TagService()
            await tag_service._adjust_usage(db, user_id, tags or [], delta=+1)

            # 4. 同步 category paper_count
            category_service = CategoryService()
            await category_service._adjust_paper_count(
                db, user_id, paper.category, delta=+1
            )

            await db.commit()
            await db.refresh(paper)
            logger.info(f"用户 {user_id} 添加文献: {title[:50]}")
            return paper_to_dict(paper)
        except IntegrityError as e:
            # 并发场景下另一请求先插入，唯一约束兜底
            await db.rollback()
            logger.warning(f"用户 {user_id} 添加文献触发唯一约束: {paper_id}")
            raise PaperAlreadyExistsError() from e
        except Exception:
            await db.rollback()
            raise

    async def list_papers(
        self,
        db: AsyncSession,
        user_id: str,
        *,
        category: str | None = None,
        tag: str | None = None,
        favorite: int | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """获取收藏文献列表（支持 category/tag/favorite/search 过滤）"""
        query = select(PaperCollection).where(PaperCollection.user_id == user_id)

        if category:
            query = query.where(PaperCollection.category == category)
        if favorite is not None:
            query = query.where(PaperCollection.is_favorite == favorite)
        if tag:
            # JSON 列表包含查询：SQLite 用 json_each；这里用 like 兜底
            query = query.where(PaperCollection.tags.like(f'%"{tag}"%'))
        if search:
            query = query.where(PaperCollection.title.ilike(f"%{search}%"))

        query = (
            query.order_by(PaperCollection.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(query)
        return [paper_to_dict(p) for p in result.scalars().all()]

    async def get_paper(
        self, db: AsyncSession, user_id: str, paper_id: str
    ) -> dict[str, Any]:
        """获取单个收藏文献 - paper_id 可以是数据库ID或外部paper_id"""
        paper = await self._find_paper(db, user_id, paper_id)
        if not paper:
            raise PaperNotFoundError()
        return paper_to_dict(paper)

    async def update_paper(
        self,
        db: AsyncSession,
        user_id: str,
        paper_id: str,
        *,
        tags: list[str] | None = None,
        category: str | None = None,
        notes: str | None = None,
        rating: int | None = None,
        is_favorite: int | None = None,
    ) -> dict[str, Any]:
        """更新收藏文献，同步 tag usage_count 与 category paper_count"""
        paper = await self._find_paper(db, user_id, paper_id)
        if not paper:
            raise PaperNotFoundError()

        try:
            tag_service = TagService()
            category_service = CategoryService()

            # tags 变更：diff 同步 usage_count
            if tags is not None:
                old_tags = set(paper.tags or [])
                new_tags = set(tags)
                removed = list(old_tags - new_tags)
                added = list(new_tags - old_tags)
                if removed:
                    await tag_service._adjust_usage(db, user_id, removed, delta=-1)
                if added:
                    await tag_service._adjust_usage(db, user_id, added, delta=+1)
                paper.tags = list(new_tags)

            # category 变更：同步 paper_count
            if category is not None and category != paper.category:
                old_category = paper.category
                if old_category:
                    await category_service._adjust_paper_count(
                        db, user_id, old_category, delta=-1
                    )
                await category_service._adjust_paper_count(
                    db, user_id, category, delta=+1
                )
                paper.category = category

            if notes is not None:
                paper.notes = notes
            if rating is not None:
                paper.rating = rating
            if is_favorite is not None:
                paper.is_favorite = is_favorite

            await db.commit()
            await db.refresh(paper)
            return paper_to_dict(paper)
        except Exception:
            await db.rollback()
            raise

    async def delete_paper(self, db: AsyncSession, user_id: str, paper_id: str) -> None:
        """删除收藏文献，级联清理 notes/citations，回收 tag/category 计数"""
        paper = await self._find_paper(db, user_id, paper_id)
        if not paper:
            raise PaperNotFoundError()

        try:
            tag_service = TagService()
            category_service = CategoryService()

            # 1. 回收 tag usage_count
            if paper.tags:
                await tag_service._adjust_usage(db, user_id, paper.tags, delta=-1)

            # 2. 回收 category paper_count
            if paper.category:
                await category_service._adjust_paper_count(
                    db, user_id, paper.category, delta=-1
                )

            # 3. 级联删除阅读笔记
            await db.execute(
                delete(ReadingNote).where(
                    ReadingNote.user_id == user_id,
                    ReadingNote.paper_id == paper.id,
                )
            )

            # 4. 级联删除引用关系（citing 或 cited 任一匹配）
            await db.execute(
                delete(CitationRelation).where(
                    CitationRelation.user_id == user_id,
                    (CitationRelation.citing_paper_id == paper.paper_id)
                    | (CitationRelation.cited_paper_id == paper.paper_id),
                )
            )

            # 5. 删除收藏本身
            await db.execute(
                delete(PaperCollection).where(
                    PaperCollection.user_id == user_id,
                    PaperCollection.id == paper.id,
                )
            )

            await db.commit()
            logger.info(f"用户 {user_id} 删除文献: {paper.title[:50]}")
        except Exception:
            await db.rollback()
            raise

    async def _find_paper(
        self, db: AsyncSession, user_id: str, paper_id: str
    ) -> PaperCollection | None:
        """先按数据库ID查找，找不到再按外部paper_id查找"""
        result = await db.execute(
            select(PaperCollection).where(
                PaperCollection.user_id == user_id,
                PaperCollection.id == paper_id,
            )
        )
        paper = result.scalar_one_or_none()
        if paper:
            return paper

        result = await db.execute(
            select(PaperCollection).where(
                PaperCollection.user_id == user_id,
                PaperCollection.paper_id == paper_id,
            )
        )
        return result.scalar_one_or_none()


# ========== CategoryService ==========


class CategoryService:
    """分类服务 - 维护 paper_count"""

    async def create_category(
        self,
        db: AsyncSession,
        user_id: str,
        *,
        name: str,
        description: str | None = None,
        color: str = "#6366f1",
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        category = PaperCategory(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            description=description,
            color=color,
            parent_id=parent_id,
        )
        db.add(category)
        await db.commit()
        await db.refresh(category)
        return category_to_dict(category)

    async def list_categories(
        self, db: AsyncSession, user_id: str
    ) -> list[dict[str, Any]]:
        result = await db.execute(
            select(PaperCategory).where(PaperCategory.user_id == user_id)
        )
        return [category_to_dict(c) for c in result.scalars().all()]

    async def delete_category(
        self, db: AsyncSession, user_id: str, category_id: str
    ) -> None:
        """删除分类 - 把该分类下 papers 改为 uncategorized（避免孤儿数据）"""
        result = await db.execute(
            select(PaperCategory).where(
                PaperCategory.user_id == user_id,
                PaperCategory.id == category_id,
            )
        )
        category = result.scalar_one_or_none()
        if not category:
            raise CategoryNotFoundError()

        # 把该分类下的 papers 改为 uncategorized
        papers_result = await db.execute(
            select(PaperCollection).where(
                PaperCollection.user_id == user_id,
                PaperCollection.category == category.name,
            )
        )
        for p in papers_result.scalars().all():
            p.category = "uncategorized"

        await db.execute(
            delete(PaperCategory).where(
                PaperCategory.user_id == user_id,
                PaperCategory.id == category_id,
            )
        )
        await db.commit()

    async def _adjust_paper_count(
        self, db: AsyncSession, user_id: str, category_name: str | None, delta: int
    ) -> None:
        """调整分类的 paper_count
        （按 name 匹配，因为 PaperCollection.category 存的是 name；None 安全跳过）
        """
        if not category_name or category_name == "uncategorized":
            return  # uncategorized 不是真实的分类记录
        result = await db.execute(
            select(PaperCategory).where(
                PaperCategory.user_id == user_id,
                PaperCategory.name == category_name,
            )
        )
        category = result.scalar_one_or_none()
        if category:
            current = category.paper_count or 0
            category.paper_count = max(0, current + delta)


# ========== TagService ==========


class TagService:
    """标签服务 - 维护 usage_count"""

    async def create_tag(
        self,
        db: AsyncSession,
        user_id: str,
        *,
        name: str,
        color: str = "#10b981",
    ) -> dict[str, Any]:
        tag = PaperTag(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            color=color,
        )
        db.add(tag)
        await db.commit()
        await db.refresh(tag)
        return tag_to_dict(tag)

    async def list_tags(self, db: AsyncSession, user_id: str) -> list[dict[str, Any]]:
        result = await db.execute(select(PaperTag).where(PaperTag.user_id == user_id))
        return [tag_to_dict(t) for t in result.scalars().all()]

    async def delete_tag(self, db: AsyncSession, user_id: str, tag_id: str) -> None:
        """删除标签 - 从所有 papers 的 tags 列表里移除该标签"""
        result = await db.execute(
            select(PaperTag).where(
                PaperTag.user_id == user_id,
                PaperTag.id == tag_id,
            )
        )
        tag = result.scalar_one_or_none()
        if not tag:
            raise TagNotFoundError()

        # 从所有 papers 的 tags 列表里移除
        papers_result = await db.execute(
            select(PaperCollection).where(
                PaperCollection.user_id == user_id,
                PaperCollection.tags.like(f'%"{tag.name}"%'),
            )
        )
        for p in papers_result.scalars().all():
            if p.tags:
                p.tags = [t for t in p.tags if t != tag.name]

        await db.execute(
            delete(PaperTag).where(
                PaperTag.user_id == user_id,
                PaperTag.id == tag_id,
            )
        )
        await db.commit()

    async def _adjust_usage(
        self, db: AsyncSession, user_id: str, tag_names: list[str], delta: int
    ) -> None:
        """批量调整 tag usage_count（不存在则按 delta>0 创建）"""
        if not tag_names:
            return
        unique_names = list(dict.fromkeys(tag_names))  # 去重保序
        for name in unique_names:
            result = await db.execute(
                select(PaperTag).where(
                    PaperTag.user_id == user_id,
                    PaperTag.name == name,
                )
            )
            tag = result.scalar_one_or_none()
            if tag:
                current = tag.usage_count or 0
                tag.usage_count = max(0, current + delta)
            elif delta > 0:
                # 首次使用即创建：创建本身就消耗 1 次 usage（否则首个
                # 引用它的文献永远少计 1，见 fork 黄金测试 G8）
                db.add(
                    PaperTag(
                        id=str(uuid.uuid4()),
                        user_id=user_id,
                        name=name,
                        usage_count=delta,
                    )
                )


# ========== CitationService ==========


class CitationService:
    """引用关系服务 - 封装 CitationNetwork 构建"""

    async def add_citation(
        self,
        db: AsyncSession,
        user_id: str,
        *,
        citing_paper_id: str,
        cited_paper_id: str,
        citing_title: str | None = None,
        cited_title: str | None = None,
        weight: int = 1,
        source: str = "manual",
    ) -> dict[str, Any]:
        """添加引用关系，自动从 PaperCollection 回填 title"""
        # 1. 检查是否已存在
        result = await db.execute(
            select(CitationRelation).where(
                CitationRelation.user_id == user_id,
                CitationRelation.citing_paper_id == citing_paper_id,
                CitationRelation.cited_paper_id == cited_paper_id,
            )
        )
        if result.scalar_one_or_none():
            raise CitationAlreadyExistsError()

        # 2. 回填 title（如果未提供）
        if not citing_title:
            citing_title = await self._lookup_title(db, user_id, citing_paper_id)
        if not cited_title:
            cited_title = await self._lookup_title(db, user_id, cited_paper_id)

        try:
            citation = CitationRelation(
                id=str(uuid.uuid4()),
                user_id=user_id,
                citing_paper_id=citing_paper_id,
                cited_paper_id=cited_paper_id,
                citing_title=citing_title,
                cited_title=cited_title,
                weight=weight,
                source=source,
            )
            db.add(citation)
            await db.commit()
            await db.refresh(citation)
            return citation_to_dict(citation)
        except IntegrityError as e:
            # 并发场景下另一请求先插入，唯一约束兜底
            await db.rollback()
            logger.warning(
                f"用户 {user_id} 添加引用触发唯一约束: "
                f"{citing_paper_id}->{cited_paper_id}"
            )
            raise CitationAlreadyExistsError() from e
        except Exception:
            await db.rollback()
            raise

    async def add_citations_batch(
        self, db: AsyncSession, user_id: str, citations: list[dict[str, Any]]
    ) -> dict[str, int]:
        """批量添加引用关系，返回 {added, skipped}"""
        added = 0
        skipped = 0
        for cit in citations:
            result = await db.execute(
                select(CitationRelation).where(
                    CitationRelation.user_id == user_id,
                    CitationRelation.citing_paper_id == cit["citing_paper_id"],
                    CitationRelation.cited_paper_id == cit["cited_paper_id"],
                )
            )
            if result.scalar_one_or_none():
                skipped += 1
                continue

            citing_title = cit.get("citing_title")
            cited_title = cit.get("cited_title")
            if not citing_title:
                citing_title = await self._lookup_title(
                    db, user_id, cit["citing_paper_id"]
                )
            if not cited_title:
                cited_title = await self._lookup_title(
                    db, user_id, cit["cited_paper_id"]
                )

            db.add(
                CitationRelation(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    citing_paper_id=cit["citing_paper_id"],
                    cited_paper_id=cit["cited_paper_id"],
                    citing_title=citing_title,
                    cited_title=cited_title,
                    weight=cit.get("weight", 1),
                    source=cit.get("source", "manual"),
                )
            )
            added += 1

        await db.commit()
        return {"added": added, "skipped": skipped}

    async def list_citations(
        self,
        db: AsyncSession,
        user_id: str,
        *,
        paper_id: str | None = None,
        direction: str = "both",
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """获取引用关系列表"""
        query = select(CitationRelation).where(CitationRelation.user_id == user_id)

        if paper_id:
            if direction == "forward":
                query = query.where(CitationRelation.citing_paper_id == paper_id)
            elif direction == "backward":
                query = query.where(CitationRelation.cited_paper_id == paper_id)
            else:
                query = query.where(
                    (CitationRelation.citing_paper_id == paper_id)
                    | (CitationRelation.cited_paper_id == paper_id)
                )

        query = (
            query.order_by(CitationRelation.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(query)
        return [citation_to_dict(c) for c in result.scalars().all()]

    async def delete_citation(
        self, db: AsyncSession, user_id: str, citation_id: str
    ) -> None:
        result = cast(
            "CursorResult[Any]",
            await db.execute(
                delete(CitationRelation).where(
                    CitationRelation.user_id == user_id,
                    CitationRelation.id == citation_id,
                )
            ),
        )
        if result.rowcount == 0:
            raise CitationNotFoundError()
        await db.commit()

    # ----- 网络分析（统一构建 CitationNetwork） -----

    async def _build_network(self, db: AsyncSession, user_id: str) -> CitationNetwork:
        """加载用户所有 papers + citations，构建 CitationNetwork"""
        citation_result = await db.execute(
            select(CitationRelation).where(CitationRelation.user_id == user_id)
        )
        citations = citation_result.scalars().all()

        # 独立变量名：mypy 按首次绑定定型，复用 result 会把
        # papers 误推为 CitationRelation
        papers_result = await db.execute(
            select(PaperCollection).where(PaperCollection.user_id == user_id)
        )
        papers = papers_result.scalars().all()

        network = CitationNetwork()
        for p in papers:
            network.add_paper(
                {
                    "id": p.paper_id,
                    "title": p.title,
                    "authors": p.authors or [],
                    "year": p.year,
                    "journal": p.journal,
                    "citation_count": p.citation_count or 0,
                }
            )
        for c in citations:
            network.add_citation(c.citing_paper_id, c.cited_paper_id, c.weight or 1)
        return network

    async def get_graph(
        self, db: AsyncSession, user_id: str, paper_id: str, depth: int = 2
    ) -> dict[str, Any]:
        """获取引用网络图"""
        network = await self._build_network(db, user_id)
        graph_data = network.get_citation_graph(paper_id, depth)
        metrics = network.compute_metrics()
        return {
            "nodes": graph_data.get("nodes", []),
            "edges": graph_data.get("edges", []),
            "metrics": {
                "total_papers": metrics.get("total_papers", 0),
                "total_citations": metrics.get("total_citations", 0),
                "avg_citations": metrics.get("avg_citations", 0),
                "density": metrics.get("density", 0),
            },
        }

    async def co_citation(
        self, db: AsyncSession, user_id: str, min_co_citations: int = 1, top_k: int = 50
    ) -> dict[str, Any]:
        network = await self._build_network(db, user_id)
        return network.co_citation_analysis(
            min_co_citations=min_co_citations, top_k=top_k
        )

    async def influential_papers(
        self, db: AsyncSession, user_id: str, top_k: int = 10
    ) -> dict[str, Any]:
        network = await self._build_network(db, user_id)
        return {"influential_papers": network.get_influential_papers(top_k)}

    async def research_lineage(
        self, db: AsyncSession, user_id: str, paper_id: str, max_depth: int = 5
    ) -> dict[str, Any]:
        network = await self._build_network(db, user_id)
        return network.research_lineage(paper_id, max_depth)

    async def research_frontier(
        self, db: AsyncSession, user_id: str, year_from: int = 2020, top_k: int = 20
    ) -> dict[str, Any]:
        network = await self._build_network(db, user_id)
        return network.research_frontier(year_from, top_k)

    async def detect_clusters(
        self,
        db: AsyncSession,
        user_id: str,
        algorithm: str = "louvain",
        min_cluster_size: int = 3,
    ) -> dict[str, Any]:
        network = await self._build_network(db, user_id)
        return network.detect_research_clusters(algorithm, min_cluster_size)

    async def citation_timeline(
        self, db: AsyncSession, user_id: str, paper_id: str
    ) -> dict[str, Any]:
        network = await self._build_network(db, user_id)
        return network.citation_timeline(paper_id)

    async def _lookup_title(
        self, db: AsyncSession, user_id: str, paper_id: str
    ) -> str | None:
        """从 PaperCollection 查询 paper_id 对应的 title"""
        result = await db.execute(
            select(PaperCollection.title).where(
                PaperCollection.user_id == user_id,
                PaperCollection.paper_id == paper_id,
            )
        )
        return result.scalar_one_or_none()


# ========== NoteService ==========


class NoteService:
    """阅读笔记服务"""

    async def create_note(
        self,
        db: AsyncSession,
        user_id: str,
        *,
        paper_id: str,
        content: str,
        note_type: str = "general",
        page_range: str | None = None,
    ) -> dict[str, Any]:
        """创建阅读笔记 - 验证 paper 属于当前用户"""
        result = await db.execute(
            select(PaperCollection).where(
                PaperCollection.user_id == user_id,
                PaperCollection.id == paper_id,
            )
        )
        if not result.scalar_one_or_none():
            raise PaperNotFoundError()

        note = ReadingNote(
            id=str(uuid.uuid4()),
            user_id=user_id,
            paper_id=paper_id,
            content=content,
            note_type=note_type,
            page_range=page_range,
        )
        db.add(note)
        await db.commit()
        await db.refresh(note)
        return note_to_dict(note)

    async def list_notes(
        self, db: AsyncSession, user_id: str, paper_id: str
    ) -> list[dict[str, Any]]:
        result = await db.execute(
            select(ReadingNote)
            .where(
                ReadingNote.user_id == user_id,
                ReadingNote.paper_id == paper_id,
            )
            .order_by(ReadingNote.created_at.desc())
        )
        return [note_to_dict(n) for n in result.scalars().all()]

    async def update_note(
        self,
        db: AsyncSession,
        user_id: str,
        note_id: str,
        *,
        content: str | None = None,
        note_type: str | None = None,
        page_range: str | None = None,
    ) -> dict[str, Any]:
        result = await db.execute(
            select(ReadingNote).where(
                ReadingNote.user_id == user_id,
                ReadingNote.id == note_id,
            )
        )
        note = result.scalar_one_or_none()
        if not note:
            raise NoteNotFoundError()

        if content is not None:
            note.content = content
        if note_type is not None:
            note.note_type = note_type
        if page_range is not None:
            note.page_range = page_range

        await db.commit()
        await db.refresh(note)
        return note_to_dict(note)

    async def delete_note(self, db: AsyncSession, user_id: str, note_id: str) -> None:
        result = cast(
            "CursorResult[Any]",
            await db.execute(
                delete(ReadingNote).where(
                    ReadingNote.user_id == user_id,
                    ReadingNote.id == note_id,
                )
            ),
        )
        if result.rowcount == 0:
            raise NoteNotFoundError()
        await db.commit()


# ========== LibraryStatsService ==========


class LibraryStatsService:
    """文献库统计聚合"""

    async def get_stats(self, db: AsyncSession, user_id: str) -> dict[str, Any]:
        # 总文献数
        result = await db.execute(
            select(func.count(PaperCollection.id)).where(
                PaperCollection.user_id == user_id
            )
        )
        total_papers = result.scalar() or 0

        # 总分类数
        result = await db.execute(
            select(func.count(PaperCategory.id)).where(PaperCategory.user_id == user_id)
        )
        total_categories = result.scalar() or 0

        # 总标签数
        result = await db.execute(
            select(func.count(PaperTag.id)).where(PaperTag.user_id == user_id)
        )
        total_tags = result.scalar() or 0

        # 收藏数
        result = await db.execute(
            select(func.count(PaperCollection.id)).where(
                PaperCollection.user_id == user_id,
                PaperCollection.is_favorite == 1,
            )
        )
        favorite_count = result.scalar() or 0

        # 最近文献（独立变量名：mypy 按首次绑定定型，复用 result 会误推为 int）
        recent_result = await db.execute(
            select(PaperCollection)
            .where(PaperCollection.user_id == user_id)
            .order_by(PaperCollection.created_at.desc())
            .limit(5)
        )
        recent_papers = [
            {"id": p.id, "title": p.title, "year": p.year}
            for p in recent_result.scalars().all()
        ]

        # 热门分类
        categories_result = await db.execute(
            select(PaperCategory)
            .where(PaperCategory.user_id == user_id)
            .order_by(PaperCategory.paper_count.desc())
            .limit(5)
        )
        top_categories = [
            {"name": c.name, "count": c.paper_count or 0}
            for c in categories_result.scalars().all()
        ]

        # 热门标签
        tags_result = await db.execute(
            select(PaperTag)
            .where(PaperTag.user_id == user_id)
            .order_by(PaperTag.usage_count.desc())
            .limit(5)
        )
        top_tags = [
            {"name": t.name, "count": t.usage_count or 0}
            for t in tags_result.scalars().all()
        ]

        return {
            "total_papers": total_papers,
            "total_categories": total_categories,
            "total_tags": total_tags,
            "favorite_count": favorite_count,
            "recent_papers": recent_papers,
            "top_categories": top_categories,
            "top_tags": top_tags,
        }


# ========== LibraryService 门面 ==========


class LibraryService:
    """统一 LibraryService 门面 - 聚合 6 个子服务

    用法：
        svc = LibraryService()
        await svc.papers.add_paper(db, user_id, ...)
        await svc.citations.get_graph(db, user_id, paper_id, depth=2)
    """

    def __init__(self) -> None:
        self.papers = PaperService()
        self.categories = CategoryService()
        self.tags = TagService()
        self.citations = CitationService()
        self.notes = NoteService()
        self.stats = LibraryStatsService()

"""文献库模型 — SQLAlchemy 2.0 Mapped[] 风格（credibility-convergence 批次二）

列定义与原 legacy Column 等价（同名/同约束/同默认值）；
default=list：SQLAlchemy 标量 default 只在 mapper 配置时求值一次，
传 [] 会让所有新行共享同一列表对象（就地 mutate 跨行串数据）。
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class PaperCollection(Base):
    """文献收藏"""

    __tablename__ = "paper_collections"
    # 唯一约束：同一用户不能重复收藏同一外部 paper_id
    __table_args__ = (UniqueConstraint("user_id", "paper_id", name="uq_user_paper"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id"), nullable=False, index=True
    )
    paper_id: Mapped[str] = mapped_column(String, nullable=False)  # 来源ID
    title: Mapped[str] = mapped_column(String, nullable=False)
    authors: Mapped[list[str]] = mapped_column(JSON, default=list)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    journal: Mapped[str | None] = mapped_column(String, nullable=True)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    # semantic_scholar, arxiv 等
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    citation_count: Mapped[int] = mapped_column(Integer, default=0)

    # 用户标注
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)  # 标签列表
    category: Mapped[str | None] = mapped_column(
        String, default="uncategorized"
    )  # 分类
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # 笔记
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 评分 1-5
    is_favorite: Mapped[int] = mapped_column(Integer, default=0)  # 是否收藏

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )


class PaperCategory(Base):
    """文献分类"""

    __tablename__ = "paper_categories"
    # 唯一约束：同一用户下分类名唯一
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_category_name"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    color: Mapped[str | None] = mapped_column(String, default="#6366f1")  # 颜色标记
    parent_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("paper_categories.id"), nullable=True
    )  # 父分类
    paper_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PaperTag(Base):
    """文献标签"""

    __tablename__ = "paper_tags"
    # 唯一约束：同一用户下标签名唯一
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_user_tag_name"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    color: Mapped[str | None] = mapped_column(String, default="#10b981")
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CitationRelation(Base):
    """引用关系"""

    __tablename__ = "citation_relations"
    # 唯一约束：同一用户下同一引用关系不能重复
    __table_args__ = (
        UniqueConstraint(
            "user_id", "citing_paper_id", "cited_paper_id", name="uq_user_citation"
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id"), nullable=False, index=True
    )
    citing_paper_id: Mapped[str] = mapped_column(
        String, nullable=False, index=True
    )  # 引用方论文ID
    cited_paper_id: Mapped[str] = mapped_column(
        String, nullable=False, index=True
    )  # 被引方论文ID
    citing_title: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # 引用方标题（冗余，方便查询）
    cited_title: Mapped[str | None] = mapped_column(String, nullable=True)  # 被引方标题
    weight: Mapped[int] = mapped_column(Integer, default=1)  # 关系权重
    source: Mapped[str | None] = mapped_column(
        String, default="manual"
    )  # manual, semantic_scholar, auto
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ReadingNote(Base):
    """阅读笔记"""

    __tablename__ = "reading_notes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id"), nullable=False, index=True
    )
    paper_id: Mapped[str] = mapped_column(
        String, ForeignKey("paper_collections.id"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    note_type: Mapped[str | None] = mapped_column(
        String, default="general"
    )  # general, insight, method, question
    page_range: Mapped[str | None] = mapped_column(String, nullable=True)  # 页码范围
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

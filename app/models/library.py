from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.core.database import Base


class PaperCollection(Base):
    """文献收藏"""

    __tablename__ = "paper_collections"
    # 唯一约束：同一用户不能重复收藏同一外部 paper_id
    __table_args__ = (UniqueConstraint("user_id", "paper_id", name="uq_user_paper"),)

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    paper_id = Column(String, nullable=False)  # 来源ID
    title = Column(String, nullable=False)
    authors = Column(JSON, default=[])
    abstract = Column(Text)
    year = Column(Integer)
    journal = Column(String)
    url = Column(String)
    source = Column(String)  # semantic_scholar, arxiv等
    citation_count = Column(Integer, default=0)

    # 用户标注
    tags = Column(JSON, default=[])  # 标签列表
    category = Column(String, default="uncategorized")  # 分类
    notes = Column(Text)  # 笔记
    rating = Column(Integer)  # 评分 1-5
    is_favorite = Column(Integer, default=0)  # 是否收藏

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PaperCategory(Base):
    """文献分类"""

    __tablename__ = "paper_categories"
    # 唯一约束：同一用户下分类名唯一
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_category_name"),
    )

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(String)
    color = Column(String, default="#6366f1")  # 颜色标记
    parent_id = Column(String, ForeignKey("paper_categories.id"))  # 父分类
    paper_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PaperTag(Base):
    """文献标签"""

    __tablename__ = "paper_tags"
    # 唯一约束：同一用户下标签名唯一
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_user_tag_name"),)

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    color = Column(String, default="#10b981")
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CitationRelation(Base):
    """引用关系"""

    __tablename__ = "citation_relations"
    # 唯一约束：同一用户下同一引用关系不能重复
    __table_args__ = (
        UniqueConstraint(
            "user_id", "citing_paper_id", "cited_paper_id", name="uq_user_citation"
        ),
    )

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    citing_paper_id = Column(String, nullable=False, index=True)  # 引用方论文ID
    cited_paper_id = Column(String, nullable=False, index=True)  # 被引方论文ID
    citing_title = Column(String)  # 引用方标题（冗余，方便查询）
    cited_title = Column(String)  # 被引方标题
    weight = Column(Integer, default=1)  # 关系权重
    source = Column(String, default="manual")  # manual, semantic_scholar, auto
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ReadingNote(Base):
    """阅读笔记"""

    __tablename__ = "reading_notes"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    paper_id = Column(
        String, ForeignKey("paper_collections.id"), nullable=False, index=True
    )
    content = Column(Text, nullable=False)
    note_type = Column(String, default="general")  # general, insight, method, question
    page_range = Column(String)  # 页码范围
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

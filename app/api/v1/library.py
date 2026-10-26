from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services.library_service import (
    CategoryNotFoundError,
    CitationAlreadyExistsError,
    CitationNotFoundError,
    LibraryError,
    LibraryService,
    NoteNotFoundError,
    PaperAlreadyExistsError,
    PaperNotFoundError,
    TagNotFoundError,
)
from app.utils.logger import get_logger

logger = get_logger("api.library")
router = APIRouter()
library_service = LibraryService()


# ========== 请求模型 ==========


class PaperAddRequest(BaseModel):
    paper_id: str = Field(..., description="文献ID")
    title: str = Field(..., description="标题")
    authors: list[str] = Field(default=[], description="作者列表")
    abstract: str | None = Field(default=None, description="摘要")
    year: int | None = Field(default=None, description="年份")
    journal: str | None = Field(default=None, description="期刊")
    url: str | None = Field(default=None, description="链接")
    source: str | None = Field(default=None, description="来源")
    tags: list[str] = Field(default=[], description="标签")
    category: str | None = Field(default=None, description="分类")
    notes: str | None = Field(default=None, description="笔记")


class PaperUpdateRequest(BaseModel):
    tags: list[str] | None = None
    category: str | None = None
    notes: str | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    is_favorite: int | None = Field(default=None, ge=0, le=1)


class CategoryCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="分类名称")
    description: str | None = Field(default=None, description="描述")
    color: str = Field(default="#6366f1", description="颜色")
    parent_id: str | None = Field(default=None, description="父分类ID")


class TagCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=30, description="标签名称")
    color: str = Field(default="#10b981", description="颜色")


# ========== 响应模型 ==========


class PaperResponse(BaseModel):
    id: str
    paper_id: str
    title: str
    authors: list[str]
    abstract: str | None
    year: int | None
    journal: str | None
    url: str | None
    source: str | None
    tags: list[str]
    category: str | None
    notes: str | None
    rating: int | None
    is_favorite: int
    created_at: str | None

    model_config = ConfigDict(from_attributes=True)


class CategoryResponse(BaseModel):
    id: str
    name: str
    description: str | None
    color: str
    parent_id: str | None
    paper_count: int

    model_config = ConfigDict(from_attributes=True)


class TagResponse(BaseModel):
    id: str
    name: str
    color: str
    usage_count: int

    model_config = ConfigDict(from_attributes=True)


class LibraryStatsResponse(BaseModel):
    total_papers: int
    total_categories: int
    total_tags: int
    favorite_count: int
    recent_papers: list[dict[str, Any]]
    top_categories: list[dict[str, Any]]
    top_tags: list[dict[str, Any]]


# ========== 异常映射辅助 ==========


def _map_library_error(exc: LibraryError) -> HTTPException:
    """把服务层异常映射为 HTTPException"""
    return HTTPException(status_code=exc.status_code, detail=exc.message)


# ========== 文献收藏端点 ==========


@router.post("/papers", response_model=PaperResponse)
async def add_paper(
    request: PaperAddRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaperResponse:
    """添加文献到收藏"""
    try:
        data = await library_service.papers.add_paper(
            db,
            current_user.id,
            paper_id=request.paper_id,
            title=request.title,
            authors=request.authors,
            abstract=request.abstract,
            year=request.year,
            journal=request.journal,
            url=request.url,
            source=request.source,
            tags=request.tags,
            category=request.category,
            notes=request.notes,
        )
        return PaperResponse(**data)
    except PaperAlreadyExistsError as e:
        raise _map_library_error(e)


@router.get("/papers", response_model=list[PaperResponse])
async def list_papers(
    category: str | None = Query(default=None, description="按分类筛选"),
    tag: str | None = Query(default=None, description="按标签筛选"),
    favorite: int | None = Query(default=None, description="按收藏筛选"),
    search: str | None = Query(default=None, description="搜索关键词"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PaperResponse]:
    """获取收藏文献列表"""
    items = await library_service.papers.list_papers(
        db,
        current_user.id,
        category=category,
        tag=tag,
        favorite=favorite,
        search=search,
        limit=limit,
        offset=offset,
    )
    return [PaperResponse(**d) for d in items]


@router.get("/papers/{paper_id}", response_model=PaperResponse)
async def get_paper(
    paper_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaperResponse:
    """获取单个收藏文献 - paper_id 可以是数据库ID或外部paper_id"""
    try:
        data = await library_service.papers.get_paper(db, current_user.id, paper_id)
        return PaperResponse(**data)
    except PaperNotFoundError as e:
        raise _map_library_error(e)


@router.put("/papers/{paper_id}", response_model=PaperResponse)
async def update_paper(
    paper_id: str,
    request: PaperUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaperResponse:
    """更新收藏文献 - paper_id 可以是数据库ID或外部paper_id"""
    try:
        data = await library_service.papers.update_paper(
            db,
            current_user.id,
            paper_id,
            tags=request.tags,
            category=request.category,
            notes=request.notes,
            rating=request.rating,
            is_favorite=request.is_favorite,
        )
        return PaperResponse(**data)
    except PaperNotFoundError as e:
        raise _map_library_error(e)


@router.delete("/papers/{paper_id}")
async def delete_paper(
    paper_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """删除收藏文献 - paper_id 可以是数据库ID或外部paper_id"""
    try:
        await library_service.papers.delete_paper(db, current_user.id, paper_id)
        return {"status": "success", "message": "已删除"}
    except PaperNotFoundError as e:
        raise _map_library_error(e)


# ========== 分类端点 ==========


@router.post("/categories", response_model=CategoryResponse)
async def create_category(
    request: CategoryCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CategoryResponse:
    """创建分类"""
    data = await library_service.categories.create_category(
        db,
        current_user.id,
        name=request.name,
        description=request.description,
        color=request.color,
        parent_id=request.parent_id,
    )
    return CategoryResponse(**data)


@router.get("/categories", response_model=list[CategoryResponse])
async def list_categories(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[CategoryResponse]:
    """获取分类列表"""
    items = await library_service.categories.list_categories(db, current_user.id)
    return [CategoryResponse(**d) for d in items]


@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """删除分类（该分类下 papers 自动改为 uncategorized）"""
    try:
        await library_service.categories.delete_category(
            db, current_user.id, category_id
        )
        return {"status": "success", "message": "已删除"}
    except CategoryNotFoundError as e:
        raise _map_library_error(e)


# ========== 标签端点 ==========


@router.post("/tags", response_model=TagResponse)
async def create_tag(
    request: TagCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TagResponse:
    """创建标签"""
    data = await library_service.tags.create_tag(
        db, current_user.id, name=request.name, color=request.color
    )
    return TagResponse(**data)


@router.get("/tags", response_model=list[TagResponse])
async def list_tags(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[TagResponse]:
    """获取标签列表"""
    items = await library_service.tags.list_tags(db, current_user.id)
    return [TagResponse(**d) for d in items]


@router.delete("/tags/{tag_id}")
async def delete_tag(
    tag_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """删除标签（自动从所有 papers 的 tags 列表移除）"""
    try:
        await library_service.tags.delete_tag(db, current_user.id, tag_id)
        return {"status": "success", "message": "已删除"}
    except TagNotFoundError as e:
        raise _map_library_error(e)


# ========== 统计端点 ==========


@router.get("/stats", response_model=LibraryStatsResponse)
async def get_library_stats(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> LibraryStatsResponse:
    """获取文献库统计"""
    data = await library_service.stats.get_stats(db, current_user.id)
    return LibraryStatsResponse(**data)


# ========== 引用网络端点 ==========


class CitationAddRequest(BaseModel):
    citing_paper_id: str = Field(..., description="引用方论文ID")
    cited_paper_id: str = Field(..., description="被引方论文ID")
    citing_title: str | None = Field(default=None, description="引用方标题")
    cited_title: str | None = Field(default=None, description="被引方标题")
    weight: int = Field(default=1, description="关系权重")
    source: str = Field(
        default="manual", description="来源: manual/semantic_scholar/auto"
    )


class CitationBatchRequest(BaseModel):
    citations: list[CitationAddRequest] = Field(..., description="批量引用关系")


class CitationGraphRequest(BaseModel):
    paper_id: str = Field(..., description="中心论文ID")
    depth: int = Field(default=2, ge=1, le=5, description="展开深度")


class CoCitationRequest(BaseModel):
    min_co_citations: int = Field(default=1, ge=1, description="最小共被引次数")
    top_k: int = Field(default=50, ge=1, le=200, description="返回数量")


class CitationResponse(BaseModel):
    id: str
    citing_paper_id: str
    cited_paper_id: str
    citing_title: str | None
    cited_title: str | None
    weight: int
    source: str
    created_at: str | None

    model_config = ConfigDict(from_attributes=True)


class NetworkGraphResponse(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    metrics: dict[str, Any] | None = None


@router.post("/citations", response_model=CitationResponse)
async def add_citation(
    request: CitationAddRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CitationResponse:
    """添加引用关系（自动回填 citing/cited_title）"""
    try:
        data = await library_service.citations.add_citation(
            db,
            current_user.id,
            citing_paper_id=request.citing_paper_id,
            cited_paper_id=request.cited_paper_id,
            citing_title=request.citing_title,
            cited_title=request.cited_title,
            weight=request.weight,
            source=request.source,
        )
        return CitationResponse(**data)
    except CitationAlreadyExistsError as e:
        raise _map_library_error(e)


@router.post("/citations/batch")
async def add_citations_batch(
    request: CitationBatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """批量添加引用关系"""
    citations = [c.model_dump() for c in request.citations]
    return await library_service.citations.add_citations_batch(
        db, current_user.id, citations
    )


@router.get("/citations", response_model=list[CitationResponse])
async def list_citations(
    paper_id: str | None = Query(default=None, description="按论文ID筛选"),
    direction: str = Query(default="both", description="方向: forward/backward/both"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CitationResponse]:
    """获取引用关系列表"""
    items = await library_service.citations.list_citations(
        db,
        current_user.id,
        paper_id=paper_id,
        direction=direction,
        limit=limit,
        offset=offset,
    )
    return [CitationResponse(**d) for d in items]


@router.delete("/citations/{citation_id}")
async def delete_citation(
    citation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """删除引用关系"""
    try:
        await library_service.citations.delete_citation(
            db, current_user.id, citation_id
        )
        return {"status": "success", "message": "已删除"}
    except CitationNotFoundError as e:
        raise _map_library_error(e)


@router.post("/citations/network/graph", response_model=NetworkGraphResponse)
async def get_citation_graph(
    request: CitationGraphRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NetworkGraphResponse:
    """获取引用网络图"""
    data = await library_service.citations.get_graph(
        db, current_user.id, request.paper_id, request.depth
    )
    return NetworkGraphResponse(**data)


@router.post("/citations/network/co-citation")
async def co_citation_analysis(
    request: CoCitationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """共被引分析"""
    return await library_service.citations.co_citation(
        db,
        current_user.id,
        min_co_citations=request.min_co_citations,
        top_k=request.top_k,
    )


@router.post("/citations/network/influential")
async def get_influential_papers(
    top_k: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """获取高影响力论文（基于PageRank）"""
    return await library_service.citations.influential_papers(
        db, current_user.id, top_k
    )


@router.post("/citations/network/lineage")
async def get_research_lineage(
    paper_id: str = Query(..., description="论文ID"),
    max_depth: int = Query(default=5, ge=1, le=10),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """获取研究脉络（追溯学术传承）"""
    return await library_service.citations.research_lineage(
        db, current_user.id, paper_id, max_depth
    )


@router.post("/citations/network/frontier")
async def get_research_frontier(
    year_from: int = Query(default=2020, description="起始年份"),
    top_k: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """识别研究前沿"""
    return await library_service.citations.research_frontier(
        db, current_user.id, year_from, top_k
    )


@router.post("/citations/network/clusters")
async def detect_research_clusters(
    algorithm: str = Query(default="louvain", description="算法: louvain/simple"),
    min_cluster_size: int = Query(default=3, ge=2, le=20),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """检测研究聚类/社区"""
    return await library_service.citations.detect_clusters(
        db, current_user.id, algorithm, min_cluster_size
    )


@router.get("/citations/network/timeline/{paper_id}")
async def get_citation_timeline(
    paper_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """获取论文引用时间线"""
    return await library_service.citations.citation_timeline(
        db, current_user.id, paper_id
    )


# ========== 阅读笔记端点 ==========


class NoteCreateRequest(BaseModel):
    paper_id: str = Field(..., description="论文收藏ID")
    content: str = Field(..., min_length=1, description="笔记内容")
    note_type: str = Field(
        default="general", description="类型: general/insight/method/question"
    )
    page_range: str | None = Field(default=None, description="页码范围")


class NoteUpdateRequest(BaseModel):
    content: str | None = Field(default=None, min_length=1)
    note_type: str | None = Field(default=None)
    page_range: str | None = Field(default=None)


class NoteResponse(BaseModel):
    id: str
    paper_id: str
    content: str
    note_type: str
    page_range: str | None
    created_at: str | None
    updated_at: str | None

    model_config = ConfigDict(from_attributes=True)


@router.post("/notes", response_model=NoteResponse)
async def create_note(
    request: NoteCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteResponse:
    """创建阅读笔记"""
    try:
        data = await library_service.notes.create_note(
            db,
            current_user.id,
            paper_id=request.paper_id,
            content=request.content,
            note_type=request.note_type,
            page_range=request.page_range,
        )
        return NoteResponse(**data)
    except PaperNotFoundError as e:
        raise _map_library_error(e)


@router.get("/notes/{paper_id}", response_model=list[NoteResponse])
async def list_notes(
    paper_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[NoteResponse]:
    """获取论文阅读笔记"""
    items = await library_service.notes.list_notes(db, current_user.id, paper_id)
    return [NoteResponse(**d) for d in items]


@router.put("/notes/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: str,
    request: NoteUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteResponse:
    """更新阅读笔记"""
    try:
        data = await library_service.notes.update_note(
            db,
            current_user.id,
            note_id,
            content=request.content,
            note_type=request.note_type,
            page_range=request.page_range,
        )
        return NoteResponse(**data)
    except NoteNotFoundError as e:
        raise _map_library_error(e)


@router.delete("/notes/{note_id}")
async def delete_note(
    note_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """删除阅读笔记"""
    try:
        await library_service.notes.delete_note(db, current_user.id, note_id)
        return {"status": "success", "message": "已删除"}
    except NoteNotFoundError as e:
        raise _map_library_error(e)

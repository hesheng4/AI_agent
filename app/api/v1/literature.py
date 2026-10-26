from typing import Any

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel, Field

from app.agents.literature import get_literature_agent
from app.agents.literature.citation import CitationAnalyzer
from app.api.deps import get_current_user
from app.config import get_settings
from app.models.user import User
from app.utils.logger import get_logger

logger = get_logger("api.literature")
router = APIRouter()
settings = get_settings()


# 请求模型
class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="搜索关键词")
    filters: dict[str, Any] = Field(default_factory=dict, description="过滤条件")


class ReadRequest(BaseModel):
    content: str = Field(
        ...,
        min_length=50,
        max_length=settings.MAX_CONTENT_LENGTH,
        description="文献内容",
    )


class PaperItem(BaseModel):
    """单篇文献的请求体模型（用于 SummarizeRequest.papers 字段）

    命名说明：以 Item 后缀表示集合中的元素项，区别于顶层 *Response 响应模型。
    """

    title: str = Field(..., description="文献标题")
    abstract: str = Field(..., description="文献摘要")


class SummarizeRequest(BaseModel):
    papers: list[PaperItem] = Field(..., min_length=1, description="文献列表")


# 响应模型
class SearchResponse(BaseModel):
    status: str
    papers: list[dict[str, Any]]
    suggestions: str
    total_results: int


class ReadResponse(BaseModel):
    status: str
    analysis: str
    key_points: list[str]


class SummarizeResponse(BaseModel):
    status: str
    summaries: list[dict[str, str]]
    review: str
    total_processed: int


@router.post("/search", response_model=SearchResponse)
async def search_literature(
    request: SearchRequest, current_user: User = Depends(get_current_user)
) -> SearchResponse:
    """文献搜索"""
    logger.info(f"用户 {current_user.id} 搜索文献: {request.query}")

    agent = get_literature_agent()
    result = await agent.process(
        {"task": "search", "query": request.query, "filters": request.filters}
    )

    return SearchResponse(**result)


@router.post("/read", response_model=ReadResponse)
async def read_literature(
    request: ReadRequest, current_user: User = Depends(get_current_user)
) -> ReadResponse:
    """文献阅读分析"""
    logger.info(f"用户 {current_user.id} 分析文献")

    agent = get_literature_agent()
    result = await agent.process({"task": "read", "content": request.content})

    return ReadResponse(**result)


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize_literature(
    request: SummarizeRequest, current_user: User = Depends(get_current_user)
) -> SummarizeResponse:
    """文献总结"""
    logger.info(f"用户 {current_user.id} 总结 {len(request.papers)} 篇文献")

    agent = get_literature_agent()
    result = await agent.process(
        {"task": "summarize", "papers": [p.model_dump() for p in request.papers]}
    )

    return SummarizeResponse(**result)


# ========== 引用分析端点 ==========


class CitationNetworkResponse(BaseModel):
    status: str
    center: str
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    stats: dict[str, int]


class CoCitationResponse(BaseModel):
    status: str
    papers_analyzed: int
    co_citations: list[dict[str, Any]]
    total_pairs: int


class CitationTrendResponse(BaseModel):
    status: str
    paper_id: str
    total_citations: int
    trend: list[dict[str, Any]]
    peak_year: int | None


@router.get("/citations/{paper_id}")
async def get_citations(
    paper_id: str,
    limit: int = Query(default=50, le=200),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取引用该论文的文献"""
    logger.info(f"用户 {current_user.id} 获取引用: {paper_id}")

    citations = await CitationAnalyzer.get_citations(paper_id, limit=limit)

    return {
        "status": "success",
        "paper_id": paper_id,
        "citations": citations,
        "total": len(citations),
    }


@router.get("/references/{paper_id}")
async def get_references(
    paper_id: str,
    limit: int = Query(default=50, le=200),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取该论文的参考文献"""
    logger.info(f"用户 {current_user.id} 获取参考文献: {paper_id}")

    references = await CitationAnalyzer.get_references(paper_id, limit=limit)

    return {
        "status": "success",
        "paper_id": paper_id,
        "references": references,
        "total": len(references),
    }


@router.get("/citation-network/{paper_id}", response_model=CitationNetworkResponse)
async def get_citation_network(
    paper_id: str,
    depth: int = Query(default=1, le=2),
    current_user: User = Depends(get_current_user),
) -> CitationNetworkResponse:
    """构建引用网络"""
    logger.info(f"用户 {current_user.id} 构建引用网络: {paper_id}")

    network = await CitationAnalyzer.build_citation_network(paper_id, depth=depth)

    return CitationNetworkResponse(status="success", **network)


@router.post("/co-citations", response_model=CoCitationResponse)
async def find_co_citations(
    paper_ids: list[str] = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
) -> CoCitationResponse:
    """查找共被引关系"""
    logger.info(f"用户 {current_user.id} 查找共被引: {len(paper_ids)} 篇")

    result = await CitationAnalyzer.find_co_citations(paper_ids)

    return CoCitationResponse(status="success", **result)


@router.get("/citation-trend/{paper_id}", response_model=CitationTrendResponse)
async def get_citation_trend(
    paper_id: str, current_user: User = Depends(get_current_user)
) -> CitationTrendResponse:
    """获取引用趋势"""
    logger.info(f"用户 {current_user.id} 获取引用趋势: {paper_id}")

    result = await CitationAnalyzer.get_citation_trend(paper_id)

    return CitationTrendResponse(status="success", **result)


# ========== 引用网络高级分析端点
# （基于 CitationNetwork.build_from_references） ==========


class CitationGraphRequest(BaseModel):
    papers: list[dict[str, Any]] = Field(
        ..., min_length=1, description="论文列表（含references字段）"
    )
    paper_id: str = Field(..., description="中心论文ID")
    depth: int = Field(default=2, ge=1, le=5, description="展开深度")


class CoCitationAnalysisRequest(BaseModel):
    papers: list[dict[str, Any]] = Field(
        ..., min_length=1, description="论文列表（含references字段）"
    )
    min_co_citations: int = Field(default=1, ge=1, description="最小共被引次数")
    top_k: int = Field(default=50, ge=1, le=500, description="返回前K对")


class BibliographicCouplingRequest(BaseModel):
    papers: list[dict[str, Any]] = Field(
        ..., min_length=1, description="论文列表（含references字段）"
    )
    min_coupling: int = Field(default=1, ge=1, description="最小耦合强度")
    top_k: int = Field(default=50, ge=1, le=500, description="返回前K对")


class ResearchClustersRequest(BaseModel):
    papers: list[dict[str, Any]] = Field(
        ..., min_length=1, description="论文列表（含references字段）"
    )
    algorithm: str = Field(default="louvain", description="聚类算法：louvain 或 simple")
    min_cluster_size: int = Field(default=3, ge=1, description="最小聚类大小")


class ResearchFrontierRequest(BaseModel):
    papers: list[dict[str, Any]] = Field(
        ..., min_length=1, description="论文列表（含references字段）"
    )
    year_from: int = Field(default=2020, description="起始年份")
    top_k: int = Field(default=20, ge=1, le=200, description="返回前K篇")


class ResearchLineageRequest(BaseModel):
    papers: list[dict[str, Any]] = Field(
        ..., min_length=1, description="论文列表（含references字段）"
    )
    paper_id: str = Field(..., description="起始论文ID")
    max_depth: int = Field(default=5, ge=1, le=20, description="最大追溯深度")


class KnowledgeDiffusionRequest(BaseModel):
    papers: list[dict[str, Any]] = Field(
        ..., min_length=1, description="论文列表（含references字段）"
    )
    paper_id: str = Field(..., description="起源论文ID")
    max_depth: int = Field(default=3, ge=1, le=10, description="最大扩散深度")


class CitationTimelineRequest(BaseModel):
    papers: list[dict[str, Any]] = Field(
        ..., min_length=1, description="论文列表（含references字段）"
    )
    paper_id: str = Field(..., description="目标论文ID")


class InfluentialPapersRequest(BaseModel):
    papers: list[dict[str, Any]] = Field(
        ..., min_length=1, description="论文列表（含references字段）"
    )
    top_k: int = Field(default=10, ge=1, le=200, description="返回前K篇")


@router.post("/citation-graph")
async def build_citation_graph(
    request: CitationGraphRequest, current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """构建指定论文的引用关系图（BFS展开，含图表配置）"""
    logger.info(
        f"用户 {current_user.id} 构建引用图: {request.paper_id}, depth={request.depth}"
    )

    agent = get_literature_agent()
    return await agent.process(
        {
            "task": "citation_network",
            "analysis": "graph",
            "papers": request.papers,
            "paper_id": request.paper_id,
            "depth": request.depth,
        }
    )


@router.post("/co-citation")
async def co_citation_analysis(
    request: CoCitationAnalysisRequest, current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """共被引分析：发现经常被一起引用的论文对"""
    logger.info(f"用户 {current_user.id} 共被引分析: {len(request.papers)} 篇")

    agent = get_literature_agent()
    return await agent.process(
        {
            "task": "citation_network",
            "analysis": "co_citation",
            "papers": request.papers,
            "min_co_citations": request.min_co_citations,
            "top_k": request.top_k,
        }
    )


@router.post("/bibliographic-coupling")
async def bibliographic_coupling(
    request: BibliographicCouplingRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """文献耦合分析：发现引用相同参考文献的论文对"""
    logger.info(f"用户 {current_user.id} 文献耦合分析: {len(request.papers)} 篇")

    agent = get_literature_agent()
    return await agent.process(
        {
            "task": "citation_network",
            "analysis": "coupling",
            "papers": request.papers,
            "min_coupling": request.min_coupling,
            "top_k": request.top_k,
        }
    )


@router.post("/research-clusters")
async def research_clusters(
    request: ResearchClustersRequest, current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """研究聚类/社区检测：发现研究主题分组"""
    logger.info(
        f"用户 {current_user.id} 研究聚类: {len(request.papers)} 篇, "
        f"algo={request.algorithm}"
    )

    agent = get_literature_agent()
    return await agent.process(
        {
            "task": "citation_network",
            "analysis": "clusters",
            "papers": request.papers,
            "algorithm": request.algorithm,
            "min_cluster_size": request.min_cluster_size,
        }
    )


@router.post("/research-frontier")
async def research_frontier(
    request: ResearchFrontierRequest, current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """研究前沿识别：近年高影响力论文与新兴主题"""
    logger.info(f"用户 {current_user.id} 研究前沿: year_from={request.year_from}")

    agent = get_literature_agent()
    return await agent.process(
        {
            "task": "citation_network",
            "analysis": "frontier",
            "papers": request.papers,
            "year_from": request.year_from,
            "top_k": request.top_k,
        }
    )


@router.post("/research-lineage")
async def research_lineage(
    request: ResearchLineageRequest, current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """研究脉络追溯：从一篇论文回溯到学术根源"""
    logger.info(f"用户 {current_user.id} 研究脉络: {request.paper_id}")

    agent = get_literature_agent()
    return await agent.process(
        {
            "task": "citation_network",
            "analysis": "lineage",
            "papers": request.papers,
            "paper_id": request.paper_id,
            "max_depth": request.max_depth,
        }
    )


@router.post("/knowledge-diffusion")
async def knowledge_diffusion(
    request: KnowledgeDiffusionRequest, current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """知识扩散分析：追踪论文影响力的传播路径"""
    logger.info(f"用户 {current_user.id} 知识扩散: {request.paper_id}")

    agent = get_literature_agent()
    return await agent.process(
        {
            "task": "citation_network",
            "analysis": "diffusion",
            "papers": request.papers,
            "paper_id": request.paper_id,
            "max_depth": request.max_depth,
        }
    )


@router.post("/citation-timeline")
async def citation_timeline(
    request: CitationTimelineRequest, current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """引用时间线：按年份统计被引趋势"""
    logger.info(f"用户 {current_user.id} 引用时间线: {request.paper_id}")

    agent = get_literature_agent()
    return await agent.process(
        {
            "task": "citation_network",
            "analysis": "timeline",
            "papers": request.papers,
            "paper_id": request.paper_id,
        }
    )


@router.post("/influential-papers")
async def influential_papers(
    request: InfluentialPapersRequest, current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """高影响力论文识别（基于PageRank）"""
    logger.info(f"用户 {current_user.id} 高影响力论文: top_k={request.top_k}")

    agent = get_literature_agent()
    return await agent.process(
        {
            "task": "citation_network",
            "analysis": "influential",
            "papers": request.papers,
            "top_k": request.top_k,
        }
    )

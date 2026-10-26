import asyncio
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from app.core.vector_store import get_vector_store
from app.utils.embedding import get_embedding_client
from app.utils.exceptions import ToolException
from app.utils.logger import get_logger

logger = get_logger("tools.literature")

# API配置
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"
ARXIV_API = "https://export.arxiv.org/api/query"

# 请求超时
TIMEOUT = 30.0

# 模块级复用的 httpx 客户端，避免每次请求重建连接池
# limits 控制连接复用，headers 加 User-Agent 避免被部分 API 拒绝
_HTTP_CLIENT: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    """懒初始化并复用全局 httpx 客户端"""
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None or _HTTP_CLIENT.is_closed:
        _HTTP_CLIENT = httpx.AsyncClient(
            timeout=TIMEOUT,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            headers={"User-Agent": "ResearchAgentPlatform/1.0"},
        )
    return _HTTP_CLIENT


async def close_http_client() -> None:
    """应用关闭时调用，释放连接池"""
    global _HTTP_CLIENT
    if _HTTP_CLIENT is not None and not _HTTP_CLIENT.is_closed:
        await _HTTP_CLIENT.aclose()
    _HTTP_CLIENT = None


# arXiv Atom 命名空间
_ATOM_NS = "{http://www.w3.org/2005/Atom}"


def _parse_arxiv_response(content: str, limit: int) -> list[dict[str, Any]]:
    """用 ElementTree 解析 arXiv Atom XML，比正则更稳健"""
    papers: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        logger.warning(f"arXiv XML 解析失败: {e}")
        return papers

    for entry in root.findall(f"{_ATOM_NS}entry")[:limit]:

        def _text(tag: str) -> str:
            node = entry.find(f"{_ATOM_NS}{tag}")
            return node.text.strip() if node is not None and node.text else ""

        title = _text("title").replace("\n", " ")
        abstract = _text("summary").replace("\n", " ")
        published = _text("published")
        raw_id = _text("id")
        arxiv_id = raw_id.split("/")[-1] if raw_id else ""

        authors = [
            n.text.strip()
            for n in entry.findall(f"{_ATOM_NS}author/{_ATOM_NS}name")
            if n.text
        ]

        papers.append(
            {
                "id": arxiv_id,
                "title": title,
                "authors": authors,
                "abstract": abstract,
                "year": int(published[:4]) if published[:4].isdigit() else None,
                "journal": "arXiv",
                "citation_count": 0,
                "url": raw_id,
                "source": "arxiv",
            }
        )
    return papers


# 向量集合名称
PAPERS_COLLECTION = "papers"


class LiteratureTools:
    """文献工具集"""

    @staticmethod
    async def search_papers(
        query: str, filters: dict[str, Any] | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """搜索文献 - 使用Semantic Scholar API"""
        logger.info(f"搜索文献: {query}, limit={limit}")

        try:
            # 优先使用Semantic Scholar
            papers = await LiteratureTools._search_semantic_scholar(query, limit)
            if papers:
                return papers

            # 备选：arXiv
            logger.info("Semantic Scholar无结果，尝试arXiv")
            return await LiteratureTools._search_arxiv(query, limit)

        except Exception as e:
            logger.error(f"文献搜索失败: {e}", exc_info=True)
            raise ToolException(f"文献搜索失败: {str(e)}", tool_name="search_papers")

    @staticmethod
    async def _search_semantic_scholar(query: str, limit: int) -> list[dict[str, Any]]:
        """Semantic Scholar搜索"""
        url = f"{SEMANTIC_SCHOLAR_API}/paper/search"
        params: dict[str, Any] = {
            "query": query,
            "limit": limit,
            "fields": "title,authors,abstract,year,journal,citationCount,url",
        }

        try:
            client = _get_http_client()
            response = await client.get(url, params=params)

            if response.status_code == 429:
                logger.warning("Semantic Scholar限流，稍后重试")
                await asyncio.sleep(2)
                response = await client.get(url, params=params)

            if response.status_code != 200:
                logger.warning(f"Semantic Scholar返回 {response.status_code}")
                return []

            data = response.json()
            papers = []

            for item in data.get("data", []):
                papers.append(
                    {
                        "id": item.get("paperId", ""),
                        "title": item.get("title", ""),
                        "authors": [a.get("name", "") for a in item.get("authors", [])],
                        "abstract": item.get("abstract", ""),
                        "year": item.get("year"),
                        "journal": (
                            item.get("journal", {}).get("name", "")
                            if item.get("journal")
                            else ""
                        ),
                        "citation_count": item.get("citationCount", 0),
                        "url": item.get("url", ""),
                        "source": "semantic_scholar",
                    }
                )

            logger.info(f"Semantic Scholar返回 {len(papers)} 篇文献")
            return papers
        except Exception as e:
            logger.error(f"Semantic Scholar请求失败: {e}")
            return []

    @staticmethod
    async def _search_arxiv(query: str, limit: int) -> list[dict[str, Any]]:
        """arXiv搜索"""
        params: dict[str, Any] = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": limit,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }

        client = _get_http_client()
        response = await client.get(ARXIV_API, params=params)

        if response.status_code != 200:
            logger.warning(f"arXiv返回 {response.status_code}")
            return []

        papers = _parse_arxiv_response(response.text, limit)
        logger.info(f"arXiv返回 {len(papers)} 篇文献")
        return papers

    @staticmethod
    async def get_paper_details(
        paper_id: str, source: str = "semantic_scholar"
    ) -> dict[str, Any]:
        """获取文献详情"""
        logger.info(f"获取文献详情: {paper_id}")

        if source == "semantic_scholar":
            url = f"{SEMANTIC_SCHOLAR_API}/paper/{paper_id}"
            params = {
                "fields": (
                    "title,authors,abstract,year,journal,citationCount,"
                    "references,tldr,url"
                )
            }

            client = _get_http_client()
            response = await client.get(url, params=params)

            if response.status_code != 200:
                raise ToolException(
                    f"获取文献失败: {response.status_code}",
                    tool_name="get_paper_details",
                )

            data = response.json()
            return {
                "id": data.get("paperId"),
                "title": data.get("title"),
                "authors": [a.get("name") for a in data.get("authors", [])],
                "abstract": data.get("abstract"),
                "year": data.get("year"),
                "journal": (
                    data.get("journal", {}).get("name") if data.get("journal") else None
                ),
                "citation_count": data.get("citationCount", 0),
                "references": [
                    r.get("paperId") for r in data.get("references", [])[:10]
                ],
                "tldr": data.get("tldr", {}).get("text") if data.get("tldr") else None,
                "url": data.get("url"),
            }

        raise ToolException(f"不支持的源: {source}", tool_name="get_paper_details")

    @staticmethod
    async def extract_summary(paper_content: str) -> str:
        """提取文献摘要 - 从全文中提取关键信息"""
        logger.info(f"提取摘要，内容长度: {len(paper_content)}")

        # 提取前500字作为摘要
        if len(paper_content) > 500:
            return paper_content[:500] + "..."
        return paper_content

    @staticmethod
    def format_citation(paper: dict[str, Any], style: str = "apa") -> str:
        """格式化引用"""
        authors = paper.get("authors", [])
        year = paper.get("year", "n.d.")
        title = paper.get("title", "Untitled")
        journal = paper.get("journal", "")
        url = paper.get("url", "")

        first_author = authors[0] if authors else "Unknown"

        if style == "apa":
            # APA格式: 作者 (年份). 标题. 期刊.
            author_str = first_author
            if len(authors) > 1:
                author_str = f"{first_author} et al."
            return f"{author_str} ({year}). {title}. {journal}."

        elif style == "mla":
            # MLA格式: 作者. "标题." 期刊, 年份.
            return f'{first_author}. "{title}." {journal}, {year}.'

        elif style == "chicago":
            # Chicago格式
            return f'{first_author}. "{title}." {journal} ({year}). {url}'

        else:
            return f"{title} by {', '.join(authors)} ({year})"

    @staticmethod
    def format_citations(papers: list[dict[str, Any]], style: str = "apa") -> str:
        """批量格式化引用"""
        citations = []
        for i, paper in enumerate(papers, 1):
            citation = LiteratureTools.format_citation(paper, style)
            citations.append(f"[{i}] {citation}")
        return "\n".join(citations)

    @staticmethod
    async def index_paper(paper: dict[str, Any]) -> str:
        """将文献索引到向量库"""
        logger.info(f"索引文献: {paper.get('title', 'unknown')}")

        try:
            vector_store = get_vector_store()
            embedding_client = get_embedding_client()

            # 准备文本
            text = f"{paper.get('title', '')} {paper.get('abstract', '')}"

            # 生成embedding
            embedding = await embedding_client.embed(text)

            # 准备元数据
            metadata = {
                "title": paper.get("title"),
                "authors": paper.get("authors", []),
                "year": paper.get("year"),
                "journal": paper.get("journal"),
                "url": paper.get("url"),
                "source": paper.get("source"),
            }

            # 插入向量库
            ids = await vector_store.insert(
                PAPERS_COLLECTION,
                texts=[text],
                embeddings=[embedding],
                metadatas=[metadata],
            )

            logger.info(f"文献索引成功: {ids[0]}")
            return ids[0]

        except Exception as e:
            logger.error(f"文献索引失败: {e}")
            raise ToolException(f"文献索引失败: {str(e)}", tool_name="index_paper")

    @staticmethod
    async def semantic_search(
        query: str,
        top_k: int = 10,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[dict[str, Any]]:
        """语义搜索"""
        logger.info(f"语义搜索: {query}")

        try:
            vector_store = get_vector_store()
            embedding_client = get_embedding_client()

            # 生成查询向量
            query_embedding = await embedding_client.embed(query)

            # 构建过滤表达式
            filter_expr = None
            if year_from or year_to:
                conditions = []
                if year_from:
                    conditions.append(f"metadata['year'] >= {year_from}")
                if year_to:
                    conditions.append(f"metadata['year'] <= {year_to}")
                filter_expr = " and ".join(conditions)

            # 向量搜索
            results = await vector_store.search(
                PAPERS_COLLECTION,
                query_embedding=query_embedding,
                top_k=top_k,
                filter_expr=filter_expr,
            )

            logger.info(f"语义搜索返回 {len(results)} 条结果")
            return results

        except Exception as e:
            logger.error(f"语义搜索失败: {e}")
            raise ToolException(f"语义搜索失败: {str(e)}", tool_name="semantic_search")

    @staticmethod
    async def index_papers_batch(papers: list[dict[str, Any]]) -> list[str]:
        """批量索引文献"""
        logger.info(f"批量索引 {len(papers)} 篇文献")

        try:
            vector_store = get_vector_store()
            embedding_client = get_embedding_client()

            # 准备数据
            texts = []
            metadatas = []
            for paper in papers:
                text = f"{paper.get('title', '')} {paper.get('abstract', '')}"
                texts.append(text)
                metadatas.append(
                    {
                        "title": paper.get("title"),
                        "authors": paper.get("authors", []),
                        "year": paper.get("year"),
                        "journal": paper.get("journal"),
                        "url": paper.get("url"),
                        "source": paper.get("source"),
                    }
                )

            # 批量生成embedding
            embeddings = await embedding_client.embed_batch(texts)

            # 批量插入
            ids = await vector_store.insert(
                PAPERS_COLLECTION,
                texts=texts,
                embeddings=embeddings,
                metadatas=metadatas,
            )

            logger.info(f"批量索引成功: {len(ids)} 篇")
            return ids

        except Exception as e:
            logger.error(f"批量索引失败: {e}")
            raise ToolException(
                f"批量索引失败: {str(e)}", tool_name="index_papers_batch"
            )

    # ========== 文献库管理工具 ==========

    @staticmethod
    def deduplicate_papers(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """检测重复文献"""
        from difflib import SequenceMatcher

        duplicates = []

        for i, paper in enumerate(papers):
            for j, other in enumerate(papers):
                if i >= j:
                    continue

                # 标题相似度
                title_sim = SequenceMatcher(
                    None, paper.get("title", "").lower(), other.get("title", "").lower()
                ).ratio()

                # DOI 匹配
                same_doi = (
                    paper.get("doi")
                    and other.get("doi")
                    and paper.get("doi") == other.get("doi")
                )

                # ID 匹配
                same_id = (
                    paper.get("id")
                    and other.get("id")
                    and paper.get("id") == other.get("id")
                )

                if same_id or same_doi or title_sim > 0.85:
                    duplicates.append(
                        {
                            "paper_1": {
                                "id": paper.get("id"),
                                "title": paper.get("title"),
                            },
                            "paper_2": {
                                "id": other.get("id"),
                                "title": other.get("title"),
                            },
                            "similarity": round(title_sim, 3),
                            "reason": (
                                "same_id"
                                if same_id
                                else ("same_doi" if same_doi else "title_similarity")
                            ),
                        }
                    )

        return duplicates

    # ========== 引用网络分析工具 ==========

    @staticmethod
    def analyze_citation_network(
        papers: list[dict[str, Any]], citations: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """分析引用网络"""
        from app.services.citation_network import CitationNetwork

        network = CitationNetwork()
        for p in papers:
            network.add_paper(
                {
                    "id": p.get("id") or p.get("paper_id", ""),
                    "title": p.get("title", ""),
                    "authors": p.get("authors", []),
                    "year": p.get("year"),
                    "journal": p.get("journal", ""),
                    "citation_count": p.get("citation_count", 0),
                }
            )
        for c in citations:
            network.add_citation(
                c.get("citing_paper_id", ""),
                c.get("cited_paper_id", ""),
                c.get("weight", 1),
            )

        metrics = network.compute_metrics()
        influential = network.get_influential_papers(top_k=10)
        co_citations = network.co_citation_analysis(min_co_citations=1, top_k=10)
        graph = network.to_graph_data()

        return {
            "metrics": metrics,
            "influential_papers": influential,
            "co_citations": co_citations.get("co_citation_pairs", [])[:10],
            "graph": graph,
        }

    @staticmethod
    def trace_research_lineage(
         papers: list[dict[str, Any]], citations: list[dict[str, Any]],
        paper_id: str, max_depth: int = 5
    ) -> dict[str, Any]:
        """追溯研究脉络"""
        from app.services.citation_network import CitationNetwork

        network = CitationNetwork()
        for p in papers:
            network.add_paper(
                {
                    "id": p.get("id") or p.get("paper_id", ""),
                    "title": p.get("title", ""),
                    "authors": p.get("authors", []),
                    "year": p.get("year"),
                    "journal": p.get("journal", ""),
                    "citation_count": p.get("citation_count", 0),
                }
            )
        for c in citations:
            network.add_citation(
                c.get("citing_paper_id", ""),
                c.get("cited_paper_id", ""),
                c.get("weight", 1),
            )

        return network.research_lineage(paper_id, max_depth)

    @staticmethod
    def identify_frontier(
        papers: list[dict[str, Any]],
        citations: list[dict[str, Any]],
        year_from: int = 2020,
        top_k: int = 20,
    ) -> dict[str, Any]:
        """识别研究前沿"""
        from app.services.citation_network import CitationNetwork

        network = CitationNetwork()
        for p in papers:
            network.add_paper(
                {
                    "id": p.get("id") or p.get("paper_id", ""),
                    "title": p.get("title", ""),
                    "authors": p.get("authors", []),
                    "year": p.get("year"),
                    "journal": p.get("journal", ""),
                    "citation_count": p.get("citation_count", 0),
                }
            )
        for c in citations:
            network.add_citation(
                c.get("citing_paper_id", ""),
                c.get("cited_paper_id", ""),
                c.get("weight", 1),
            )

        return network.research_frontier(year_from, top_k)

    @staticmethod
    def detect_clusters(
         papers: list[dict[str, Any]], citations: list[dict[str, Any]],
        algorithm: str = "louvain"
    ) -> dict[str, Any]:
        """检测研究聚类"""
        from app.services.citation_network import CitationNetwork

        network = CitationNetwork()
        for p in papers:
            network.add_paper(
                {
                    "id": p.get("id") or p.get("paper_id", ""),
                    "title": p.get("title", ""),
                    "authors": p.get("authors", []),
                    "year": p.get("year"),
                    "journal": p.get("journal", ""),
                    "citation_count": p.get("citation_count", 0),
                }
            )
        for c in citations:
            network.add_citation(
                c.get("citing_paper_id", ""),
                c.get("cited_paper_id", ""),
                c.get("weight", 1),
            )

        return network.detect_research_clusters(algorithm)

    # ========== 引用网络高级分析工具（基于 build_from_references） ==========

    @staticmethod
    def _tool_citation_graph(
        papers: list[dict[str, Any]], paper_id: str, depth: int = 2
    ) -> dict[str, Any]:
        """构建指定论文的引用关系图（BFS展开，含图表配置）"""
        from app.services.citation_network import CitationNetwork

        network = CitationNetwork()
        network.build_from_references(papers)
        return network.get_citation_graph(paper_id, depth)

    @staticmethod
    def _tool_co_citation(
        papers: list[dict[str, Any]], min_co_citations: int = 1, top_k: int = 50
    ) -> dict[str, Any]:
        """共被引分析：发现经常被一起引用的论文对"""
        from app.services.citation_network import CitationNetwork

        network = CitationNetwork()
        network.build_from_references(papers)
        return network.co_citation_analysis(min_co_citations, top_k)

    @staticmethod
    def _tool_bibliographic_coupling(
        papers: list[dict[str, Any]], min_coupling: int = 1, top_k: int = 50
    ) -> dict[str, Any]:
        """文献耦合分析：发现引用相同参考文献的论文对"""
        from app.services.citation_network import CitationNetwork

        network = CitationNetwork()
        network.build_from_references(papers)
        return network.bibliographic_coupling(min_coupling, top_k)

    @staticmethod
    def _tool_research_clusters(
         papers: list[dict[str, Any]], algorithm: str = "louvain",
        min_cluster_size: int = 3
    ) -> dict[str, Any]:
        """研究聚类/社区检测"""
        from app.services.citation_network import CitationNetwork

        network = CitationNetwork()
        network.build_from_references(papers)
        return network.detect_research_clusters(algorithm, min_cluster_size)

    @staticmethod
    def _tool_research_frontier(
        papers: list[dict[str, Any]], year_from: int = 2020, top_k: int = 20
    ) -> dict[str, Any]:
        """研究前沿识别：近年高影响力论文与新兴主题"""
        from app.services.citation_network import CitationNetwork

        network = CitationNetwork()
        network.build_from_references(papers)
        return network.research_frontier(year_from, top_k)

    @staticmethod
    def _tool_research_lineage(
        papers: list[dict[str, Any]], paper_id: str, max_depth: int = 5
    ) -> dict[str, Any]:
        """研究脉络追溯：从一篇论文回溯到学术根源"""
        from app.services.citation_network import CitationNetwork

        network = CitationNetwork()
        network.build_from_references(papers)
        return network.research_lineage(paper_id, max_depth)

    @staticmethod
    def _tool_knowledge_diffusion(
        papers: list[dict[str, Any]], paper_id: str, max_depth: int = 3
    ) -> dict[str, Any]:
        """知识扩散分析：追踪论文影响力的传播路径"""
        from app.services.citation_network import CitationNetwork

        network = CitationNetwork()
        network.build_from_references(papers)
        return network.knowledge_diffusion(paper_id, max_depth)

    @staticmethod
    def _tool_citation_timeline(
        papers: list[dict[str, Any]], paper_id: str
    ) -> dict[str, Any]:
        """引用时间线：按年份统计被引趋势"""
        from app.services.citation_network import CitationNetwork

        network = CitationNetwork()
        network.build_from_references(papers)
        return network.citation_timeline(paper_id)

    @staticmethod
    def _tool_influential_papers(
        papers: list[dict[str, Any]], top_k: int = 10
    ) -> dict[str, Any]:
        """高影响力论文识别（基于PageRank）"""
        from app.services.citation_network import CitationNetwork

        network = CitationNetwork()
        network.build_from_references(papers)
        influential = network.get_influential_papers(top_k)
        return {"influential_papers": influential, "n_papers": len(influential)}

    @staticmethod
    def _tool_network_metrics(papers: list[dict[str, Any]]) -> dict[str, Any]:
        """引用网络整体指标"""
        from app.services.citation_network import CitationNetwork

        network = CitationNetwork()
        network.build_from_references(papers)
        return network.compute_metrics()

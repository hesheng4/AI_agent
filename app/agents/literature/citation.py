"""引用网络分析模块"""

from collections import defaultdict
from typing import Any

import httpx

from app.utils.exceptions import ToolException
from app.utils.logger import get_logger

logger = get_logger("citation")

SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"
TIMEOUT = 30.0


class CitationAnalyzer:
    """引用网络分析器"""

    @staticmethod
    async def get_citations(paper_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """获取引用该论文的文献"""
        logger.info(f"获取引用: {paper_id}")

        url = f"{SEMANTIC_SCHOLAR_API}/paper/{paper_id}/citations"
        params: dict[str, Any] = {
            "fields": "title,authors,year,journal,citationCount",
            "limit": limit,
        }

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.get(url, params=params)

                if response.status_code != 200:
                    logger.warning(f"获取引用失败: {response.status_code}")
                    return []

                data = response.json()
                citations = []
                for item in data.get("data", []):
                    paper = item.get("citingPaper", {})
                    citations.append(
                        {
                            "id": paper.get("paperId"),
                            "title": paper.get("title"),
                            "authors": [
                                a.get("name") for a in paper.get("authors", [])
                            ],
                            "year": paper.get("year"),
                            "journal": (
                                paper.get("journal", {}).get("name")
                                if paper.get("journal")
                                else None
                            ),
                            "citation_count": paper.get("citationCount", 0),
                        }
                    )

                logger.info(f"获取到 {len(citations)} 篇引用文献")
                return citations

        except Exception as e:
            logger.error(f"获取引用失败: {e}")
            return []

    @staticmethod
    async def get_references(paper_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """获取该论文的参考文献"""
        logger.info(f"获取参考文献: {paper_id}")

        url = f"{SEMANTIC_SCHOLAR_API}/paper/{paper_id}/references"
        params: dict[str, Any] = {
            "fields": "title,authors,year,journal,citationCount",
            "limit": limit,
        }

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.get(url, params=params)

                if response.status_code != 200:
                    logger.warning(f"获取参考文献失败: {response.status_code}")
                    return []

                data = response.json()
                references = []
                for item in data.get("data", []):
                    paper = item.get("citedPaper", {})
                    if paper.get("paperId"):
                        references.append(
                            {
                                "id": paper.get("paperId"),
                                "title": paper.get("title"),
                                "authors": [
                                    a.get("name") for a in paper.get("authors", [])
                                ],
                                "year": paper.get("year"),
                                "journal": (
                                    paper.get("journal", {}).get("name")
                                    if paper.get("journal")
                                    else None
                                ),
                                "citation_count": paper.get("citationCount", 0),
                            }
                        )

                logger.info(f"获取到 {len(references)} 篇参考文献")
                return references

        except Exception as e:
            logger.error(f"获取参考文献失败: {e}")
            return []

    @staticmethod
    async def build_citation_network(paper_id: str, depth: int = 1) -> dict[str, Any]:
        """构建引用网络"""
        logger.info(f"构建引用网络: depth={depth}")

        nodes = {}
        edges = []

        # 获取中心论文
        url = f"{SEMANTIC_SCHOLAR_API}/paper/{paper_id}"
        params = {"fields": "title,authors,year,citationCount"}

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    paper = response.json()
                    nodes[paper_id] = {
                        "id": paper_id,
                        "label": paper.get("title", "")[:50],
                        "year": paper.get("year"),
                        "citations": paper.get("citationCount", 0),
                        "level": 0,
                    }

            # 获取引用和参考文献
            citations = await CitationAnalyzer.get_citations(paper_id, limit=10)
            references = await CitationAnalyzer.get_references(paper_id, limit=10)

            # 添加引用节点和边
            for c in citations[:10]:
                cid = c.get("id")
                if cid:
                    nodes[cid] = {
                        "id": cid,
                        "label": c.get("title", "")[:50],
                        "year": c.get("year"),
                        "citations": c.get("citation_count", 0),
                        "level": 1,
                    }
                    edges.append({"source": cid, "target": paper_id, "type": "cites"})

            # 添加参考文献节点和边
            for r in references[:10]:
                rid = r.get("id")
                if rid:
                    nodes[rid] = {
                        "id": rid,
                        "label": r.get("title", "")[:50],
                        "year": r.get("year"),
                        "citations": r.get("citation_count", 0),
                        "level": 1,
                    }
                    edges.append(
                        {"source": paper_id, "target": rid, "type": "references"}
                    )

            return {
                "center": paper_id,
                "nodes": list(nodes.values()),
                "edges": edges,
                "stats": {
                    "total_nodes": len(nodes),
                    "total_edges": len(edges),
                    "citations_count": len(citations),
                    "references_count": len(references),
                },
            }

        except Exception as e:
            logger.error(f"构建引用网络失败: {e}")
            raise ToolException(
                f"构建引用网络失败: {str(e)}", tool_name="build_citation_network"
            )

    @staticmethod
    async def find_co_citations(paper_ids: list[str]) -> dict[str, Any]:
        """查找共被引关系"""
        logger.info(f"查找共被引: {len(paper_ids)} 篇论文")

        # 获取每篇论文的引用
        all_citations = {}
        for pid in paper_ids:
            citations = await CitationAnalyzer.get_citations(pid, limit=100)
            all_citations[pid] = set(c.get("id") for c in citations if c.get("id"))

        # 找共被引
        co_citations: list[dict[str, Any]] = []
        for i, pid1 in enumerate(paper_ids):
            for pid2 in paper_ids[i + 1 :]:
                common = all_citations.get(pid1, set()) & all_citations.get(pid2, set())
                if common:
                    co_citations.append(
                        {
                            "paper1": pid1,
                            "paper2": pid2,
                            "common_citations": len(common),
                            "common_papers": list(common)[:5],
                        }
                    )

        # 按共被引次数排序
        co_citations.sort(key=lambda x: x["common_citations"], reverse=True)

        return {
            "papers_analyzed": len(paper_ids),
            "co_citations": co_citations,
            "total_pairs": len(co_citations),
        }

    @staticmethod
    async def get_citation_trend(paper_id: str) -> dict[str, Any]:
        """获取引用趋势"""
        logger.info(f"获取引用趋势: {paper_id}")

        citations = await CitationAnalyzer.get_citations(paper_id, limit=500)

        # 按年份统计
        year_counts: dict[Any, int] = defaultdict(int)
        for c in citations:
            year = c.get("year")
            if year:
                year_counts[year] += 1

        # 排序
        trend = sorted(year_counts.items())

        return {
            "paper_id": paper_id,
            "total_citations": len(citations),
            "trend": [{"year": y, "count": c} for y, c in trend],
            "peak_year": (
                max(year_counts.items(), key=lambda x: x[1])[0] if year_counts else None
            ),
        }

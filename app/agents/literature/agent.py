import asyncio
from typing import Any

from app.agents.base import BaseAgent
from app.agents.literature.prompts import (
    CITATION_NETWORK_PROMPT,
    LIBRARY_MANAGE_PROMPT,
    READ_SYSTEM_PROMPT,
    SEARCH_SYSTEM_PROMPT,
    SUMMARIZE_SYSTEM_PROMPT,
)
from app.agents.literature.tools import LiteratureTools
from app.utils.exceptions import AgentException, ValidationException

# 单篇文献总结的并发上限，避免一次性压垮 LLM 后端
_SUMMARIZE_CONCURRENCY = 5


class LiteratureAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            name="literature",
            tools=[
                "search_papers",
                "extract_summary",
                "format_citation",
                "manage_library",
                "citation_network",
                "reading_notes",
            ],
        )
        self.tools_handler = LiteratureTools()

    async def process(self, request: dict[str, Any]) -> dict[str, Any]:
        task = request.get("task")

        if not task:
            raise ValidationException("缺少task字段")

        if task == "search":
            return await self._handle_search(request)
        elif task == "read":
            return await self._handle_read(request)
        elif task == "summarize":
            return await self._handle_summarize(request)
        elif task == "library":
            return await self._handle_library(request)
        elif task == "citation_network":
            return await self._handle_citation_network(request)
        elif task == "notes":
            return await self._handle_notes(request)
        else:
            raise AgentException(f"未知任务类型: {task}", self.name)

    async def _handle_search(self, request: dict[str, Any]) -> dict[str, Any]:
        """处理搜索任务"""
        self.validate_request(request, ["query"])

        query = request.get("query", "")
        filters = request.get("filters", {})

        try:
            papers = await self.tools_handler.search_papers(query, filters)

            prompt = (
                f"用户正在搜索关于 '{query}' 的文献。请提供3-5个相关的搜索关键词建议。"
            )
            suggestions = await self.call_llm(
                prompt, SEARCH_SYSTEM_PROMPT, temperature=0.0
            )

            return {
                "status": "success",
                "papers": papers,
                "suggestions": suggestions,
                "total_results": len(papers),
            }
        except Exception as e:
            self.logger.error(f"文献搜索失败: {e}", exc_info=True)
            raise AgentException(f"文献搜索失败: {str(e)}", self.name)

    async def _handle_read(self, request: dict[str, Any]) -> dict[str, Any]:
        """处理阅读任务"""
        self.validate_request(request, ["content"])

        paper_content = request.get("content", "")

        if len(paper_content) < 50:
            raise ValidationException("文献内容过短")

        try:
            prompt = f"请分析以下学术文献内容，并提供关键要点：\n\n{paper_content}"
            analysis = await self.call_llm(prompt, READ_SYSTEM_PROMPT, temperature=0.0)

            return {"status": "success", "analysis": analysis, "key_points": []}
        except Exception as e:
            self.logger.error(f"文献分析失败: {e}", exc_info=True)
            raise AgentException(f"文献分析失败: {str(e)}", self.name)

    async def _handle_summarize(self, request: dict[str, Any]) -> dict[str, Any]:
        """处理总结任务"""
        self.validate_request(request, ["papers"])

        papers = request.get("papers", [])

        if not papers:
            raise ValidationException("papers列表为空")

        try:
            # 过滤掉缺少 title/abstract 的文献，记录跳过原因
            valid_papers = []
            for i, paper in enumerate(papers):
                if not paper.get("title") or not paper.get("abstract"):
                    self.logger.warning(f"跳过第{i + 1}篇文献：缺少title或abstract")
                    continue
                valid_papers.append(paper)

            if not valid_papers:
                raise AgentException("没有有效的文献可总结", self.name)

            # 并发总结单篇文献，Semaphore 限制并发度
            sem = asyncio.Semaphore(_SUMMARIZE_CONCURRENCY)

            async def summarize_one(paper: dict[str, Any]) -> dict[str, Any]:
                prompt = (
                    f"请总结以下文献的核心内容：\n"
                    f"标题：{paper.get('title')}\n摘要：{paper.get('abstract')}"
                )
                async with sem:
                    summary = await self.call_llm(
                        prompt, SUMMARIZE_SYSTEM_PROMPT, temperature=0.0
                    )
                return {"title": paper.get("title"), "summary": summary}

            summaries = await asyncio.gather(
                *[summarize_one(p) for p in valid_papers], return_exceptions=True
            )

            # 过滤失败项，保留成功结果
            ok_summaries: list[dict[str, str]] = []
            for i, res in enumerate(summaries):
                if isinstance(res, Exception):
                    self.logger.warning(
                        f"总结第{i + 1}篇文献失败: {res}", exc_info=False
                    )
                elif isinstance(res, dict):
                    ok_summaries.append(res)

            if not ok_summaries:
                raise AgentException("所有文献总结均失败", self.name)

            summaries_text = "\n".join([s["summary"] for s in ok_summaries])
            review_prompt = (
                f"基于以下文献摘要，生成一份简要的文献综述：\n\n{summaries_text}"
            )
            review = await self.call_llm(
                review_prompt, SUMMARIZE_SYSTEM_PROMPT, temperature=0.0
            )

            return {
                "status": "success",
                "summaries": ok_summaries,
                "review": review,
                "total_processed": len(ok_summaries),
            }
        except AgentException:
            raise
        except Exception as e:
            self.logger.error(f"文献总结失败: {e}", exc_info=True)
            raise AgentException(f"文献总结失败: {str(e)}", self.name) from e

    async def _handle_library(self, request: dict[str, Any]) -> dict[str, Any]:
        """处理文献库管理任务"""
        action = request.get("action")
        if not action:
            raise ValidationException("缺少action字段")

        try:
            if action == "organize":
                """智能整理文献库：分类、标签建议"""
                papers = request.get("papers", [])
                if not papers:
                    raise ValidationException("papers列表为空")

                papers_text = "\n".join(
                    [
                        (
                            f"- {p.get('title', 'N/A')} ({p.get('year', 'N/A')}) "
                            f"[{', '.join(p.get('tags', []))}]"
                        )
                        for p in papers[:30]
                    ]
                )
                prompt = f"请对以下文献进行智能分类和标签建议：\n{papers_text}"
                suggestions = await self.call_llm(
                    prompt, LIBRARY_MANAGE_PROMPT, temperature=0.0
                )

                return {
                    "status": "success",
                    "action": "organize",
                    "suggestions": suggestions,
                }

            elif action == "deduplicate":
                """去重检查"""
                papers = request.get("papers", [])
                if not papers:
                    raise ValidationException("papers列表为空")

                result = self.tools_handler.deduplicate_papers(papers)

                return {
                    "status": "success",
                    "action": "deduplicate",
                    "duplicates": result,
                }

            elif action == "auto_tag":
                """自动标签建议"""
                paper = request.get("paper", {})
                if not paper or not paper.get("title"):
                    raise ValidationException("缺少paper或title")

                prompt = (
                    "请为以下论文推荐3-5个标签：\n标题："
                    f"{paper.get('title')}\n摘要：{paper.get('abstract', 'N/A')}"
                )
                suggestions = await self.call_llm(
                    prompt, LIBRARY_MANAGE_PROMPT, temperature=0.0
                )

                return {
                    "status": "success",
                    "action": "auto_tag",
                    "paper_id": paper.get("id"),
                    "tag_suggestions": suggestions,
                }

            else:
                raise AgentException(f"未知library action: {action}", self.name)

        except AgentException:
            raise
        except Exception as e:
            self.logger.error(f"文献库管理失败: {e}", exc_info=True)
            raise AgentException(f"文献库管理失败: {str(e)}", self.name)

    async def _handle_citation_network(self, request: dict[str, Any]) -> dict[str, Any]:
        """处理引用网络分析任务"""
        analysis = request.get("analysis")
        if analysis:
            return await self._dispatch_citation_analysis(request, analysis)

        action = request.get("action")
        if not action:
            raise ValidationException("缺少action字段")

        try:
            if action == "analyze":
                """分析引用网络"""
                papers = request.get("papers", [])
                citations = request.get("citations", [])

                result = self.tools_handler.analyze_citation_network(papers, citations)

                # LLM 解读分析结果
                prompt = (
                    f"请解读以下引用网络分析结果，用中文描述研究脉络和关键发现：\n"
                    f"论文数: {result.get('metrics', {}).get('total_papers', 0)}\n"
                    f"引用关系数: "
                    f"{result.get('metrics', {}).get('total_citations', 0)}\n"
                    f"高影响力论文: {result.get('influential_papers', [])[:5]}\n"
                    f"共被引对: {result.get('co_citations', [])[:5]}"
                )
                interpretation = await self.call_llm(
                    prompt, CITATION_NETWORK_PROMPT, temperature=0.0
                )

                return {
                    "status": "success",
                    "action": "analyze",
                    "analysis": result,
                    "interpretation": interpretation,
                }

            elif action == "lineage":
                """追溯研究脉络"""
                paper_id = request.get("paper_id")
                if not paper_id:
                    raise ValidationException("缺少paper_id")

                papers = request.get("papers", [])
                citations = request.get("citations", [])
                max_depth = request.get("max_depth", 5)

                result = self.tools_handler.trace_research_lineage(
                    papers, citations, paper_id, max_depth
                )

                return {"status": "success", "action": "lineage", "lineage": result}

            elif action == "frontier":
                """识别研究前沿"""
                papers = request.get("papers", [])
                citations = request.get("citations", [])
                year_from = request.get("year_from", 2020)
                top_k = request.get("top_k", 20)

                result = self.tools_handler.identify_frontier(
                    papers, citations, year_from, top_k
                )

                return {"status": "success", "action": "frontier", "frontier": result}

            elif action == "clusters":
                """检测研究聚类"""
                papers = request.get("papers", [])
                citations = request.get("citations", [])
                algorithm = request.get("algorithm", "louvain")

                result = self.tools_handler.detect_clusters(
                    papers, citations, algorithm
                )

                return {"status": "success", "action": "clusters", "clusters": result}

            else:
                raise AgentException(
                    f"未知citation_network action: {action}", self.name
                )

        except AgentException:
            raise
        except Exception as e:
            self.logger.error(f"引用网络分析失败: {e}", exc_info=True)
            raise AgentException(f"引用网络分析失败: {str(e)}", self.name)

    async def _dispatch_citation_analysis(
        self, request: dict[str, Any], analysis: str
    ) -> dict[str, Any]:
        """按 analysis 字段分发到引用网络高级分析工具（基于 build_from_references）"""
        papers = request.get("papers", [])
        if not papers:
            raise ValidationException("papers列表为空")

        try:
            if analysis == "graph":
                paper_id = request.get("paper_id")
                if not paper_id:
                    raise ValidationException("缺少paper_id")
                depth = request.get("depth", 2)
                result = self.tools_handler._tool_citation_graph(
                    papers, paper_id, depth
                )
                return {"status": "success", "analysis": "graph", "graph": result}

            elif analysis == "co_citation":
                min_co_citations = request.get("min_co_citations", 1)
                top_k = request.get("top_k", 50)
                result = self.tools_handler._tool_co_citation(
                    papers, min_co_citations, top_k
                )
                return {
                    "status": "success",
                    "analysis": "co_citation",
                    "co_citation": result,
                }

            elif analysis == "coupling":
                min_coupling = request.get("min_coupling", 1)
                top_k = request.get("top_k", 50)
                result = self.tools_handler._tool_bibliographic_coupling(
                    papers, min_coupling, top_k
                )
                return {
                    "status": "success",
                    "analysis": "coupling",
                    "bibliographic_coupling": result,
                }

            elif analysis == "clusters":
                algorithm = request.get("algorithm", "louvain")
                min_cluster_size = request.get("min_cluster_size", 3)
                result = self.tools_handler._tool_research_clusters(
                    papers, algorithm, min_cluster_size
                )
                return {"status": "success", "analysis": "clusters", "clusters": result}

            elif analysis == "frontier":
                year_from = request.get("year_from", 2020)
                top_k = request.get("top_k", 20)
                result = self.tools_handler._tool_research_frontier(
                    papers, year_from, top_k
                )
                return {"status": "success", "analysis": "frontier", "frontier": result}

            elif analysis == "lineage":
                paper_id = request.get("paper_id")
                if not paper_id:
                    raise ValidationException("缺少paper_id")
                max_depth = request.get("max_depth", 5)
                result = self.tools_handler._tool_research_lineage(
                    papers, paper_id, max_depth
                )
                return {"status": "success", "analysis": "lineage", "lineage": result}

            elif analysis == "diffusion":
                paper_id = request.get("paper_id")
                if not paper_id:
                    raise ValidationException("缺少paper_id")
                max_depth = request.get("max_depth", 3)
                result = self.tools_handler._tool_knowledge_diffusion(
                    papers, paper_id, max_depth
                )
                return {
                    "status": "success",
                    "analysis": "diffusion",
                    "diffusion": result,
                }

            elif analysis == "timeline":
                paper_id = request.get("paper_id")
                if not paper_id:
                    raise ValidationException("缺少paper_id")
                result = self.tools_handler._tool_citation_timeline(papers, paper_id)
                return {"status": "success", "analysis": "timeline", "timeline": result}

            elif analysis == "influential":
                top_k = request.get("top_k", 10)
                result = self.tools_handler._tool_influential_papers(papers, top_k)
                return {
                    "status": "success",
                    "analysis": "influential",
                    "influential": result,
                }

            elif analysis == "metrics":
                result = self.tools_handler._tool_network_metrics(papers)
                return {"status": "success", "analysis": "metrics", "metrics": result}

            else:
                raise AgentException(f"未知analysis类型: {analysis}", self.name)

        except AgentException:
            raise
        except Exception as e:
            self.logger.error(f"引用网络分析失败: {e}", exc_info=True)
            raise AgentException(f"引用网络分析失败: {str(e)}", self.name)

    async def _handle_notes(self, request: dict[str, Any]) -> dict[str, Any]:
        """处理阅读笔记任务"""
        action = request.get("action")
        if not action:
            raise ValidationException("缺少action字段")

        try:
            if action == "smart_note":
                """智能笔记生成"""
                content = request.get("content", "")
                note_type = request.get("note_type", "general")

                if not content:
                    raise ValidationException("缺少content")

                type_instructions = {
                    "insight": "请提取文献中的关键洞见和创新点",
                    "method": "请提取文献中使用的研究方法和技术细节",
                    "question": "请列出阅读时产生的疑问和可能的延伸研究方向",
                    "general": "请生成结构化的阅读笔记",
                }

                instruction = type_instructions.get(
                    note_type, type_instructions["general"]
                )
                prompt = f"{instruction}:\n\n{content}"
                note = await self.call_llm(prompt, READ_SYSTEM_PROMPT, temperature=0.0)

                return {
                    "status": "success",
                    "action": "smart_note",
                    "note": note,
                    "note_type": note_type,
                }

            elif action == "synthesize":
                """综合多篇文献笔记"""
                notes = request.get("notes", [])
                if not notes:
                    raise ValidationException("notes列表为空")

                notes_text = "\n\n---\n\n".join(
                    [
                        f"【{n.get('title', 'N/A')}】\n{n.get('content', '')}"
                        for n in notes
                    ]
                )
                prompt = (
                    "请综合以下多篇文献的阅读笔记，找出共性和差异，"
                    "生成综合性分析：\n\n"
                    f"{notes_text}"
                )
                synthesis = await self.call_llm(
                    prompt, SUMMARIZE_SYSTEM_PROMPT, temperature=0.0
                )

                return {
                    "status": "success",
                    "action": "synthesize",
                    "synthesis": synthesis,
                }

            else:
                raise AgentException(f"未知notes action: {action}", self.name)

        except AgentException:
            raise
        except Exception as e:
            self.logger.error(f"阅读笔记处理失败: {e}", exc_info=True)
            raise AgentException(f"阅读笔记处理失败: {str(e)}", self.name)

    # Nature-academic-search: 5 工作流
    WORKFLOWS = [
        "multi-source-search",
        "citation-verification",
        "mesh-strategy",
        "citation-file-mgmt",
        "reference-mgmt",
    ]

    # T1→T2→T3 源路由层级
    SOURCE_TIERS = {
        "T1": ["semantic_scholar", "arxiv"],  # 首选：开放 API
        "T2": ["crossref", "pubmed"],  # 备选：需 key
        "T3": ["scopus", "science_direct"],  # 付费源
    }

    @staticmethod
    def detect_workflow(request: dict[str, Any]) -> str:
        """检测学术搜索工作流类型"""
        task = request.get("task", "search")
        if "verify" in task or "核对" in task:
            return "citation-verification"
        if "mesh" in task or "策略" in task:
            return "mesh-strategy"
        if "convert" in task or "转换" in task:
            return "citation-file-mgmt"
        if "bibtex" in task or "related" in task:
            return "reference-mgmt"
        return "multi-source-search"

    # MCP 工具路由表
    MCP_TOOLS = {
        "pubmed": {
            "tier": "T2",
            "requires_key": True,
            "base_url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
        },
        "crossref": {
            "tier": "T2",
            "requires_key": False,
            "base_url": "https://api.crossref.org/works",
        },
        "arxiv": {
            "tier": "T1",
            "requires_key": False,
            "base_url": "http://export.arxiv.org/api/query",
        },
        "semantic_scholar": {
            "tier": "T1",
            "requires_key": False,
            "base_url": "https://api.semanticscholar.org/graph/v1",
        },
        "scopus": {
            "tier": "T3",
            "requires_key": True,
            "base_url": "https://api.elsevier.com/content/search/scopus",
        },
    }

    @classmethod
    def route_search(cls, query: str, preferred_tier: str = "T1") -> list[str]:
        """按 T1→T2→T3 路由选择搜索源"""
        tier_order = ["T1", "T2", "T3"]
        start = tier_order.index(preferred_tier) if preferred_tier in tier_order else 0
        sources = []
        for tier in tier_order[start:]:
            for name, cfg in cls.MCP_TOOLS.items():
                if cfg["tier"] == tier:
                    sources.append(name)
        return sources

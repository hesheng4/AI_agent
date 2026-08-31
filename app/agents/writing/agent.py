import re
from typing import Any

from app.agents.base import BaseAgent
from app.agents.writing.prompts import (
    EVIDENCE_CHAIN_PROMPT,
    GENERATE_SYSTEM_PROMPT,
    OUTLINE_SYSTEM_PROMPT,
    POLISH_SYSTEM_PROMPT,
    REVISE_PROMPT,
    STRUCTURE_ANALYSIS_PROMPT,
)
from app.agents.writing.tools import WritingTools
from app.utils.exceptions import AgentException


class WritingAgent(BaseAgent):
    """Nature-skills 驱动的学术写作 Agent

    支持任务:
    - outline: 生成论文大纲（支持论文类型分类学）
    - generate: 生成章节内容（遵循论证链）
    - polish: 润色文本（服务读者工作流）
    - structure: 分析论证结构（读者问题序列覆盖）
    - terminology: 构建术语账本
    - evidence: 分析证据链完整性
    """

    # 学术写作属半确定性任务，低温保证结构与措辞可复现
    _DETERMINISTIC_TEMPERATURE = 0.0

    def __init__(self):
        super().__init__(
            name="writing",
            tools=[
                "create_outline",
                "generate_content",
                "polish",
                "analyze_structure",
                "build_terminology",
                "analyze_evidence",
                "detect_paper_type",
                "check_grammar",
                "count_words",
            ],
        )
        self.tools_handler = WritingTools()
        # 缓存任务分派表，避免每次 process 重建
        self._task_handlers = {
            "outline": self.create_outline,
            "generate": self.generate_content,
            "polish": self.polish,
            "structure": self.analyze_structure,
            "terminology": self.build_terminology,
            "evidence": self.analyze_evidence,
            "cite": self._handle_cite,
            "export": self._handle_export,
            "revise": self.revise,
        }

    async def process(self, request: dict[str, Any]) -> dict[str, Any]:
        task = request.get("task")
        # 用户级 API 配置由 request dict 透传给 handler（不经实例属性，避免并发污染）
        handler = self._task_handlers.get(task)
        if handler:
            return await handler(request)
        raise AgentException(
            f"未知任务类型: {task!r}，支持: outline/generate/polish/"
            "structure/terminology/evidence/cite/export",
            self.name,
        )

    async def create_outline(self, request: dict[str, Any]) -> dict[str, Any]:
        """生成论文大纲（Nature-skills 论文类型分类学驱动）"""
        topic = request.get("topic", "")
        paper_type = request.get("paper_type", "research")
        journal = request.get("journal", "standard")

        # 如果未指定类型，尝试从主题推断
        if paper_type == "auto":
            detection = self.tools_handler.detect_paper_type(topic)
            paper_type = detection["detected_type"]

        # 创建类型化大纲模板
        template = self.tools_handler.create_outline_template(
            topic, paper_type, journal
        )

        # 构建增强型提示
        type_info = self.tools_handler.PAPER_TYPES.get(
            paper_type, self.tools_handler.PAPER_TYPES["research"]
        )
        prompt = (
            f"请为以下研究主题设计详细的论文大纲：\n"
            f"主题：{topic}\n"
            f"论文类型：{type_info['label']}（{type_info['definition']}）\n"
            f"核心论证链：{type_info['core_chain']}\n"
            f"读者核心问题：{type_info['reader_question']}\n"
            f"推荐起草顺序：{' → '.join(type_info['drafting_order'])}\n\n"
            f"基础模板：{template}"
        )

        optimized_outline = await self.call_llm(
            prompt,
            OUTLINE_SYSTEM_PROMPT,
            temperature=self._DETERMINISTIC_TEMPERATURE,
            user_api_key=request.get("_user_api_key"),
            user_api_base_url=request.get("_user_api_base_url"),
            user_api_model=request.get("_user_api_model"),
        )

        return {
            "template": template,
            "optimized_outline": optimized_outline,
            "paper_type": paper_type,
            "core_chain": type_info["core_chain"],
            "drafting_order": type_info["drafting_order"],
        }

    async def generate_content(self, request: dict[str, Any]) -> dict[str, Any]:
        """生成章节内容（遵循论证链和读者工作流）"""
        outline = request.get("outline", {})
        section = request.get("section", "introduction")
        paper_type = request.get("paper_type", "research")
        terminology_ledger = request.get("terminology_ledger", {})

        type_info = self.tools_handler.PAPER_TYPES.get(
            paper_type, self.tools_handler.PAPER_TYPES["research"]
        )

        # 构建增强型提示
        prompt = (
            f"请根据以下大纲的'{section}'部分生成内容：\n"
            f"论文类型：{type_info['label']}\n"
            f"核心论证链：{type_info['core_chain']}\n"
            f"当前章节：{section}\n\n"
            f"大纲：{outline}"
        )

        # 如果有术语账本，加入提示
        if terminology_ledger:
            terms_str = "\n".join(
                f"- {k}: {v.get('canonical', k)} ({v.get('full_form', '')})"
                for k, v in terminology_ledger.items()
            )
            prompt += f"\n\n术语账本（必须使用规范形式）：\n{terms_str}"

        # 上游文献检索结果（协调器注入）：列出可引用文献，标题原文进入提示
        papers = request.get("papers") or []
        if papers:
            paper_lines = []
            for i, p in enumerate(papers[:10], 1):
                if isinstance(p, dict):
                    title = str(p.get("title", "")).strip()
                    if not title:
                        continue
                    authors = ", ".join(
                        str(a) for a in (p.get("authors") or [])[:3]
                    )
                    meta = f"{authors} ({p.get('year', '')})" if authors else str(
                        p.get("year", "")
                    )
                    paper_lines.append(f"{i}. {title} {meta}".strip())
                else:
                    paper_lines.append(f"{i}. {p}")
            if paper_lines:
                prompt += (
                    "\n\n可引用检索文献（正文引用须来自该列表）：\n"
                    + "\n".join(paper_lines)
                )

        content = await self.call_llm(
            prompt,
            GENERATE_SYSTEM_PROMPT,
            temperature=self._DETERMINISTIC_TEMPERATURE,
            user_api_key=request.get("_user_api_key"),
            user_api_base_url=request.get("_user_api_base_url"),
            user_api_model=request.get("_user_api_model"),
        )

        return {"section": section, "content": content, "paper_type": paper_type}

    async def polish(self, request: dict[str, Any]) -> dict[str, Any]:
        """润色文本（服务读者工作流，不改变论证结构）"""
        content = request.get("content", "")
        request.get("paper_type", "research")

        # 先构建术语账本用于一致性检查
        ledger = self.tools_handler.build_terminology_ledger(content)
        terminology_context = ""
        if ledger["total_terms"] > 0:
            terms_str = "\n".join(
                f"- {v['canonical']}: {v.get('full_form', '')}"
                for v in ledger["ledger"].values()
            )
            terminology_context = f"\n\n已识别术语账本（确保一致性）：\n{terms_str}"

        prompt = (
            f"请润色以下学术文本，提升其学术性和可读性：\n\n"
            f"{content}{terminology_context}"
        )
        polished = await self.call_llm(
            prompt,
            POLISH_SYSTEM_PROMPT,
            temperature=self._DETERMINISTIC_TEMPERATURE,
            user_api_key=request.get("_user_api_key"),
            user_api_base_url=request.get("_user_api_base_url"),
            user_api_model=request.get("_user_api_model"),
        )

        formatted = self.tools_handler.format_academic_text(polished)

        return {
            "original": content,
            "polished": formatted,
            "terminology_ledger": ledger,
        }

    async def revise(self, request: dict[str, Any]) -> dict[str, Any]:
        """按审稿意见修订稿件（H1 迭代闭环的修订环节）

        输入 content + review_result（含 improvement_suggestions），
        LLM 生成修订稿，并返回 change_log 与无法落实的 skipped 列表。
        """
        content = request.get("content", "")
        review_result = request.get("review_result", {}) or {}
        suggestions = request.get("suggestions") or review_result.get(
            "improvement_suggestions", []
        )

        if not content.strip():
            raise AgentException("稿件内容不能为空", self.name)
        if not suggestions:
            raise AgentException("改进建议不能为空", self.name)

        suggestions_text = "\n".join(
            f"- [{s.get('severity', 'minor')}] {s.get('issue', '')}"
            f"（{s.get('location', '全文')}）→ {s.get('suggestion', '')}"
            for s in suggestions
            if isinstance(s, dict) and s.get("issue")
        )
        if not suggestions_text.strip():
            raise AgentException("改进建议不能为空", self.name)

        prompt = (
            f"{REVISE_PROMPT}\n\n"
            f"审稿改进建议：\n{suggestions_text}\n\n"
            f"稿件内容：\n{content[:8000]}"
        )
        raw = await self.call_llm(
            prompt,
            GENERATE_SYSTEM_PROMPT,
            temperature=self._DETERMINISTIC_TEMPERATURE,
            user_api_key=request.get("_user_api_key"),
            user_api_base_url=request.get("_user_api_base_url"),
            user_api_model=request.get("_user_api_model"),
        )

        parsed = self._parse_revise_result(raw, content)
        return {
            "revised_content": parsed.get("revised_content", content),
            "change_log": parsed.get("change_log", []),
            "skipped": parsed.get("skipped", []),
            "parse_error": parsed.get("parse_error", False),
        }

    @staticmethod
    def _parse_revise_result(raw: str, fallback: str) -> dict[str, Any]:
        """容错解析修订 JSON；解析失败时退回原文并标记错误"""
        if not raw or not raw.strip():
            return {
                "revised_content": fallback,
                "change_log": [],
                "skipped": [],
                "parse_error": True,
            }
        text = raw.strip()
        fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
        if fence:
            text = fence.group(1).strip()
        obj_match = re.search(r"\{.*\}", text, re.S)
        if not obj_match:
            return {
                "revised_content": fallback,
                "change_log": [],
                "skipped": [],
                "parse_error": True,
            }
        try:
            import json

            data = json.loads(obj_match.group(0))
        except Exception:
            return {
                "revised_content": fallback,
                "change_log": [],
                "skipped": [],
                "parse_error": True,
            }
        revised = data.get("revised_content") or fallback
        return {
            "revised_content": revised,
            "change_log": data.get("change_log", []),
            "skipped": data.get("skipped", []),
        }

    async def analyze_structure(self, request: dict[str, Any]) -> dict[str, Any]:
        """分析论文论证结构（Nature-skills 读者工作流驱动）"""
        content = request.get("content", "")
        paper_type = request.get("paper_type")

        # 工具层面的结构分析
        analysis = self.tools_handler.analyze_structure(content, paper_type)

        # LLM 深度分析
        prompt = (
            f"请分析以下论文的论证结构：\n\n"
            f"论文类型：{analysis.get('paper_type_label', '研究论文')}\n"
            f"核心论证链：{analysis.get('core_chain', '')}\n"
            f"结构评分：{analysis.get('overall_score', 0)}/10\n\n"
            f"文本内容：\n{content[:8000]}"
        )

        llm_analysis = await self.call_llm(
            prompt,
            STRUCTURE_ANALYSIS_PROMPT,
            temperature=self._DETERMINISTIC_TEMPERATURE,
            user_api_key=request.get("_user_api_key"),
            user_api_base_url=request.get("_user_api_base_url"),
            user_api_model=request.get("_user_api_model"),
        )

        return {
            "tool_analysis": analysis,
            "llm_analysis": llm_analysis,
            "paper_type": analysis.get("paper_type"),
            "overall_score": analysis.get("overall_score", 0),
        }

    async def build_terminology(self, request: dict[str, Any]) -> dict[str, Any]:
        """构建术语账本（Nature-skills 术语账本规则）"""
        content = request.get("content", "")

        ledger = self.tools_handler.build_terminology_ledger(content)

        return {
            "ledger": ledger["ledger"],
            "total_terms": ledger["total_terms"],
            "rules": ledger["rules"],
        }

    async def analyze_evidence(self, request: dict[str, Any]) -> dict[str, Any]:
        """分析证据链完整性（裸论断检测）"""
        content = request.get("content", "")

        # 工具层面的裸论断检测
        grammar_issues = self.tools_handler.check_grammar(content)
        naked_claims = [i for i in grammar_issues if i.get("type") == "evidence"]

        # LLM 深度分析
        prompt = f"请分析以下论文内容的证据链完整性：\n\n{content[:8000]}"
        llm_analysis = await self.call_llm(
            prompt,
            EVIDENCE_CHAIN_PROMPT,
            temperature=self._DETERMINISTIC_TEMPERATURE,
            user_api_key=request.get("_user_api_key"),
            user_api_base_url=request.get("_user_api_base_url"),
            user_api_model=request.get("_user_api_model"),
        )

        return {
            "naked_claims": naked_claims,
            "llm_analysis": llm_analysis,
            "total_naked_claims": len(naked_claims),
        }

    async def _handle_cite(self, request: dict[str, Any]) -> dict[str, Any]:
        """引用插入 + 参考文献生成

        request: {text, citations}
        返回: {text_with_citations, reference_list, citation_order}
        """
        text = request.get("text", "")
        citations = request.get("citations", [])

        text_with_citations = self.tools_handler.insert_citations(text, citations)
        citation_order = list(self.tools_handler._last_citation_order)
        reference_list = self.tools_handler.build_reference_list(citations, style="apa")

        return {
            "text_with_citations": text_with_citations,
            "reference_list": reference_list,
            "citation_order": citation_order,
        }

    async def _handle_export(self, request: dict[str, Any]) -> dict[str, Any]:
        """统一导出手稿或文献

        request: {manuscript 或 papers, format}
        返回: {format, content}
        """
        format = request.get("format", "")
        manuscript = request.get("manuscript")
        papers = request.get("papers")

        if manuscript is not None:
            content = self.tools_handler.export_manuscript(manuscript, format)
        elif papers is not None:
            content = self.tools_handler.export_papers(papers, format)
        else:
            raise AgentException("export 任务需要 manuscript 或 papers 参数", self.name)

        return {
            "format": format,
            "content": content,
        }

    @staticmethod
    def detect_section(task: str) -> list[str]:
        """检测目标章节（nature-writing section 轴）"""
        section_map = {
            "abstract": ["摘要", "abstract"],
            "intro": ["引言", "introduction", "intro"],
            "related-work": ["相关工作", "文献综述", "related work"],
            "method": ["方法", "method", "methodology"],
            "experiments": ["实验", "experiment", "results"],
            "discussion": ["讨论", "discussion"],
            "conclusion": ["结论", "conclusion"],
            "title": ["标题", "title"],
        }
        detected = []
        lower = task.lower()
        for section, keywords in section_map.items():
            if any(k in lower for k in keywords):
                detected.append(section)
        return detected or ["method"]

    @staticmethod
    def detect_language(text: str) -> str:
        """检测语言方向（nature-writing language 轴）"""
        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        return "zh-to-en" if chinese_chars > len(text) * 0.3 else "en"

    # Nature-writing: 8步显式工作流
    WRITING_WORKFLOW_STEPS = [
        "1_intake_claims",  # 收集作者声明/结果/图表/笔记
        "2_detect_axes",  # 检测 paper_type/section/language/journal
        "3_load_fragments",  # 按 manifest 加载对应静态片段
        "4_plan_argument",  # 写一句话论证链 (core_chain)
        "5_plan_drafting_order",  # 确定起草顺序 (drafting_order)
        "6_draft_section",  # 按顺序起草各节
        "7_check_evidence",  # 检查证据/边界缺失，标记 placeholder
        "8_output_with_flags",  # 输出 + 缺失标记列表
    ]

    @staticmethod
    def check_evidence_gaps(draft: str) -> list[str]:
        """Step 7: 检查证据/边界缺失，返回 placeholder 列表"""
        gaps = []
        markers = ["TODO", "FIXME", "PLACEHOLDER", "需要补充", "待补充"]
        for line_no, line in enumerate(draft.split("\n"), 1):
            for m in markers:
                if m in line:
                    gaps.append(f"L{line_no}: {line.strip()[:80]}")
        return gaps

    @staticmethod
    def fix_latex_layout(tex_source: str) -> dict[str, Any]:
        """LaTeX 排版修复：浮动体/稀疏页/跨页图表/Supplementary"""
        import re

        fixes = []
        # 1. Float too large → 添加 [H] 或 resize
        if re.search(r"\\begin\{figure\}(?!\[H\])", tex_source):
            fixes.append("建议在 figure 环境添加 [H] 选项防止浮动")
        # 2. Sparse pages → 添加 \clearpage
        if "supplementary" in tex_source.lower() and "\\clearpage" not in tex_source:
            fixes.append("Supplementary 前建议添加 \\clearpage")
        # 3. Stranded headings → 检查 \section/\subsection 后无内容
        # 正则匹配 \section{...} 含嵌套花括号（如 \section{The \textbf{X} method}），
        # 并覆盖 \subsection / \subsubsection / \paragraph 等分级标题
        sections = re.findall(
            r"\\(?:sub){0,2}section\*?\{((?:[^{}]|\{[^{}]*\})+)\}",
            tex_source,
        )
        for s in sections:
            fixes.append(f"检查 section '{s}' 是否孤立")
        return {"fixes": fixes, "total": len(fixes)}

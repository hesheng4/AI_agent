from typing import Any

from app.agents.base import BaseAgent
from app.agents.citation.prompts import (
    CITATION_SYSTEM_PROMPT,
    CLAIM_IDENTIFICATION_PROMPT,
    REFERENCE_FORMAT_PROMPT,
    SEGMENT_SPLITTING_PROMPT,
)
from app.services.citation_verification import verify_references
from app.utils.exceptions import AgentException
from app.utils.logger import get_logger

logger = get_logger("agent.citation")


class CitationAgent(BaseAgent):
    """Nature-skills 引用 Agent

    支持任务:
    - add-citations: 为文本添加引用
    - verify-citations: 验证现有引用
    - format-references: 格式化参考文献列表
    """

    # 引用类任务属确定性任务，低温保证 JSON 输出稳定与引用结果可复现
    _DETERMINISTIC_TEMPERATURE = 0.0

    def __init__(self) -> None:
        super().__init__(
            name="citation",
            tools=["add-citations", "verify-citations", "format-references"],
        )
        # 缓存任务分派表，避免每次 process 重建
        self._task_handlers = {
            "add-citations": self.add_citations,
            "verify-citations": self.verify_citations,
            "format-references": self.format_references,
        }

    async def process(self, request: dict[str, Any]) -> dict[str, Any]:
        task = str(request.get("task", ""))

        handler = self._task_handlers.get(task)
        if handler:
            return await handler(request)
        else:
            raise AgentException(f"未知任务类型: {task}", self.name)

    async def add_citations(self, request: dict[str, Any]) -> dict[str, Any]:
        """为文本添加引用"""
        content = request.get("content", "")
        journal_scope = request.get("journal_scope", "general")

        if not content.strip():
            raise AgentException("内容不能为空", self.name)

        # Step 1: 分割为可引用段落
        segment_prompt = f"{SEGMENT_SPLITTING_PROMPT}\n\n文本内容：\n{content[:6000]}"
        segments = await self.call_llm(
            segment_prompt,
            CITATION_SYSTEM_PROMPT,
            temperature=self._DETERMINISTIC_TEMPERATURE,
        )

        # Step 2: 识别需要引用的论断
        claim_prompt = f"{CLAIM_IDENTIFICATION_PROMPT}\n\n文本段落：\n{segments}"
        claims = await self.call_llm(
            claim_prompt,
            CITATION_SYSTEM_PROMPT,
            temperature=self._DETERMINISTIC_TEMPERATURE,
        )

        # Step 3: 为论断匹配引用并评估支撑等级
        citation_prompt = (
            f"请为以下论断建议引用文献（期刊范围：{journal_scope}）：\n\n"
            f"论断列表：\n{claims}\n\n"
            f"对每个论断，建议1-3条引用，标明支撑等级。\n"
            f"不编造不存在的文献，无法确认的标记为 [需确认]。"
        )
        citations = await self.call_llm(
            citation_prompt,
            CITATION_SYSTEM_PROMPT,
            temperature=self._DETERMINISTIC_TEMPERATURE,
        )

        # Step 4: 生成带引用的文本
        # 不再截断原文：前 3 步基于 content[:6000] 已识别完论断与引用，
        # 整合阶段需用完整原文，否则上标编号会与论断错位/丢失
        final_prompt = (
            f"请将以下引用整合到原文中，使用 Nature 上标编号格式：\n\n"
            f"原文：\n{content}\n\n"
            f"引用建议：\n{citations}"
        )
        annotated_text = await self.call_llm(
            final_prompt,
            CITATION_SYSTEM_PROMPT,
            temperature=self._DETERMINISTIC_TEMPERATURE,
        )

        return {
            "segments": segments,
            "claims": claims,
            "citations": citations,
            "annotated_text": annotated_text,
            "journal_scope": journal_scope,
        }

    async def verify_citations(self, request: dict[str, Any]) -> dict[str, Any]:
        """验证现有引用（外部实查 + LLM 论断判断）

        Step 1: 逐条外部实查（CrossRef/OpenAlex），不存在的文献/幻觉引用被打标；
        Step 2: LLM 基于实查结果做引用-论断支撑度判断。
        外部服务不可用时自动降级为纯 LLM 判断，不阻断流程。
        """
        content = request.get("content", "")
        references = request.get("references", [])

        if not content.strip():
            raise AgentException("内容不能为空", self.name)

        # 空引用列表直接返回，避免走无意义的 LLM 验证浪费 token
        if not references:
            return {
                "verification": "未提供参考文献，跳过验证",
                "total_references": 0,
                "verified_count": 0,
                "suspicious_count": 0,
                "per_reference": [],
            }

        # Step 1: 外部实查（网络失败/异常自动降级为 uncertain，不阻断）
        per_reference: list[dict[str, Any]] = []
        verified_count = 0
        suspicious_count = 0
        external_summary = ""
        try:
            results = await verify_references(references)
            per_reference = [r.to_dict() for r in results]
            verified_count = sum(
                1 for r in per_reference if r["status"] == "verified"
            )
            suspicious_count = sum(
                1 for r in per_reference if r["status"] != "verified"
            )
            lines = []
            for i, r in enumerate(per_reference):
                detail = f"[{i + 1}] {r['status']}: {r['reference']}"
                if r.get("matched_title"):
                    detail += f" → 匹配: {r['matched_title']}"
                    if r.get("matched_doi"):
                        detail += f" (DOI: {r['matched_doi']})"
                if r.get("issues"):
                    detail += f" ⚠ {'；'.join(r['issues'])}"
                lines.append(detail)
            external_summary = "\n".join(lines)
        except Exception as e:  # 外部服务异常不应阻断验证流程
            logger.warning("外部引用实查失败，降级为纯 LLM 判断: %s", e)
            external_summary = "外部实查不可用，以下为纯 LLM 判断结果。"

        # Step 2: LLM 论断-引用支撑度判断（附外部实查结果）
        refs_text = "\n".join(f"[{i + 1}] {r}" for i, r in enumerate(references))

        verify_prompt = (
            f"请验证以下文本中的引用是否与论断匹配：\n\n"
            f"文本：\n{content[:6000]}\n\n"
            f"参考文献：\n{refs_text}\n\n"
        )
        if external_summary:
            verify_prompt += (
                f"外部实查结果（CrossRef/OpenAlex 逐条存在性核查）：\n"
                f"{external_summary}\n\n"
                f"注意：status=not_found 表示该文献在 CrossRef/OpenAlex 中"
                f"不存在（高度疑似幻觉引用）；status=uncertain 表示未找到"
                f"强匹配文献。请结合此信息重点复核这些条目。\n\n"
            )
        verify_prompt += (
            "检查：\n"
            "1. 每个引用是否支撑对应的论断？\n"
            "2. 是否有论断缺少引用？\n"
            "3. 是否有不相关的引用？\n"
            "4. 引用格式是否一致？"
        )

        verification = await self.call_llm(
            verify_prompt,
            CITATION_SYSTEM_PROMPT,
            temperature=self._DETERMINISTIC_TEMPERATURE,
        )

        return {
            "verification": verification,
            "total_references": len(references),
            "verified_count": verified_count,
            "suspicious_count": suspicious_count,
            "per_reference": per_reference,
        }

    async def format_references(self, request: dict[str, Any]) -> dict[str, Any]:
        """格式化参考文献列表"""
        references: list[str] = request.get("references", [])
        style = request.get("style", "nature")

        if not references:
            raise AgentException("参考文献列表不能为空", self.name)

        refs_text = "\n".join(f"[{i + 1}] {r}" for i, r in enumerate(references))

        format_prompt = (
            f"{REFERENCE_FORMAT_PROMPT}\n\n目标格式：{style}\n\n参考文献：\n{refs_text}"
        )

        formatted = await self.call_llm(
            format_prompt,
            CITATION_SYSTEM_PROMPT,
            temperature=self._DETERMINISTIC_TEMPERATURE,
        )

        return {
            "formatted_references": formatted,
            "style": style,
            "total_references": len(references),
        }

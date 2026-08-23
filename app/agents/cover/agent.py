"""Nature-skills 驱动的投稿信 Agent

支持任务:
- draft: 起草投稿信（hook → gap → advance → significance → fit → declarations）
- audit: 审计现有投稿信的desk-reject风险
- presubmission: 起草presubmission enquiry
"""

from typing import Any

from app.agents.base import BaseAgent
from app.agents.cover.prompts import (
    COVER_AUDIT_PROMPT,
    COVER_DRAFT_PROMPT,
    COVER_PRESUBMISSION_PROMPT,
)
from app.utils.exceptions import AgentException


class CoverAgent(BaseAgent):
    """Nature-skills 驱动的投稿信 Agent"""

    # 投稿信属半确定性任务（同输入应产出稳定结构），低温保证格式与措辞可复现
    _DETERMINISTIC_TEMPERATURE = 0.0

    def __init__(self):
        super().__init__(
            name="cover",
            tools=["draft", "audit", "presubmission"],
        )
        # 缓存任务分派表，避免每次 process 重建
        self._handlers = {
            "draft": self.draft,
            "audit": self.audit,
            "presubmission": self.presubmission,
        }

    async def process(self, request: dict[str, Any]) -> dict[str, Any]:
        task = request.get("task") or "draft"
        handler = self._handlers.get(task)
        if handler:
            return await handler(request)
        raise AgentException(f"未知任务类型: {task}", self.name)

    async def draft(self, request: dict[str, Any]) -> dict[str, Any]:
        """起草投稿信"""
        title = request.get("title", "")
        abstract = request.get("abstract", "")
        key_result = request.get("key_result", "")
        journal = request.get("journal", "")
        significance = request.get("significance", "")

        # 起草至少需要标题或摘要之一，避免空输入浪费 LLM token
        if not (title.strip() or abstract.strip()):
            raise AgentException("起草投稿信至少需要 title 或 abstract", self.name)

        prompt = (
            f"起草Nature风格投稿信：\n"
            f"论文标题：{title}\n"
            f"目标期刊：{journal or '[AUTHOR_INPUT: 目标期刊]'}\n"
            f"关键结果：{key_result}\n"
            f"显著性：{significance}\n\n"
            f"摘要：{abstract}\n\n"
            f"架构：hook → gap → advance → significance → fit → declarations\n"
            f"长度预算：250-500词，一页"
        )
        result = await self.call_llm(
            prompt,
            COVER_DRAFT_PROMPT,
            temperature=self._DETERMINISTIC_TEMPERATURE,
            user_api_key=request.get("_user_api_key"),
            user_api_base_url=request.get("_user_api_base_url"),
            user_api_model=request.get("_user_api_model"),
        )
        return {"cover_letter": result, "journal": journal}

    async def audit(self, request: dict[str, Any]) -> dict[str, Any]:
        """审计投稿信desk-reject风险"""
        content = request.get("content", "")
        journal = request.get("journal", "")

        if not content.strip():
            raise AgentException("审计内容不能为空", self.name)

        prompt = (
            f"审计以下投稿信的desk-reject风险：\n"
            f"目标期刊：{journal or '未指定'}\n\n{content}"
        )
        result = await self.call_llm(
            prompt,
            COVER_AUDIT_PROMPT,
            temperature=self._DETERMINISTIC_TEMPERATURE,
            user_api_key=request.get("_user_api_key"),
            user_api_base_url=request.get("_user_api_base_url"),
            user_api_model=request.get("_user_api_model"),
        )
        return {"audit": result}

    async def presubmission(self, request: dict[str, Any]) -> dict[str, Any]:
        """起草presubmission enquiry"""
        title = request.get("title", "")
        abstract = request.get("abstract", "")
        journal = request.get("journal", "")

        if not (title.strip() or abstract.strip()):
            raise AgentException(
                "presubmission enquiry 至少需要 title 或 abstract", self.name
            )

        prompt = (
            f"起草presubmission enquiry邮件：\n"
            f"论文标题：{title}\n"
            f"目标期刊：{journal or '[AUTHOR_INPUT: 目标期刊]'}\n\n"
            f"摘要：{abstract}"
        )
        result = await self.call_llm(
            prompt,
            COVER_PRESUBMISSION_PROMPT,
            temperature=self._DETERMINISTIC_TEMPERATURE,
            user_api_key=request.get("_user_api_key"),
            user_api_base_url=request.get("_user_api_base_url"),
            user_api_model=request.get("_user_api_model"),
        )
        return {"presubmission_enquiry": result}

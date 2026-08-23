"""Nature-skills 驱动的 Methods 可复现性 Agent

支持任务:
- audit: 审计Methods可复现性+合规（材料标识符、伦理声明、禁用短语）
- draft: 从作者笔记起草Methods文本
- check_ethics: 伦理/审批/知情同意声明审计
- remove_vague: 禁用模糊短语替换
"""

from typing import Any

from app.agents.base import BaseAgent
from app.agents.methods.prompts import (
    ETHICS_CHECK_PROMPT,
    METHODS_AUDIT_PROMPT,
    METHODS_DRAFT_PROMPT,
    VAGUE_REMOVAL_PROMPT,
)
from app.utils.exceptions import AgentException


class MethodsAgent(BaseAgent):
    """Nature-skills 驱动的 Methods 可复现性 Agent"""

    def __init__(self):
        super().__init__(
            name="methods",
            tools=["audit", "draft", "check_ethics", "remove_vague"],
        )

    async def process(self, request: dict[str, Any]) -> dict[str, Any]:
        task = request.get("task", "audit")

        handlers = {
            "audit": self.audit,
            "draft": self.draft,
            "check_ethics": self.check_ethics,
            "remove_vague": self.remove_vague,
        }
        handler = handlers.get(task)
        if handler:
            return await handler(request)
        raise AgentException(f"未知任务类型: {task}", self.name)

    async def audit(self, request: dict[str, Any]) -> dict[str, Any]:
        """审计Methods可复现性+合规"""
        content = request.get("content", "")
        study_type = request.get("study_type", "experimental")
        journal = request.get("journal", "nature")

        prompt = (
            f"审计以下Methods部分的可复现性与合规性：\n"
            f"研究类型：{study_type}\n"
            f"目标期刊：{journal}\n\n"
            f"检查项：材料标识符(供应商/目录号/RRID)、设备参数、对照、"
            f"重复定义、软件版本、rigor元素(随机化/盲法/纳入排除)、"
            f"伦理声明、禁用模糊短语\n\n{content}"
        )
        result = await self.call_llm(
            prompt,
            METHODS_AUDIT_PROMPT,
            temperature=0.0,
            user_api_key=request.get("_user_api_key"),
            user_api_base_url=request.get("_user_api_base_url"),
            user_api_model=request.get("_user_api_model"),
        )
        return {"audit": result, "study_type": study_type}

    async def draft(self, request: dict[str, Any]) -> dict[str, Any]:
        """从作者笔记起草Methods文本"""
        notes = request.get("content", "")
        study_type = request.get("study_type", "experimental")
        journal = request.get("journal", "nature")

        prompt = (
            f"根据以下实验笔记起草Nature风格Methods文本：\n"
            f"研究类型：{study_type}\n"
            f"目标期刊：{journal}\n\n{notes}"
        )
        result = await self.call_llm(
            prompt,
            METHODS_DRAFT_PROMPT,
            temperature=0.0,
            user_api_key=request.get("_user_api_key"),
            user_api_base_url=request.get("_user_api_base_url"),
            user_api_model=request.get("_user_api_model"),
        )
        return {"draft": result}

    async def check_ethics(self, request: dict[str, Any]) -> dict[str, Any]:
        """伦理/审批/知情同意声明审计"""
        content = request.get("content", "")
        study_type = request.get("study_type", "experimental")

        prompt = (
            f"审计以下Methods的伦理声明完整性：\n"
            f"研究类型：{study_type}\n"
            f"检查：审批机构、批号、知情同意、动物伦理、生物安全\n\n{content}"
        )
        result = await self.call_llm(
            prompt,
            ETHICS_CHECK_PROMPT,
            temperature=0.0,
            user_api_key=request.get("_user_api_key"),
            user_api_base_url=request.get("_user_api_base_url"),
            user_api_model=request.get("_user_api_model"),
        )
        return {"ethics_check": result}

    async def remove_vague(self, request: dict[str, Any]) -> dict[str, Any]:
        """禁用模糊短语替换"""
        content = request.get("content", "")
        prompt = (
            "替换以下Methods文本中的模糊短语：\n"
            "禁用：'standard conditions', 'routine methods', "
            f"'data were analysed statistically', "
            f"'as described previously' (无引用)\n\n{content}"
        )
        result = await self.call_llm(
            prompt,
            VAGUE_REMOVAL_PROMPT,
            temperature=0.0,
            user_api_key=request.get("_user_api_key"),
            user_api_base_url=request.get("_user_api_base_url"),
            user_api_model=request.get("_user_api_model"),
        )
        return {"revised": result}

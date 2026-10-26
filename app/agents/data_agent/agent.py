from typing import Any

from app.agents.base import BaseAgent
from app.agents.data_agent.prompts import (
    DATA_SYSTEM_PROMPT,
    FAIR_AUDIT_PROMPT,
    REPOSITORY_SELECTION_PROMPT,
    STATEMENT_GENERATION_PROMPT,
)
from app.utils.exceptions import AgentException


class DataAvailabilityAgent(BaseAgent):
    """Nature-skills 数据可用性 Agent

    支持任务:
    - generate-statement: 生成数据可用性声明
    - audit-statement: 审计 FAIR 合规性
    - select-repository: 推荐数据仓库
    """

    # 数据可用性声明属半确定性任务，低温保证输出可复现
    _DETERMINISTIC_TEMPERATURE = 0.0

    def __init__(self) -> None:
        super().__init__(
            name="data_agent",
            tools=["generate-statement", "audit-statement", "select-repository"],
        )
        # 缓存任务分派表，避免每次 process 重建
        self._task_handlers = {
            "generate-statement": self.generate_statement,
            "audit-statement": self.audit_statement,
            "select-repository": self.select_repository,
        }

    async def process(self, request: dict[str, Any]) -> dict[str, Any]:
        task = str(request.get("task", ""))
        handler = self._task_handlers.get(task)
        if handler:
            return await handler(request)
        raise AgentException(f"未知任务类型: {task!r}", self.name)

    async def generate_statement(self, request: dict[str, Any]) -> dict[str, Any]:
        """生成数据可用性声明"""
        data_description = request.get("data_description", "")
        repository_type = request.get("repository_type", "")
        restrictions = request.get("restrictions", "")
        journal = request.get("journal", "nature")

        if not data_description.strip():
            raise AgentException("数据描述不能为空", self.name)

        prompt = (
            f"{STATEMENT_GENERATION_PROMPT}\n\n"
            f"数据描述：\n{data_description}\n\n"
            f"仓库类型：{repository_type or '待推荐'}\n\n"
        )
        if restrictions:
            prompt += f"访问限制：{restrictions}\n\n"
        prompt += f"期刊：{journal}\n\n"
        prompt += (
            "请生成符合 Nature 规范的数据可用性声明，"
            "缺失信息用 AUTHOR_INPUT_NEEDED 标记。"
        )

        statement = await self.call_llm(
            prompt,
            DATA_SYSTEM_PROMPT,
            temperature=self._DETERMINISTIC_TEMPERATURE,
        )

        return {
            "statement": statement,
            "journal": journal,
            "has_restrictions": bool(restrictions),
        }

    async def audit_statement(self, request: dict[str, Any]) -> dict[str, Any]:
        """审计 FAIR 合规性"""
        statement = request.get("statement", "")

        if not statement.strip():
            raise AgentException("数据可用性声明不能为空", self.name)

        audit_prompt = f"{FAIR_AUDIT_PROMPT}\n\n数据可用性声明：\n{statement}"

        audit_result = await self.call_llm(
            audit_prompt,
            DATA_SYSTEM_PROMPT,
            temperature=self._DETERMINISTIC_TEMPERATURE,
        )

        return {"audit_result": audit_result, "fair_compliance": "pending_review"}

    async def select_repository(self, request: dict[str, Any]) -> dict[str, Any]:
        """推荐数据仓库"""
        data_type = request.get("data_type", "")
        data_size = request.get("data_size", "")
        access_control = request.get("access_control", "open")

        if not data_type.strip():
            raise AgentException("数据类型不能为空", self.name)

        prompt = (
            f"{REPOSITORY_SELECTION_PROMPT}\n\n"
            f"数据类型：{data_type}\n"
            f"数据大小：{data_size or '未知'}\n"
            f"访问控制需求：{access_control}\n\n"
            f"请推荐最合适的数据仓库，给出首选和备选，并说明理由。"
        )

        recommendation = await self.call_llm(
            prompt,
            DATA_SYSTEM_PROMPT,
            temperature=self._DETERMINISTIC_TEMPERATURE,
        )

        return {
            "recommendation": recommendation,
            "data_type": data_type,
            "access_control": access_control,
        }

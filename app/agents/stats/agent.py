"""Nature-skills 驱动的统计报告 Agent

支持任务:
- audit: 审计现有统计报告（Results/图例/Methods统计段）
- draft: 起草合规统计声明（图例n/test/dispersion行、Methods统计段）
- check_test: 检验选择合理性审计
- check_multiple: 多重比较校正审计
"""

from typing import Any

from app.agents.base import BaseAgent
from app.agents.stats.prompts import (
    MULTIPLE_COMPARISON_PROMPT,
    STATS_AUDIT_PROMPT,
    STATS_DRAFT_PROMPT,
    TEST_SELECTION_PROMPT,
)
from app.utils.exceptions import AgentException


class StatsAgent(BaseAgent):
    """Nature-skills 驱动的统计报告 Agent"""

    def __init__(self) -> None:
        super().__init__(
            name="stats",
            tools=[
                "audit",
                "draft",
                "check_test",
                "check_multiple",
            ],
        )

    async def process(self, request: dict[str, Any]) -> dict[str, Any]:
        task = request.get("task", "audit")

        handlers = {
            "audit": self.audit,
            "draft": self.draft,
            "check_test": self.check_test,
            "check_multiple": self.check_multiple,
        }
        handler = handlers.get(task)
        if handler:
            return await handler(request)
        raise AgentException(f"未知任务类型: {task}", self.name)

    async def audit(self, request: dict[str, Any]) -> dict[str, Any]:
        """审计现有统计报告"""
        content = request.get("content", "")
        # results / figure_legend / methods
        location = request.get("location", "results")
        journal = request.get("journal", "nature")

        prompt = (
            f"审计以下统计报告，找出所有不合规项：\n"
            f"报告位置：{location}\n"
            f"目标期刊：{journal}\n\n"
            f"检查项：精确p值、效应量+CI、样本量定义、误差棒含义、"
            f"检验选择合理性、多重比较校正、不编造\n\n{content}"
        )
        result = await self.call_llm(
            prompt,
            STATS_AUDIT_PROMPT,
            temperature=0.0,
            user_api_key=request.get("_user_api_key"),
            user_api_base_url=request.get("_user_api_base_url"),
            user_api_model=request.get("_user_api_model"),
        )
        return {"audit": result, "location": location}

    async def draft(self, request: dict[str, Any]) -> dict[str, Any]:
        """起草合规统计声明"""
        content = request.get("content", "")
        location = request.get("location", "figure_legend")
        journal = request.get("journal", "nature")

        prompt = (
            f"根据以下信息起草Nature风格统计声明：\n"
            f"声明位置：{location}\n"
            f"目标期刊：{journal}\n\n{content}"
        )
        result = await self.call_llm(
            prompt,
            STATS_DRAFT_PROMPT,
            temperature=0.0,
            user_api_key=request.get("_user_api_key"),
            user_api_base_url=request.get("_user_api_base_url"),
            user_api_model=request.get("_user_api_model"),
        )
        return {"draft": result, "location": location}

    async def check_test(self, request: dict[str, Any]) -> dict[str, Any]:
        """检验选择合理性审计"""
        content = request.get("content", "")
        prompt = (
            "审计以下统计检验选择的合理性"
            "（配对/非配对、单侧/双侧、参数/非参数）：\n\n"
            f"{content}"
        )
        result = await self.call_llm(
            prompt,
            TEST_SELECTION_PROMPT,
            temperature=0.0,
            user_api_key=request.get("_user_api_key"),
            user_api_base_url=request.get("_user_api_base_url"),
            user_api_model=request.get("_user_api_model"),
        )
        return {"test_check": result}

    async def check_multiple(self, request: dict[str, Any]) -> dict[str, Any]:
        """多重比较校正审计"""
        content = request.get("content", "")
        prompt = f"审计以下多重比较校正是否充分，命名校正方法及其适用族：\n\n{content}"
        result = await self.call_llm(
            prompt,
            MULTIPLE_COMPARISON_PROMPT,
            temperature=0.0,
            user_api_key=request.get("_user_api_key"),
            user_api_base_url=request.get("_user_api_base_url"),
            user_api_model=request.get("_user_api_model"),
        )
        return {"multiple_comparison_check": result}

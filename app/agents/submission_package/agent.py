"""Nature-skills 投稿包组装 Agent"""

from typing import Any

from app.agents.base import BaseAgent
from app.agents.submission_package.prompts import (
    SUBPKG_SYSTEM_PROMPT,
    SUBPKG_WORKFLOW_STEPS,
)
from app.utils.exceptions import AgentException


class SubmissionPackageAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="submission_package",
            tools=["match_journal", "checklist", "consistency_check"],
        )

    async def process(self, request: dict[str, Any]) -> dict[str, Any]:
        task = request.get("task", "checklist")
        handlers = {
            "match_journal": self.match_journal,
            "checklist": self.checklist,
            "consistency_check": self.consistency_check,
        }
        handler = handlers.get(task)
        if handler:
            return await handler(request)
        raise AgentException(f"未知任务类型: {task}", self.name)

    async def match_journal(self, request):
        abstract = request.get("abstract", "")
        prompt = (
            "根据摘要推荐 Nature Portfolio 候选期刊"
            "（含 scope-fit 理由）：\n\n"
            f"{abstract[:4000]}"
        )
        result = await self.call_llm(
            prompt,
            SUBPKG_SYSTEM_PROMPT,
            temperature=0.0,
            user_api_key=request.get("_user_api_key"),
            user_api_base_url=request.get("_user_api_base_url"),
            user_api_model=request.get("_user_api_model"),
        )
        return {"journal_matches": result}

    async def checklist(self, request):
        journal = request.get("journal", "nature")
        artefacts = request.get("artefacts", {})
        prompt = (
            f"生成 {journal} 投稿清单，标记已有项✓/缺失项✗/需确认⚠，"
            f"路由缺失项到对应 skill：\n已有材料：{artefacts}"
        )
        result = await self.call_llm(
            prompt,
            SUBPKG_SYSTEM_PROMPT,
            temperature=0.0,
            user_api_key=request.get("_user_api_key"),
            user_api_base_url=request.get("_user_api_base_url"),
            user_api_model=request.get("_user_api_model"),
        )
        return {"checklist": result}

    async def consistency_check(self, request):
        artefacts = request.get("artefacts", {})
        prompt = (
            "跨件一致性检查（C1期刊名/C2图数量/C3作者/C4统计方法/"
            "C5数据可用性/C6伦理/C7扩展数据）：\n"
            f"{artefacts}"
        )
        result = await self.call_llm(
            prompt,
            SUBPKG_SYSTEM_PROMPT,
            temperature=0.0,
            user_api_key=request.get("_user_api_key"),
            user_api_base_url=request.get("_user_api_base_url"),
            user_api_model=request.get("_user_api_model"),
        )
        return {"consistency": result}

    WORKFLOW_STEPS = SUBPKG_WORKFLOW_STEPS

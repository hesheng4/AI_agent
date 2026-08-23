import json
import re
from typing import Any

from app.agents.base import BaseAgent
from app.agents.reviewer.prompts import (
    FACT_BASE_EXTRACTION_PROMPT,
    QUICK_CHECK_PROMPT,
    REVIEW_SCORE_PROMPT,
    REVIEWER_SYSTEM_PROMPT,
    STRUCTURED_REVIEW_EXTRACTION_PROMPT,
)
from app.utils.exceptions import AgentException


class ReviewerAgent(BaseAgent):
    """Nature-skills 模拟审稿 Agent

    支持任务:
    - assess: 完整审稿评估（3审稿人 + 交叉综述）
    - score: 对审稿结果量化评分（H1 迭代闭环停止条件）
    - quick-check: 快速预审检查
    """

    def __init__(self):
        super().__init__(name="reviewer", tools=["assess", "score", "quick-check"])

    async def process(self, request: dict[str, Any]) -> dict[str, Any]:
        task = request.get("task")

        task_handlers = {
            "assess": self.assess,
            "score": self.score,
            "quick-check": self.quick_check,
        }

        handler = task_handlers.get(task)
        if handler:
            return await handler(request)
        else:
            raise AgentException(f"未知任务类型: {task}", self.name)

    async def assess(self, request: dict[str, Any]) -> dict[str, Any]:
        """完整审稿评估（3审稿人 + 交叉综述）"""
        content = request.get("content", "")
        paper_type = request.get("paper_type", "research")
        input_scope = request.get("input_scope", "full manuscript")

        if not content.strip():
            raise AgentException("稿件内容不能为空", self.name)

        # Step 1: 提取事实基础
        fact_base_prompt = (
            f"{FACT_BASE_EXTRACTION_PROMPT}\n\n稿件内容：\n{content[:8000]}"
        )
        fact_base = await self.call_llm(
            fact_base_prompt, REVIEWER_SYSTEM_PROMPT, temperature=0.0
        )

        # Step 2: 生成3审稿人报告 + 交叉综述
        assessment_prompt = (
            f"请基于以下事实基础，生成3份审稿人报告和1份交叉综述：\n\n"
            f"论文类型：{paper_type}\n"
            f"输入范围：{input_scope}\n"
            f"稿件内容：\n{content[:8000]}\n\n"
            f"事实基础：\n{fact_base}\n\n"
            f"请确保三位审稿人分别侧重：\n"
            f"- 审稿人1：技术严谨性\n"
            f"- 审稿人2：新颖性与影响力\n"
            f"- 审稿人3：跨学科影响力与可读性\n\n"
            f"严格遵循输出格式，不要编造实验、引用或审稿人身份。"
        )

        review_result = await self.call_llm(
            assessment_prompt, REVIEWER_SYSTEM_PROMPT, temperature=0.0
        )

        # Step 3: 结构化提取「优缺点+改进建议」（B3：投稿前自检 + 审稿回复串联）
        structured = await self._extract_structured(review_result)

        return {
            "fact_base": fact_base,
            "review_result": review_result,
            "strengths": structured.get("strengths", []),
            "improvement_suggestions": structured.get("improvement_suggestions", []),
            "paper_type": paper_type,
            "input_scope": input_scope,
        }

    async def _extract_structured(self, review_result: str) -> dict[str, Any]:
        """从审稿结果提取结构化优缺点+改进建议（容错 JSON 解析）"""
        try:
            raw = await self.call_llm(
                f"{STRUCTURED_REVIEW_EXTRACTION_PROMPT}\n\n审稿结果：\n{review_result[:12000]}",
                REVIEWER_SYSTEM_PROMPT,
                temperature=0.0,
            )
        except Exception:
            return {"strengths": [], "improvement_suggestions": []}
        return self._parse_structured(raw)

    @staticmethod
    def _parse_structured(raw: str) -> dict[str, Any]:
        """容错解析 LLM 返回的 JSON（剥离代码块围栏/前后杂文）"""
        if not raw or not raw.strip():
            return {"strengths": [], "improvement_suggestions": []}
        text = raw.strip()
        # 剥离 ```json ... ``` 代码块围栏
        fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
        if fence:
            text = fence.group(1).strip()
        # 提取首个 JSON 对象
        obj_match = re.search(r"\{.*\}", text, re.S)
        if not obj_match:
            return {"strengths": [], "improvement_suggestions": []}
        try:
            data = json.loads(obj_match.group(0))
        except json.JSONDecodeError:
            return {"strengths": [], "improvement_suggestions": []}
        strengths = data.get("strengths") or []
        suggestions = data.get("improvement_suggestions") or []
        return {
            "strengths": [s.get("text", "") for s in strengths if isinstance(s, dict)],
            "improvement_suggestions": suggestions,
        }

    async def score(self, request: dict[str, Any]) -> dict[str, Any]:
        """对审稿结果量化评分（H1 迭代闭环停止条件）

        输入 review_result（assess 的审稿文本），LLM 按 5 维度打分，
        返回 overall（0-10，1 位小数）与各维度分。
        """
        review_result = request.get("review_result", "")
        if not review_result.strip():
            raise AgentException("审稿结果不能为空", self.name)
        try:
            raw = await self.call_llm(
                f"{REVIEW_SCORE_PROMPT}\n\n审稿结果：\n{review_result[:12000]}",
                REVIEWER_SYSTEM_PROMPT,
                temperature=0.0,
            )
        except Exception:
            return {"overall": None, "axes": {}}
        return self._parse_score(raw)

    @staticmethod
    def _parse_score(raw: str) -> dict[str, Any]:
        """容错解析评分 JSON（剥离代码块围栏/前后杂文）"""
        empty = {"overall": None, "axes": {}}
        if not raw or not raw.strip():
            return empty
        text = raw.strip()
        fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
        if fence:
            text = fence.group(1).strip()
        obj_match = re.search(r"\{.*\}", text, re.S)
        if not obj_match:
            return empty
        try:
            data = json.loads(obj_match.group(0))
        except json.JSONDecodeError:
            return empty
        axes = {
            key: data[key]
            for key in (
                "originality",
                "importance",
                "readership",
                "soundness",
                "readability",
            )
            if isinstance(data.get(key), (int, float))
        }
        overall = data.get("overall")
        if not isinstance(overall, (int, float)):
            overall = round(sum(axes.values()) / len(axes), 1) if axes else None
        else:
            overall = round(float(overall), 1)
        return {"overall": overall, "axes": axes}

    async def quick_check(self, request: dict[str, Any]) -> dict[str, Any]:
        """快速预审检查"""
        content = request.get("content", "")
        paper_type = request.get("paper_type", "research")

        if not content.strip():
            raise AgentException("稿件内容不能为空", self.name)

        prompt = (
            f"{QUICK_CHECK_PROMPT}\n\n论文类型：{paper_type}\n\n"
            f"稿件内容：\n{content[:6000]}"
        )

        quick_result = await self.call_llm(
            prompt, REVIEWER_SYSTEM_PROMPT, temperature=0.0
        )

        return {"quick_check": quick_result, "paper_type": paper_type}

    # Nature-reviewer: 结构化输出格式
    REVIEWER_OUTPUT_SCHEMA = {
        "review_setup": [
            "input_scope",
            "assessment_boundary",
            "claim_summary",
            "evidence_base",
            "missing_materials",
        ],
        "reviewer_1": [
            "overall",
            "interested_audience",
            "strengths",
            "concerns",
            "technical_failings",
            "criteria_assessment",
            "recommendation",
        ],
        "reviewer_2": [
            "overall",
            "interested_audience",
            "strengths",
            "concerns",
            "technical_failings",
            "criteria_assessment",
            "recommendation",
        ],
        "reviewer_3": [
            "overall",
            "interested_audience",
            "strengths",
            "concerns",
            "technical_failings",
            "criteria_assessment",
            "recommendation",
        ],
        "cross_review": [
            "consensus_strengths",
            "consensus_risks",
            "emphasis_differences",
            "significance_readout",
            "key_issues_to_resolve",
        ],
        "risk_unsupported": ["items"],
    }

    @staticmethod
    def qa_check(review_result: dict) -> dict:
        """QA 检查：groundedness/coverage/role/non-invention"""
        issues = []
        if "cross_review" not in review_result:
            issues.append("缺少交叉综述")
        if "risk_unsupported" not in review_result:
            issues.append("缺少风险/未支撑声明")
        return {"passed": len(issues) == 0, "issues": issues}

from typing import Any

from app.agents.base import BaseAgent
from app.agents.response.prompts import (
    COMMENT_CLASSIFICATION_PROMPT,
    RESPONSE_SYSTEM_PROMPT,
    TONE_AUDIT_PROMPT,
)
from app.utils.exceptions import AgentException


class ResponseAgent(BaseAgent):
    """Nature-skills 审稿回复 Agent

    支持任务:
    - draft: 起草逐点回复信
    - audit: 审计已有回复的完整性和语气
    - revise: 修改回复信
    """

    def __init__(self):
        super().__init__(name="response", tools=["draft", "audit", "revise"])

    async def process(self, request: dict[str, Any]) -> dict[str, Any]:
        task = request.get("task")

        task_handlers = {
            "draft": self.draft,
            "audit": self.audit,
            "revise": self.revise,
        }

        handler = task_handlers.get(task)
        if handler:
            return await handler(request)
        else:
            raise AgentException(f"未知任务类型: {task}", self.name)

    async def draft(self, request: dict[str, Any]) -> dict[str, Any]:
        """起草逐点回复信"""
        reviewer_comments: list[str] = request.get("reviewer_comments", [])
        decision_type = request.get("decision_type", "major")
        manuscript_content = request.get("manuscript_content", "")
        user_notes = request.get("user_notes", "")
        review_result = request.get("review_result")

        # B3 串联：未直接提供意见时，从 reviewer 结构化结果派生
        if not reviewer_comments and review_result:
            derived = self._derive_comments(review_result)
            reviewer_comments = derived.get("reviewer_comments", [])
            derived_decision = derived.get("decision_type")
            if derived_decision and not request.get("decision_type"):
                decision_type = derived_decision

        if not reviewer_comments:
            raise AgentException("审稿意见不能为空", self.name)

        # Step 1: 分类审稿意见
        comments_text = "\n".join(
            f"意见 {i + 1}: {c}" for i, c in enumerate(reviewer_comments)
        )
        classification_prompt = (
            f"{COMMENT_CLASSIFICATION_PROMPT}\n\n审稿意见：\n{comments_text}"
        )
        classification = await self.call_llm(
            classification_prompt, RESPONSE_SYSTEM_PROMPT, temperature=0.0
        )

        # Step 2: 起草逐点回复
        draft_prompt = (
            f"请为以下审稿意见起草逐点回复：\n\n"
            f"决策类型：{decision_type}\n\n"
            f"审稿意见：\n{comments_text}\n\n"
            f"意见分类结果：\n{classification}\n\n"
        )
        if manuscript_content:
            draft_prompt += f"稿件内容摘要：\n{manuscript_content[:4000]}\n\n"
        if user_notes:
            draft_prompt += f"作者备注：\n{user_notes}\n\n"

        draft_prompt += (
            "请严格按输出格式起草回复，不要编造实验或引用，"
            "需要作者补充的信息标记为 AUTHOR_INPUT_NEEDED。"
        )

        response_letter = await self.call_llm(
            draft_prompt, RESPONSE_SYSTEM_PROMPT, temperature=0.0
        )

        return {
            "classification": classification,
            "response_letter": response_letter,
            "decision_type": decision_type,
            "total_comments": len(reviewer_comments),
        }

    @staticmethod
    def _derive_comments(review_result: dict) -> dict:
        """从 reviewer 结构化结果（improvement_suggestions）派生审稿意见与决策类型

        B3 串联：reviewer.assess 输出的 improvement_suggestions 每项含
        issue/location/suggestion/severity/category，转成回复 Agent 的逐条意见列表，
        并按 major 意见数量推断决策类型（major 意见存在 → major，否则 minor）。
        """
        suggestions = review_result.get("improvement_suggestions") or []
        comments: list[str] = []
        for idx, item in enumerate(suggestions, start=1):
            if not isinstance(item, dict):
                continue
            issue = str(item.get("issue", "")).strip()
            if not issue:
                continue
            severity = str(item.get("severity", "minor"))
            location = str(item.get("location", "")).strip()
            line = f"[{severity}] {issue}"
            if location and location != "全文":
                line += f"（{location}）"
            comments.append(line)

        major_count = sum(1 for c in comments if c.startswith("[major]"))
        decision_type = "major" if major_count > 0 else "minor"
        return {"reviewer_comments": comments, "decision_type": decision_type}

    async def audit(self, request: dict[str, Any]) -> dict[str, Any]:
        """审计已有回复的完整性和语气"""
        response_content = request.get("response_content", "")
        reviewer_comments: list[str] = request.get("reviewer_comments", [])

        if not response_content.strip():
            raise AgentException("回复内容不能为空", self.name)

        comments_text = (
            "\n".join(f"意见 {i + 1}: {c}" for i, c in enumerate(reviewer_comments))
            if reviewer_comments
            else "（未提供原审稿意见）"
        )

        audit_prompt = (
            f"{TONE_AUDIT_PROMPT}\n\n"
            f"审稿意见：\n{comments_text}\n\n"
            f"回复内容：\n{response_content[:8000]}"
        )

        audit_result = await self.call_llm(
            audit_prompt, RESPONSE_SYSTEM_PROMPT, temperature=0.0
        )

        return {"audit_result": audit_result, "total_comments": len(reviewer_comments)}

    async def revise(self, request: dict[str, Any]) -> dict[str, Any]:
        """修改回复信"""
        response_content = request.get("response_content", "")
        feedback = request.get("feedback", "")
        reviewer_comments: list[str] = request.get("reviewer_comments", [])

        if not response_content.strip():
            raise AgentException("回复内容不能为空", self.name)
        if not feedback.strip():
            raise AgentException("修改反馈不能为空", self.name)

        comments_text = (
            "\n".join(f"意见 {i + 1}: {c}" for i, c in enumerate(reviewer_comments))
            if reviewer_comments
            else ""
        )

        revise_prompt = (
            f"请根据反馈修改以下审稿回复：\n\n"
            f"原审稿意见：\n{comments_text}\n\n"
            f"当前回复：\n{response_content[:6000]}\n\n"
            f"修改反馈：\n{feedback}\n\n"
            f"请保持输出格式一致，不要编造内容。"
        )

        revised = await self.call_llm(
            revise_prompt, RESPONSE_SYSTEM_PROMPT, temperature=0.0
        )

        return {"revised_response": revised, "feedback_applied": feedback[:200]}

    # Nature-response: 10 步工作流
    WORKFLOW_STEPS = [
        "1_identify_mode",
        "2_extract_editor_items",
        "3_extract_reviewer_items",
        "4_classify_items",
        "5_build_strategy",
        "6_draft_point_by_point",
        "7_map_changes_to_locations",
        "8_flag_missing_input",
        "9_run_qa",
        "10_package_output",
    ]

    @staticmethod
    def assign_item_ids(comments: list[dict]) -> list[dict]:
        """为 editor/reviewer 意见分配结构化 ID (E.1, R1.1, R2.1)"""
        result = []
        e_count = 0
        r_counts: dict[int, int] = {}
        for item in comments:
            role = item.get("role", "reviewer")
            reviewer_num = item.get("reviewer_number", 1)
            if role == "editor":
                e_count += 1
                item["item_id"] = f"E.{e_count}"
            else:
                r_counts[reviewer_num] = r_counts.get(reviewer_num, 0) + 1
                item["item_id"] = f"R{reviewer_num}.{r_counts[reviewer_num]}"
            result.append(item)
        return result

    async def run_10_step_workflow(self, request: dict) -> dict:
        """完整10步工作流实现"""
        # Step 1: 识别模式
        mode = request.get("task_mode", "draft")
        decision_type = request.get("decision_type", "major_revision")
        # Step 2-3: 提取 editor + reviewer 意见
        comments = request.get("comments", [])
        assigned = self.assign_item_ids(comments)
        editor_items = [c for c in assigned if c.get("item_id", "").startswith("E.")]
        reviewer_items = [c for c in assigned if c.get("item_id", "").startswith("R")]
        # Step 4: 分类
        classified = {"major": [], "minor": [], "clarification": []}
        for item in assigned:
            sev = item.get("severity", "minor")
            classified.get(sev, classified["minor"]).append(item)
        # Step 5: 构建策略
        strategy = {
            "total_items": len(assigned),
            "editor_items": len(editor_items),
            "reviewer_items": len(reviewer_items),
            "major_count": len(classified["major"]),
        }
        # Step 6-8: 由 draft()/audit()/revise() 处理
        # Step 9: QA
        qa_issues = []
        for item in assigned:
            if "AUTHOR_INPUT_NEEDED" in str(item):
                qa_issues.append(f"{item['item_id']}: 需作者补充")
        # Step 10: 打包输出
        return {
            "mode": mode,
            "decision_type": decision_type,
            "editor_items": editor_items,
            "reviewer_items": reviewer_items,
            "classified": classified,
            "strategy": strategy,
            "qa_passed": len(qa_issues) == 0,
            "qa_issues": qa_issues,
        }

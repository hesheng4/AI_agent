"""审稿迭代闭环服务（H1）

借鉴 AI-Scientist v1：把 reviewer + writing 串成"审稿 → 修订 → 再审稿"自动循环，
以审稿分数（0-10）为停止条件：

1. reviewer.assess 审稿 → 结构化意见（improvement_suggestions）
2. reviewer.score 量化评分（overall）
3. 分数 < target_score 且未达最大轮数 → writing.revise 按意见修订稿件
4. 再审稿，直到分数达标或达到 max_rounds

工程特性：
- 停止条件双保险：分数阈值 / 最大轮数（默认 3）
- 修订无实质变化或意见为空时提前收敛，避免死循环
- 评分失败（overall=None）时降级：无分数可判 → 直接收敛，不空转
- 输出完整迭代记录（每轮分数/意见数/改动摘要），可审计、可回放
"""

from typing import Any

from app.agents.reviewer.agent import ReviewerAgent
from app.agents.writing.agent import WritingAgent
from app.utils.exceptions import AgentException
from app.utils.logger import get_logger

logger = get_logger("review_loop")

DEFAULT_MAX_ROUNDS = 3
DEFAULT_TARGET_SCORE = 7.0  # 0-10 分，Nature 级一般需 >= 7


class ReviewLoopService:
    """审稿 → 修订 → 再审稿自动迭代闭环"""

    def __init__(
        self,
        reviewer: ReviewerAgent | None = None,
        writing: WritingAgent | None = None,
    ):
        self.reviewer = reviewer or ReviewerAgent()
        self.writing = writing or WritingAgent()

    async def run(
        self,
        content: str,
        paper_type: str = "research",
        max_rounds: int = DEFAULT_MAX_ROUNDS,
        target_score: float = DEFAULT_TARGET_SCORE,
    ) -> dict[str, Any]:
        """执行审稿迭代闭环，返回最终稿件与迭代记录"""
        if not content.strip():
            raise AgentException("稿件内容不能为空", self.name)

        current = content
        rounds: list[dict[str, Any]] = []
        converged = False
        stop_reason = "max_rounds"

        for round_no in range(1, max(1, int(max_rounds)) + 1):
            # Step 1: 审稿
            assess_result = await self.reviewer.process(
                {
                    "task": "assess",
                    "content": current,
                    "paper_type": paper_type,
                }
            )
            suggestions = assess_result.get("improvement_suggestions") or []

            # Step 2: 评分
            score_result = await self.reviewer.process(
                {
                    "task": "score",
                    "review_result": assess_result.get("review_result", ""),
                }
            )
            overall = score_result.get("overall")
            logger.info(
                f"审稿迭代 第{round_no}轮: 分数={overall}, 意见数={len(suggestions)}"
            )

            round_record: dict[str, Any] = {
                "round": round_no,
                "score": overall,
                "axes": score_result.get("axes", {}),
                "suggestion_count": len(suggestions),
                "change_summary": "",
            }

            # Step 3: 停止条件判断
            if overall is not None and overall >= target_score:
                converged = True
                stop_reason = "score_achieved"
                rounds.append(round_record)
                break
            if overall is None:
                # 无法评分 → 不空转，直接收敛（保留当前稿件）
                converged = True
                stop_reason = "score_unavailable"
                rounds.append(round_record)
                break
            if round_no >= max_rounds:
                rounds.append(round_record)
                break
            if not suggestions:
                converged = True
                stop_reason = "no_suggestions"
                rounds.append(round_record)
                break

            # Step 4: 修订
            revise_result = await self.writing.process(
                {
                    "task": "revise",
                    "content": current,
                    "review_result": assess_result,
                }
            )
            revised = revise_result.get("revised_content", "")

            # 修订无效（空/未变化）→ 提前收敛防死循环
            if not revised.strip() or revised.strip() == current.strip():
                converged = True
                stop_reason = "revise_no_change"
                round_record["change_summary"] = "修订未产生实质变化"
                rounds.append(round_record)
                break

            round_record["change_summary"] = (
                f"按 {len(suggestions)} 条意见修订"
                f"（落实 {len(revise_result.get('change_log', []))} 条"
                f"，跳过 {len(revise_result.get('skipped', []))} 条）"
            )
            rounds.append(round_record)
            current = revised.strip()

        return {
            "final_content": current,
            "rounds": rounds,
            "total_rounds": len(rounds),
            "converged": converged,
            "stop_reason": stop_reason,
            "target_score": target_score,
            "max_rounds": int(max_rounds),
        }

    @property
    def name(self) -> str:
        return "review_loop"

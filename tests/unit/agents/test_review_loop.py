"""H1：审稿→修改→再审稿自动迭代闭环 单元测试

覆盖：
- ReviewLoopService.run：分数达标收敛 / 多轮迭代 / 最大轮数停止 /
  评分不可用收敛 / 修订无变化收敛 / 空内容校验
- ReviewerAgent.score：评分任务（LLM JSON 解析、容错降级）
- WritingAgent.revise：修订任务（JSON 解析、容错降级、空建议校验）
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.reviewer.agent import ReviewerAgent
from app.agents.writing.agent import WritingAgent
from app.services.review_loop import ReviewLoopService
from app.utils.exceptions import AgentException

# ─────────────────────────────────────────────
# 测试替身：模拟 reviewer / writing agent
# ─────────────────────────────────────────────


class FakeReviewer:
    """按轮次脚本返回审稿结果的假 reviewer"""

    def __init__(self, assess_results: list[dict], scores: list[dict]):
        self.assess_results = list(assess_results)
        self.scores = list(scores)
        self.assess_calls = 0
        self.score_calls = 0

    async def process(self, request: dict) -> dict:
        task = request.get("task")
        if task == "assess":
            idx = min(self.assess_calls, len(self.assess_results) - 1)
            result = self.assess_results[idx]
            self.assess_calls += 1
            return result
        if task == "score":
            idx = min(self.score_calls, len(self.scores) - 1)
            result = self.scores[idx]
            self.score_calls += 1
            return result
        raise AssertionError(f"unexpected task {task}")


class FakeWriting:
    """记录修订调用并返回修订稿的假 writing agent

    revised_content 为 None 时按调用次数递增（修订稿 v1/v2/...），
    避免多轮迭代时触发服务的"修订无变化"守卫。
    """

    def __init__(self, revised_content: str | None = None):
        self.revised_content = revised_content
        self.revise_calls: list[dict] = []

    async def process(self, request: dict) -> dict:
        self.revise_calls.append(request)
        if self.revised_content is None:
            content = f"修订稿 v{len(self.revise_calls)}"
        else:
            content = self.revised_content
        return {
            "revised_content": content,
            "change_log": [{"issue": "x", "location": "方法", "change": "补充"}],
            "skipped": [],
        }


ASSESS_OK = {
    "review_result": "审稿人1: 良好。审稿人2: 良好。",
    "improvement_suggestions": [{"issue": "补充对照组", "severity": "major"}],
}
SCORE_9 = {"overall": 9.0, "axes": {"originality": 9}}
SCORE_5 = {"overall": 5.0, "axes": {"originality": 5}}
SCORE_NONE = {"overall": None, "axes": {}}


# ─────────────────────────────────────────────
# ReviewLoopService.run
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_converges_when_score_achieved():
    """首轮分数达标 → 1 轮收敛，不再修订"""
    service = ReviewLoopService(
        reviewer=FakeReviewer([ASSESS_OK], [SCORE_9]),
        writing=FakeWriting(),
    )
    result = await service.run("稿件内容", max_rounds=3, target_score=7.0)
    assert result["converged"] is True
    assert result["stop_reason"] == "score_achieved"
    assert result["total_rounds"] == 1
    assert result["rounds"][0]["score"] == 9.0
    assert service.writing.revise_calls == []  # 未触发修订


@pytest.mark.asyncio
async def test_run_iterates_until_score_achieved():
    """分数不足 → 修订 → 再审，第二轮达标收敛"""
    service = ReviewLoopService(
        reviewer=FakeReviewer([ASSESS_OK, ASSESS_OK], [SCORE_5, SCORE_9]),
        writing=FakeWriting(revised_content="修订稿 v2"),
    )
    result = await service.run("稿件内容", max_rounds=3, target_score=7.0)
    assert result["converged"] is True
    assert result["stop_reason"] == "score_achieved"
    assert result["total_rounds"] == 2
    assert result["final_content"] == "修订稿 v2"
    assert len(service.writing.revise_calls) == 1
    # 修订请求应携带原稿件与审稿结果
    assert service.writing.revise_calls[0]["content"] == "稿件内容"
    assert "improvement_suggestions" in service.writing.revise_calls[0]["review_result"]


@pytest.mark.asyncio
async def test_run_stops_at_max_rounds():
    """始终不达标 → 达最大轮数停止，未收敛"""
    service = ReviewLoopService(
        reviewer=FakeReviewer(
            [ASSESS_OK, ASSESS_OK, ASSESS_OK],
            [SCORE_5, SCORE_5, SCORE_5],
        ),
        writing=FakeWriting(),
    )
    result = await service.run("稿件内容", max_rounds=3, target_score=7.0)
    assert result["converged"] is False
    assert result["stop_reason"] == "max_rounds"
    assert result["total_rounds"] == 3
    assert len(service.writing.revise_calls) == 2  # 第3轮不修订


@pytest.mark.asyncio
async def test_run_converges_when_score_unavailable():
    """评分不可用（overall=None）→ 不空转，直接收敛"""
    service = ReviewLoopService(
        reviewer=FakeReviewer([ASSESS_OK], [SCORE_NONE]),
        writing=FakeWriting(),
    )
    result = await service.run("稿件内容", max_rounds=3, target_score=7.0)
    assert result["converged"] is True
    assert result["stop_reason"] == "score_unavailable"
    assert result["total_rounds"] == 1
    assert service.writing.revise_calls == []


@pytest.mark.asyncio
async def test_run_converges_when_no_suggestions():
    """审稿无改进建议 → 提前收敛"""
    assess_no_suggestions = {"review_result": "审稿结果", "improvement_suggestions": []}
    service = ReviewLoopService(
        reviewer=FakeReviewer([assess_no_suggestions], [SCORE_5]),
        writing=FakeWriting(),
    )
    result = await service.run("稿件内容", max_rounds=3, target_score=7.0)
    assert result["converged"] is True
    assert result["stop_reason"] == "no_suggestions"


@pytest.mark.asyncio
async def test_run_converges_when_revise_no_change():
    """修订未产生变化 → 提前收敛防死循环"""
    service = ReviewLoopService(
        reviewer=FakeReviewer([ASSESS_OK], [SCORE_5]),
        writing=FakeWriting(revised_content="稿件内容"),  # 修订=原文
    )
    result = await service.run("稿件内容", max_rounds=3, target_score=7.0)
    assert result["converged"] is True
    assert result["stop_reason"] == "revise_no_change"
    assert result["total_rounds"] == 1


@pytest.mark.asyncio
async def test_run_empty_content_raises():
    service = ReviewLoopService(
        reviewer=FakeReviewer([ASSESS_OK], [SCORE_9]), writing=FakeWriting()
    )
    with pytest.raises(AgentException, match="稿件内容不能为空"):
        await service.run("   ", max_rounds=3, target_score=7.0)


# ─────────────────────────────────────────────
# ReviewerAgent.score
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_score_parses_json():
    reviewer = ReviewerAgent()
    with patch.object(
        reviewer,
        "call_llm",
        new=AsyncMock(
            return_value='{"overall": 7.5, "originality": 8, "importance": 7}'
        ),
    ):
        result = await reviewer.score({"review_result": "审稿文本"})
    assert result["overall"] == 7.5
    assert result["axes"]["originality"] == 8


@pytest.mark.asyncio
async def test_score_fence_stripped():
    reviewer = ReviewerAgent()
    with patch.object(
        reviewer,
        "call_llm",
        new=AsyncMock(return_value="```json\n{\"overall\": 6}\n```"),
    ):
        result = await reviewer.score({"review_result": "审稿文本"})
    assert result["overall"] == 6.0


@pytest.mark.asyncio
async def test_score_invalid_json_degrades():
    reviewer = ReviewerAgent()
    with patch.object(
        reviewer, "call_llm", new=AsyncMock(return_value="not json")
    ):
        result = await reviewer.score({"review_result": "审稿文本"})
    assert result == {"overall": None, "axes": {}}


@pytest.mark.asyncio
async def test_score_llm_failure_degrades():
    reviewer = ReviewerAgent()
    with patch.object(
        reviewer, "call_llm", new=AsyncMock(side_effect=RuntimeError("boom"))
    ):
        result = await reviewer.score({"review_result": "审稿文本"})
    assert result == {"overall": None, "axes": {}}


@pytest.mark.asyncio
async def test_score_empty_review_raises():
    reviewer = ReviewerAgent()
    with pytest.raises(AgentException, match="审稿结果不能为空"):
        await reviewer.score({"review_result": "  "})


# ─────────────────────────────────────────────
# WritingAgent.revise
# ─────────────────────────────────────────────


REVISE_JSON = """```json
{
  "revised_content": "修订后的完整稿件",
  "change_log": [
    {"issue": "补充对照组", "location": "方法", "change": "增加对照组说明"}
  ],
  "skipped": []
}
```"""


@pytest.mark.asyncio
async def test_revise_parses_result():
    writing = WritingAgent()
    with patch.object(
        writing, "call_llm", new=AsyncMock(return_value=REVISE_JSON)
    ):
        result = await writing.revise(
            {
                "content": "稿件",
                "suggestions": [{"issue": "补充对照组", "severity": "major"}],
            }
        )
    assert result["revised_content"] == "修订后的完整稿件"
    assert len(result["change_log"]) == 1
    assert result["skipped"] == []


@pytest.mark.asyncio
async def test_revise_fallback_to_original():
    """解析失败 → 退回原文并标记 parse_error"""
    writing = WritingAgent()
    with patch.object(
        writing, "call_llm", new=AsyncMock(return_value="not json")
    ):
        result = await writing.revise(
            {"content": "原稿件", "suggestions": [{"issue": "x", "severity": "major"}]}
        )
    assert result["revised_content"] == "原稿件"
    assert result["parse_error"] is True


@pytest.mark.asyncio
async def test_revise_empty_content_raises():
    writing = WritingAgent()
    with pytest.raises(AgentException, match="稿件内容不能为空"):
        await writing.revise({"content": "", "suggestions": [{"issue": "x"}]})


@pytest.mark.asyncio
async def test_revise_empty_suggestions_raises():
    writing = WritingAgent()
    with pytest.raises(AgentException, match="改进建议不能为空"):
        await writing.revise({"content": "稿件", "suggestions": []})


@pytest.mark.asyncio
async def test_revise_accepts_review_result_shape():
    """H1 串联：writing.revise 可直接接收 assess 的 review_result"""
    writing = WritingAgent()
    with patch.object(
        writing, "call_llm", new=AsyncMock(return_value=REVISE_JSON)
    ) as mock_llm:
        result = await writing.revise(
            {
                "content": "稿件",
                "review_result": {
                    "improvement_suggestions": [
                        {"issue": "补充对照组", "severity": "major", "location": "方法"}
                    ]
                },
            }
        )
    assert result["revised_content"] == "修订后的完整稿件"
    # 建议应进入 prompt
    prompt = mock_llm.call_args_list[0][0][0]
    assert "补充对照组" in prompt

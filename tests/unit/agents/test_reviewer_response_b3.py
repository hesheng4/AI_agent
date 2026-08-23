"""B3：审稿结构化输出「优缺点+改进建议」+ 串联审稿回复 单元测试

覆盖：
- reviewer.assess 输出结构化 strengths / improvement_suggestions
- reviewer._parse_structured 容错 JSON 解析（围栏/杂文/非法 JSON）
- response._derive_comments 从 review_result 派生审稿意见与决策类型
- response.draft 接收 review_result 串联（不传 reviewer_comments 也能起草）
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.response.agent import ResponseAgent
from app.agents.reviewer.agent import ReviewerAgent
from app.utils.exceptions import AgentException


@pytest.fixture
def reviewer():
    return ReviewerAgent()


@pytest.fixture
def responder():
    return ResponseAgent()


# ─────────────────────────────────────────────
# reviewer.assess：结构化输出
# ─────────────────────────────────────────────

STRUCTURED_JSON = """```json
{
  "strengths": [{"text": "研究问题清晰，实验设计合理"}],
  "improvement_suggestions": [
    {
      "issue": "缺乏对照组",
      "location": "方法",
      "suggestion": "增加阴性对照实验",
      "severity": "major",
      "category": "methodological"
    },
    {
      "issue": "讨论部分结论过度外推",
      "location": "讨论",
      "suggestion": "收敛结论表述",
      "severity": "minor",
      "category": "interpretive"
    }
  ]
}
```"""


@pytest.mark.asyncio
async def test_assess_returns_structured_fields(reviewer):
    """assess 应返回 strengths 与 improvement_suggestions 结构化字段"""
    with patch.object(
        reviewer,
        "call_llm",
        new=AsyncMock(side_effect=["fact_base", "review_result", STRUCTURED_JSON]),
    ):
        result = await reviewer.assess(
            {"content": "稿件内容", "paper_type": "research"}
        )
    assert result["fact_base"] == "fact_base"
    assert result["review_result"] == "review_result"
    assert len(result["strengths"]) == 1
    assert result["strengths"][0] == "研究问题清晰，实验设计合理"
    assert len(result["improvement_suggestions"]) == 2
    assert result["improvement_suggestions"][0]["severity"] == "major"
    assert result["improvement_suggestions"][1]["location"] == "讨论"


@pytest.mark.asyncio
async def test_assess_structured_extraction_failure_degrades(reviewer):
    """结构化提取 LLM 调用失败时降级为空清单，不阻断审稿"""
    with patch.object(
        reviewer,
        "call_llm",
        new=AsyncMock(side_effect=[RuntimeError("boom")]),
    ):
        structured = await reviewer._extract_structured("some review")
    assert structured == {"strengths": [], "improvement_suggestions": []}


# ─────────────────────────────────────────────
# reviewer._parse_structured：容错 JSON 解析
# ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw, expected",
    [
        (STRUCTURED_JSON, 2),  # 代码块围栏
        ('{"strengths": [], "improvement_suggestions": []}', 0),  # 裸 JSON
        (
            "审稿结果如下：\n{"
            + '"strengths": [{"text": "x"}], "improvement_suggestions": []}'
            + "}\n以上。",
            0,
        ),  # 前后杂文
        ("无有效内容", 0),  # 非法
        ("", 0),  # 空
        ("```json\nnot json\n```", 0),  # 围栏内非法
    ],
)
def test_parse_structured_tolerant(raw, expected):
    result = ReviewerAgent._parse_structured(raw)
    assert "strengths" in result
    assert "improvement_suggestions" in result
    assert len(result["improvement_suggestions"]) == expected


# ─────────────────────────────────────────────
# response._derive_comments：review_result → 意见 + 决策类型
# ─────────────────────────────────────────────


def test_derive_comments_maps_suggestions():
    review_result = {
        "improvement_suggestions": [
            {
                "issue": "缺乏对照组",
                "location": "方法",
                "severity": "major",
                "category": "methodological",
            },
            {
                "issue": "结论过度外推",
                "location": "讨论",
                "severity": "minor",
                "category": "interpretive",
            },
        ]
    }
    derived = ResponseAgent._derive_comments(review_result)
    assert derived["decision_type"] == "major"  # 存在 major 意见
    assert len(derived["reviewer_comments"]) == 2
    assert derived["reviewer_comments"][0].startswith("[major]")
    assert "方法" in derived["reviewer_comments"][0]
    assert derived["reviewer_comments"][1].startswith("[minor]")


def test_derive_comments_no_major_means_minor():
    review_result = {
        "improvement_suggestions": [
            {"issue": "措辞需调整", "location": "全文", "severity": "minor"}
        ]
    }
    derived = ResponseAgent._derive_comments(review_result)
    assert derived["decision_type"] == "minor"
    assert "（全文）" not in derived["reviewer_comments"][0]  # 全文位置省略


def test_derive_comments_empty_suggestions():
    assert ResponseAgent._derive_comments({}) == {
        "reviewer_comments": [],
        "decision_type": "minor",
    }


# ─────────────────────────────────────────────
# response.draft：review_result 串联
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_draft_with_review_result_derives_comments(responder):
    """不传 reviewer_comments，仅传 review_result 应能派生意见并起草"""
    review_result = {
        "improvement_suggestions": [
            {
                "issue": "缺乏对照组",
                "location": "方法",
                "severity": "major",
                "category": "methodological",
            }
        ]
    }
    with patch.object(
        responder,
        "call_llm",
        new=AsyncMock(side_effect=["classification", "response_letter"]),
    ) as mock_llm:
        result = await responder.draft(
            {"review_result": review_result, "manuscript_content": "稿件"}
        )
    assert result["total_comments"] == 1
    assert result["decision_type"] == "major"
    # 派生意见应进入 draft 的 comments_text（第二次 LLM 调用 prompt 含 [major]）
    prompt = mock_llm.call_args_list[1][0][0]
    assert "[major] 缺乏对照组" in prompt


@pytest.mark.asyncio
async def test_draft_without_comments_or_review_raises(responder):
    """既无 reviewer_comments 也无 review_result 应抛异常"""
    with pytest.raises(AgentException, match="审稿意见不能为空"):
        await responder.draft({"manuscript_content": "稿件"})


@pytest.mark.asyncio
async def test_draft_review_result_empty_suggestions_raises(responder):
    """review_result 无有效建议时仍应抛异常（不静默生成空回复）"""
    with pytest.raises(AgentException, match="审稿意见不能为空"):
        await responder.draft({"review_result": {}})


@pytest.mark.asyncio
async def test_draft_legacy_comments_still_works(responder):
    """原有 reviewer_comments 直传方式不受影响（向后兼容）"""
    with patch.object(
        responder,
        "call_llm",
        new=AsyncMock(side_effect=["classification", "response_letter"]),
    ):
        result = await responder.draft({"reviewer_comments": ["意见一"]})
    assert result["total_comments"] == 1
    assert result["decision_type"] == "major"

"""Paper2PPT Agent 单元测试

本轮补齐：paper2ppt 模块此前零测试。覆盖 9 步工作流端到端（mock call_llm）、
空内容校验、论文类型启发式分类、术语账本、QA 自审（过短内容告警）。
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.paper2ppt.agent import Paper2PPTAgent
from app.utils.exceptions import AgentException


@pytest.fixture
def agent():
    return Paper2PPTAgent()


# ─────────────────────────────────────────────
# 工作流端到端
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_content_raises(agent):
    """空内容应抛 AgentException"""
    with pytest.raises(AgentException, match="论文内容不能为空"):
        await agent.process({"content": "  "})


@pytest.mark.asyncio
async def test_process_full_workflow(agent):
    """9 步工作流：分类 → 术语 → LLM 生成 → QA 自审（长内容通过）"""
    # 注意：避免 benchmark/dataset 词（resource 分类先于 methods 命中）
    content = (
        "We propose a new algorithm and framework for this task. " + "x" * 250
    )
    with patch.object(
        agent, "call_llm", new=AsyncMock(return_value="y" * 250)
    ) as mock_llm:
        result = await agent.process({"content": content})
    assert mock_llm.call_count == 1  # 仅 _generate_deck 一次 LLM 调用
    assert result["paper_type"] == "methods"  # 'algorithm' 启发式命中
    assert result["deck"]["total_slides"] >= 1
    assert result["qa"]["passed"] is True
    assert result["slide_structure"]


@pytest.mark.asyncio
async def test_qa_flags_short_content(agent):
    """QA 自审：生成内容 <200 字符应标记未通过"""
    with patch.object(agent, "call_llm", new=AsyncMock(return_value="short deck")):
        result = await agent.process({"content": "a paper with a method here " * 10})
    assert result["qa"]["passed"] is False
    assert any("过短" in issue for issue in result["qa"]["issues"])


# ─────────────────────────────────────────────
# 启发式
# ─────────────────────────────────────────────


def test_classify_type_heuristics(agent):
    """论文类型启发式分类（clinical > resource > methods > review > materials > discovery）"""
    assert (
        agent._classify_type("A randomized clinical trial of the intervention")
        == "clinical"
    )
    assert agent._classify_type("We release a new benchmark corpus dataset") == "resource"
    assert agent._classify_type("Our method improves the algorithm") == "methods"
    assert agent._classify_type("A review and survey of the literature") == "review"
    assert agent._classify_type("Novel material synthesis with unique property") == "materials"
    assert agent._classify_type("An unclassified discovery study") == "discovery"


def test_terminology_ledger(agent):
    """术语账本：大写缩写（2-8 字符）入账并排序"""
    result = agent._build_terminology("DNA and PCR are used together")
    assert result["terms"] == ["DNA", "PCR"]
    assert result["total"] == 2

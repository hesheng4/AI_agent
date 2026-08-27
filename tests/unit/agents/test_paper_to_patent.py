"""PaperToPatent Agent 单元测试

本轮补齐：paper_to_patent 模块此前零测试。覆盖阶段门控工作流的
三种 task_mode（full_draft/claims_only/audit）、未知 mode 回退、
空内容校验。audit 模式零 LLM 调用（纯启发式）。
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.paper_to_patent.agent import PaperToPatentAgent
from app.utils.exceptions import AgentException

_CONTENT = (
    "The method uses a DNA sequencing algorithm. $E = mc^2$\n\n"
    "Figure 1 shows the results of the protocol."
)


@pytest.fixture
def agent():
    return PaperToPatentAgent()


# ─────────────────────────────────────────────
# 工作流端到端
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_content_raises(agent):
    """空内容应抛 AgentException"""
    with pytest.raises(AgentException, match="论文内容不能为空"):
        await agent.process({"content": " "})


@pytest.mark.asyncio
async def test_full_draft_mode(agent):
    """full_draft：LLM 生成草稿 + 源依据/证据规模回显"""
    with patch.object(agent, "call_llm", new=AsyncMock(return_value="drafted")) as mock_llm:
        result = await agent.process({"content": _CONTENT})
    assert mock_llm.call_count == 1
    assert result["draft"] == "drafted"
    assert result["source_map_size"] >= 2  # 两段各一条 text 源
    assert result["evidence_size"] >= 2
    assert result["invention_type"] == "algorithm"  # 默认


@pytest.mark.asyncio
async def test_claims_only_mode(agent):
    """claims_only：仅生成权利要求书"""
    with patch.object(agent, "call_llm", new=AsyncMock(return_value="claim 1")):
        result = await agent.process(
            {"content": _CONTENT, "task_mode": "claims_only"}
        )
    assert result["claims"] == "claim 1"
    assert result["invention_type"] == "algorithm"


@pytest.mark.asyncio
async def test_audit_mode_no_llm(agent):
    """audit：零 LLM 调用（纯证据账本启发式），explicit 特征全部通过"""
    with patch.object(agent, "call_llm", new=AsyncMock(return_value="stub")) as mock_llm:
        result = await agent.process({"content": _CONTENT, "task_mode": "audit"})
    assert mock_llm.call_count == 0
    assert result["audit_passed"] is True
    assert result["unsupported"] == 0
    assert result["total_features"] >= 2


@pytest.mark.asyncio
async def test_unknown_mode_falls_back_no_llm(agent):
    """未知 task_mode：回退为源依据映射 + 证据账本（不调 LLM）"""
    with patch.object(agent, "call_llm", new=AsyncMock(return_value="stub")) as mock_llm:
        result = await agent.process(
            {"content": _CONTENT, "task_mode": "bogus-mode"}
        )
    assert mock_llm.call_count == 0
    assert "source_map" in result
    assert "evidence" in result


# ─────────────────────────────────────────────
# 阶段启发式
# ─────────────────────────────────────────────


def test_source_map_detects_equation_and_figure(agent):
    """源依据映射：公式 → E 类、图表引用 → F 类、段落 → P 类"""
    source_map = agent._build_source_map(_CONTENT)
    types = {s["type"] for s in source_map}
    assert "text" in types
    assert "equation" in types
    assert "figure" in types


def test_terminology_ledger(agent):
    """术语账本：缩写与驼峰词入账并排序"""
    result = agent._build_terminology(_CONTENT)
    assert "DNA" in result["terms"]
    assert result["total"] == len(result["terms"])

"""Citation Agent 单元测试

本轮新建：citation 模块此前零测试。覆盖任务分派、空值校验、
默认 style 对齐、确定性温度（mock call_llm 验证）。
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.citation.agent import CitationAgent
from app.utils.exceptions import AgentException


@pytest.fixture
def agent():
    return CitationAgent()


# ─────────────────────────────────────────────
# 任务分派
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unknown_task_raises(agent):
    """未知 task 应抛 AgentException"""
    with pytest.raises(AgentException, match="未知任务类型"):
        await agent.process({"task": "non-existent"})


@pytest.mark.asyncio
async def test_known_tasks_dispatch(agent):
    """三个已知 task 应正确分派到 handler（mock call_llm / verify_references
    避免真实 LLM 调用与外部网络请求）"""
    with patch.object(agent, "call_llm", new=AsyncMock(return_value="stub")), patch(
        "app.agents.citation.agent.verify_references",
        new=AsyncMock(return_value=[]),
    ):
        await agent.process({"task": "add-citations", "content": "x"})
        await agent.process(
            {"task": "verify-citations", "content": "x", "references": ["r"]}
        )
        await agent.process({"task": "format-references", "references": ["r"]})


# ─────────────────────────────────────────────
# 空值校验
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_citations_empty_content_raises(agent):
    with pytest.raises(AgentException, match="内容不能为空"):
        await agent.add_citations({"content": "   "})


@pytest.mark.asyncio
async def test_verify_citations_empty_content_raises(agent):
    with pytest.raises(AgentException, match="内容不能为空"):
        await agent.verify_citations({"content": "", "references": ["r"]})


@pytest.mark.asyncio
async def test_format_references_empty_raises(agent):
    with pytest.raises(AgentException, match="参考文献列表不能为空"):
        await agent.format_references({"references": []})


# ─────────────────────────────────────────────
# C1 回归：verify 空引用列表应跳过 LLM
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_citations_empty_references_skips_llm(agent):
    """空 references 不应触发 LLM 调用"""
    with patch.object(agent, "call_llm", new=AsyncMock()) as mock_llm:
        result = await agent.verify_citations({"content": "x", "references": []})
        assert result["total_references"] == 0
        assert "跳过验证" in result["verification"]
        mock_llm.assert_not_called()


# ─────────────────────────────────────────────
# C4 回归：format 默认 style 应为 nature
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_format_references_default_style_is_nature(agent):
    """不传 style 时 agent 默认 nature，与 prompts 全篇 Nature 格式对齐"""
    with patch.object(agent, "call_llm", new=AsyncMock(return_value="formatted")):
        result = await agent.format_references({"references": ["ref1"]})
        assert result["style"] == "nature"


# ─────────────────────────────────────────────
# C6 回归：确定性任务应使用低温
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_citations_uses_low_temperature(agent):
    """citation 是确定性任务，call_llm 应被以 temperature=0.0 调用"""
    with patch.object(
        agent, "call_llm", new=AsyncMock(return_value="stub")
    ) as mock_llm:
        await agent.add_citations({"content": "some content"})
        # add_citations 触发 4 次 LLM 调用，每次 temperature 都应为 0.0
        assert mock_llm.call_count == 4
        for call in mock_llm.call_args_list:
            assert call.kwargs.get("temperature") == 0.0


@pytest.mark.asyncio
async def test_format_references_uses_low_temperature(agent):
    with patch.object(
        agent, "call_llm", new=AsyncMock(return_value="stub")
    ) as mock_llm:
        await agent.format_references({"references": ["ref1"]})
        assert mock_llm.call_count == 1
        assert mock_llm.call_args.kwargs.get("temperature") == 0.0


# ─────────────────────────────────────────────
# C2 回归：add_citations 最终整合不应截断原文
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_citations_final_prompt_uses_full_content(agent):
    """最终整合步骤应使用完整 content，而非 content[:4000]"""
    long_content = "X" * 5000  # 超过旧截断阈值 4000

    captured_prompts = []

    async def fake_call(prompt, *args, **kwargs):
        captured_prompts.append(prompt)
        return "stub"

    with patch.object(agent, "call_llm", new=AsyncMock(side_effect=fake_call)):
        await agent.add_citations({"content": long_content})

    # 第 4 次 LLM 调用的 prompt 是最终整合，应含完整原文
    final_prompt = captured_prompts[3]
    assert long_content in final_prompt
    # 确认未被截断（5000 字符全部传入）
    assert final_prompt.count("X") == 5000

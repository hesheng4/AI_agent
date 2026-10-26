"""Reader Agent 单元测试

本轮补齐：reader 模块此前零测试。覆盖 6 步工作流端到端（mock call_llm）、
空内容校验、批量翻译分段（5 段/批）、格式自动检测启发式。
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.reader.agent import ReaderAgent
from app.utils.exceptions import AgentException


@pytest.fixture
def agent():
    return ReaderAgent()


# ─────────────────────────────────────────────
# 工作流端到端
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_content_raises(agent):
    """空内容应抛 AgentException"""
    with pytest.raises(AgentException, match="论文内容不能为空"):
        await agent.process({"content": "   "})


@pytest.mark.asyncio
async def test_process_produces_bilingual_output(agent):
    """两段落 → 中英对照 Markdown + source_map + 术语账本 + 统计"""
    with patch.object(
        agent, "call_llm", new=AsyncMock(return_value="【原文】p1\n【译文】P1")
    ) as mock_llm:
        result = await agent.process(
            {"content": "第一段论文内容\n\n第二段论文内容"}
        )
    assert mock_llm.call_count == 1  # 2 段一批（batch_size=5）
    assert result["stats"]["total_segments"] == 2
    assert "【原文】" in result["paper_md"]
    assert "【译文】" in result["paper_md"]
    source_map = json.loads(result["source_map"])
    assert source_map["source_format"] == "pasted-text"
    assert len(source_map["segments"]) == 2
    json.loads(result["terminology_ledger"])  # 合法 JSON


@pytest.mark.asyncio
async def test_translation_batches_of_five(agent):
    """6 段落 → 2 批（5 + 1），2 次 LLM 调用"""
    content = "\n\n".join(f"第{i}段论文内容，足够长一些" for i in range(6))
    with patch.object(agent, "call_llm", new=AsyncMock(return_value="译文")) as mock_llm:
        result = await agent.process({"content": content})
    assert mock_llm.call_count == 2
    assert result["stats"]["total_segments"] == 6


# ─────────────────────────────────────────────
# 格式自动检测
# ─────────────────────────────────────────────


def test_detect_format_arxiv_url():
    assert (
        ReaderAgent()._detect_format("https://arxiv.org/abs/1234.5678") == "doi-arxiv"
    )


def test_detect_format_plain_url():
    assert ReaderAgent()._detect_format("https://example.com/paper.html") == "html"


def test_detect_format_pasted_text():
    assert ReaderAgent()._detect_format("plain pasted text") == "pasted-text"

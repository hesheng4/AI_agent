"""Polishing Agent 单元测试

本轮补齐：polishing 模块此前零测试。覆盖任务分派（含术语/排版/翻译
别名任务名）、默认任务、语言/论文类型启发式、确定性温度。
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.polishing.agent import PolishingAgent
from app.utils.exceptions import AgentException


@pytest.fixture
def agent():
    return PolishingAgent()


# ─────────────────────────────────────────────
# 任务分派
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unknown_task_raises(agent):
    """未知 task 应抛 AgentException"""
    with patch.object(agent, "call_llm", new=AsyncMock(return_value="stub")):
        with pytest.raises(AgentException, match="未知任务类型"):
            await agent.process({"task": "non-existent"})


@pytest.mark.asyncio
async def test_default_task_is_polish(agent):
    """不带 task 时默认走 polish（语言自动检测）"""
    with patch.object(agent, "call_llm", new=AsyncMock(return_value="polished")):
        result = await agent.process({"content": "这是一个中文段落。"})
    assert result["polished"] == "polished"
    assert result["original"] == "这是一个中文段落。"
    assert result["paper_type"] == "research"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "task,key,payload",
    [
        ("diagnose", "diagnosis", {"content": "x"}),
        ("terminology", "terminology_check", {"content": "x"}),
        ("latex_layout", "layout_fixes", {"tex_source": "\\begin{document}"}),
        ("translate", "translated", {"content": "中文内容"}),
    ],
)
async def test_known_tasks_dispatch(agent, task, key, payload):
    """diagnose/terminology/latex_layout/translate 正确分派（别名任务名）"""
    with patch.object(agent, "call_llm", new=AsyncMock(return_value="stub")):
        result = await agent.process({"task": task, **payload})
    assert result[key] == "stub"


# ─────────────────────────────────────────────
# 启发式检测
# ─────────────────────────────────────────────


def test_detect_language():
    """中文占比 >30% → zh-to-en，否则 en"""
    assert PolishingAgent.detect_language("这个算法模型很好") == "zh-to-en"
    assert PolishingAgent.detect_language("this is a simple english text") == "en"


def test_detect_paper_type():
    """论文类型关键词启发式"""
    assert PolishingAgent.detect_paper_type("we propose a new algorithm") == "algorithmic"
    assert PolishingAgent.detect_paper_type("a systematic review of the field") == "review"
    assert PolishingAgent.detect_paper_type("a causal hypothesis test") == "hypothesis"
    assert PolishingAgent.detect_paper_type("methods and protocol design") == "methods"
    assert PolishingAgent.detect_paper_type("nothing matches here") == "research"


# ─────────────────────────────────────────────
# 确定性温度
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_polish_uses_zero_temperature(agent):
    """润色是确定性任务，call_llm 应以 temperature=0.0 调用"""
    with patch.object(agent, "call_llm", new=AsyncMock(return_value="stub")) as mock_llm:
        await agent.polish({"content": "x"})
    assert mock_llm.call_args.kwargs["temperature"] == 0.0

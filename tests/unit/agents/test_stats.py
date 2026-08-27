"""Stats Agent 单元测试

本轮补齐：stats 模块此前零测试。覆盖任务分派、默认任务/默认 location、
未知任务、确定性温度（mock call_llm 验证）。
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.stats.agent import StatsAgent
from app.utils.exceptions import AgentException


@pytest.fixture
def agent():
    return StatsAgent()


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
async def test_default_task_is_audit(agent):
    """不带 task 时默认走 audit（location 默认 results）"""
    with patch.object(agent, "call_llm", new=AsyncMock(return_value="audit-result")):
        result = await agent.process({"content": "统计报告"})
    assert result["audit"] == "audit-result"
    assert result["location"] == "results"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "task,key,location",
    [
        ("audit", "audit", None),
        ("draft", "draft", "figure_legend"),
        ("check_test", "test_check", None),
        ("check_multiple", "multiple_comparison_check", None),
    ],
)
async def test_known_tasks_dispatch(agent, task, key, location):
    """四个已知 task 正确分派到对应 handler（返回键映射 + 默认 location）"""
    with patch.object(agent, "call_llm", new=AsyncMock(return_value="stub")):
        result = await agent.process({"task": task, "content": "统计报告"})
    assert result[key] == "stub"
    if key in ("audit", "draft"):
        assert result["location"] == (
            location if location is not None else "results"
        )


# ─────────────────────────────────────────────
# 确定性温度
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_draft_uses_zero_temperature(agent):
    """统计声明起草是确定性任务，call_llm 应以 temperature=0.0 调用"""
    with patch.object(agent, "call_llm", new=AsyncMock(return_value="stub")) as mock_llm:
        await agent.draft({"content": "x"})
    assert mock_llm.call_args.kwargs["temperature"] == 0.0


@pytest.mark.asyncio
async def test_draft_forwards_user_api(agent):
    """_user_api_* 透传给 call_llm（E2 契约）"""
    with patch.object(agent, "call_llm", new=AsyncMock(return_value="stub")) as mock_llm:
        await agent.draft(
            {
                "content": "x",
                "_user_api_key": "user-key-123",
                "_user_api_base_url": "https://user.example.com",
                "_user_api_model": "user-model-x",
            }
        )
    kwargs = mock_llm.call_args.kwargs
    assert kwargs["user_api_key"] == "user-key-123"
    assert kwargs["user_api_base_url"] == "https://user.example.com"
    assert kwargs["user_api_model"] == "user-model-x"

"""Writing Agent 单元测试补充

本轮新增：W1 并发污染关键回归（用户级 API 配置不经实例属性）、W4 单例。
原有 test_writing.py 14 个测试覆盖 outline + tools，本轮补关键安全回归。
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.writing import WritingAgent, get_writing_agent
from app.utils.exceptions import AgentException


@pytest.fixture
def agent():
    return WritingAgent()


# ─────────────────────────────────────────────
# W1 关键回归：用户级 API 配置不经实例属性传递
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_process_does_not_set_instance_attrs_for_user_api(agent):
    r"""W1 修复：用户级 API 配置应经 request dict 透传给 call_llm，

    旧版 process 把 _user_api_key 等存到 self._user_api_* 实例属性，
    单例下并发请求会互相覆盖（用户 A 的请求可能用用户 B 的 key）。
    修复后 handler 从 request 取并直接传给 call_llm。
    """
    with patch.object(
        agent, "call_llm", new=AsyncMock(return_value="stub")
    ) as mock_llm:
        await agent.process(
            {
                "task": "polish",
                "content": "x",
                "_user_api_key": "user_a_key",
                "_user_api_base_url": "http://a",
                "_user_api_model": "model_a",
            }
        )
        # call_llm 应直接收到 user_a 的配置
        assert mock_llm.call_args.kwargs.get("user_api_key") == "user_a_key"
        assert mock_llm.call_args.kwargs.get("user_api_base_url") == "http://a"
        assert mock_llm.call_args.kwargs.get("user_api_model") == "model_a"

    # 关键：process 后实例上不应残留 _user_api_* 属性
    assert not hasattr(agent, "_user_api_key")
    assert not hasattr(agent, "_user_api_base_url")
    assert not hasattr(agent, "_user_api_model")


@pytest.mark.asyncio
async def test_concurrent_requests_do_not_cross_contaminate(agent):
    """W1 关键：两次连续请求应各自用自己的 API 配置，不互相污染"""
    with patch.object(
        agent, "call_llm", new=AsyncMock(return_value="stub")
    ) as mock_llm:
        await agent.process(
            {
                "task": "polish",
                "content": "x",
                "_user_api_key": "user_a_key",
            }
        )
        await agent.process(
            {
                "task": "polish",
                "content": "y",
                "_user_api_key": "user_b_key",
            }
        )
        keys = [call.kwargs.get("user_api_key") for call in mock_llm.call_args_list]
        assert keys == ["user_a_key", "user_b_key"]


# ─────────────────────────────────────────────
# W3 回归：空 task 友好错误
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unknown_task_friendly_error(agent):
    with pytest.raises(AgentException, match="未知任务类型"):
        await agent.process({"task": "xyz_no_match"})


# ─────────────────────────────────────────────
# W5 回归：低温调用
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_polish_uses_low_temperature(agent):
    with patch.object(
        agent, "call_llm", new=AsyncMock(return_value="stub")
    ) as mock_llm:
        await agent.polish({"content": "x"})
        assert mock_llm.call_args.kwargs.get("temperature") == 0.0


@pytest.mark.asyncio
async def test_create_outline_uses_low_temperature(agent):
    with patch.object(
        agent, "call_llm", new=AsyncMock(return_value="stub")
    ) as mock_llm:
        await agent.create_outline({"topic": "x"})
        assert mock_llm.call_args.kwargs.get("temperature") == 0.0


# ─────────────────────────────────────────────
# W4 回归：单例工厂
# ─────────────────────────────────────────────


def test_singleton_factory_returns_same_instance():
    a = get_writing_agent()
    b = get_writing_agent()
    assert a is b


def test_singleton_is_writing_agent():
    assert isinstance(get_writing_agent(), WritingAgent)

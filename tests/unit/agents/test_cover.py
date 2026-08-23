"""Cover Agent 单元测试

本轮新建：cover 此前零测试。覆盖任务分派、空值校验、低温调用、
K5 关键修复（用户级 API 配置不再经实例属性传递）、单例。
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.cover import CoverAgent, get_cover_agent
from app.utils.exceptions import AgentException


@pytest.fixture
def agent():
    return CoverAgent()


# ─────────────────────────────────────────────
# 任务分派
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unknown_task_raises(agent):
    with pytest.raises(AgentException, match="未知任务类型"):
        await agent.process({"task": "non-existent", "content": "x"})


@pytest.mark.asyncio
async def test_known_tasks_dispatch(agent):
    with patch.object(agent, "call_llm", new=AsyncMock(return_value="stub")):
        await agent.process({"task": "draft", "title": "t", "abstract": "a"})
        await agent.process({"task": "audit", "content": "x"})
        await agent.process({"task": "presubmission", "title": "t", "abstract": "a"})


# ─────────────────────────────────────────────
# K6 回归：空 task 应回退到 draft
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_task_falls_back_to_draft(agent):
    """空字符串 task 不应抛"未知任务"，应回退默认 draft"""
    with patch.object(agent, "call_llm", new=AsyncMock(return_value="stub")):
        result = await agent.process({"task": "", "title": "t", "abstract": "a"})
        assert "cover_letter" in result


@pytest.mark.asyncio
async def test_missing_task_falls_back_to_draft(agent):
    """未传 task 应回退默认 draft"""
    with patch.object(agent, "call_llm", new=AsyncMock(return_value="stub")):
        result = await agent.process({"title": "t", "abstract": "a"})
        assert "cover_letter" in result


# ─────────────────────────────────────────────
# K10 回归：空值校验
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_draft_validates_required_fields(agent):
    """draft 至少需要 title 或 abstract，避免空输入浪费 LLM token"""
    with pytest.raises(AgentException, match="至少需要 title 或 abstract"):
        await agent.draft({"title": "", "abstract": "   "})


@pytest.mark.asyncio
async def test_audit_validates_content(agent):
    with pytest.raises(AgentException, match="审计内容不能为空"):
        await agent.audit({"content": ""})


@pytest.mark.asyncio
async def test_presubmission_validates_required_fields(agent):
    with pytest.raises(AgentException, match="至少需要 title 或 abstract"):
        await agent.presubmission({"title": "", "abstract": ""})


# ─────────────────────────────────────────────
# K8 回归：低温调用
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_draft_uses_low_temperature(agent):
    with patch.object(
        agent, "call_llm", new=AsyncMock(return_value="stub")
    ) as mock_llm:
        await agent.draft({"title": "t", "abstract": "a"})
        assert mock_llm.call_count == 1
        assert mock_llm.call_args.kwargs.get("temperature") == 0.0


@pytest.mark.asyncio
async def test_audit_uses_low_temperature(agent):
    with patch.object(
        agent, "call_llm", new=AsyncMock(return_value="stub")
    ) as mock_llm:
        await agent.audit({"content": "x"})
        assert mock_llm.call_args.kwargs.get("temperature") == 0.0


# ─────────────────────────────────────────────
# K5 关键回归：用户级 API 配置不经实例属性传递
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_process_does_not_set_instance_attrs_for_user_api(agent):
    r"""K5 修复：用户级 API 配置应经 request dict 透传给 call_llm，

    旧版 process 把 _user_api_key 等存到 self._user_api_key 实例属性，
    单例下并发请求会互相覆盖（用户 A 的请求可能用用户 B 的 key）。
    修复后 handler 从 request 取并直接传给 call_llm。
    """
    with patch.object(
        agent, "call_llm", new=AsyncMock(return_value="stub")
    ) as mock_llm:
        await agent.process(
            {
                "task": "audit",
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
    """K5 关键：两次连续请求应各自用自己的 API 配置，不互相污染"""
    with patch.object(
        agent, "call_llm", new=AsyncMock(return_value="stub")
    ) as mock_llm:
        await agent.process(
            {
                "task": "audit",
                "content": "x",
                "_user_api_key": "user_a_key",
            }
        )
        await agent.process(
            {
                "task": "audit",
                "content": "y",
                "_user_api_key": "user_b_key",
            }
        )
        # 两次调用各自用自己的 key
        keys = [call.kwargs.get("user_api_key") for call in mock_llm.call_args_list]
        assert keys == ["user_a_key", "user_b_key"]


# ─────────────────────────────────────────────
# 单例工厂
# ─────────────────────────────────────────────


def test_singleton_factory_returns_same_instance():
    a = get_cover_agent()
    b = get_cover_agent()
    assert a is b


def test_singleton_is_cover_agent():
    assert isinstance(get_cover_agent(), CoverAgent)

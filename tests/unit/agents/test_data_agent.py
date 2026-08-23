"""DataAvailability Agent 单元测试

本轮新建：data_agent 此前零测试。覆盖任务分派、空值校验、低温调用、单例。
类名已从 DataAgent 改为 DataAvailabilityAgent（消除与 data/ 的命名冲突）。
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.data_agent import (
    DataAvailabilityAgent,
    get_data_availability_agent,
)
from app.utils.exceptions import AgentException


@pytest.fixture
def agent():
    return DataAvailabilityAgent()


# ─────────────────────────────────────────────
# 任务分派
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unknown_task_raises(agent):
    with pytest.raises(AgentException, match="未知任务类型"):
        await agent.process({"task": "non-existent"})


@pytest.mark.asyncio
async def test_known_tasks_dispatch(agent):
    with patch.object(agent, "call_llm", new=AsyncMock(return_value="stub")):
        await agent.process({"task": "generate-statement", "data_description": "x"})
        await agent.process({"task": "audit-statement", "statement": "x"})
        await agent.process({"task": "select-repository", "data_type": "genomic"})


# ─────────────────────────────────────────────
# 空值校验
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_statement_validates_data_description(agent):
    with pytest.raises(AgentException, match="数据描述不能为空"):
        await agent.generate_statement({"data_description": "   "})


@pytest.mark.asyncio
async def test_audit_statement_validates_statement(agent):
    with pytest.raises(AgentException, match="数据可用性声明不能为空"):
        await agent.audit_statement({"statement": ""})


@pytest.mark.asyncio
async def test_select_repository_validates_data_type(agent):
    with pytest.raises(AgentException, match="数据类型不能为空"):
        await agent.select_repository({"data_type": ""})


# ─────────────────────────────────────────────
# D8 回归：低温调用
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_statement_uses_low_temperature(agent):
    with patch.object(
        agent, "call_llm", new=AsyncMock(return_value="stub")
    ) as mock_llm:
        await agent.generate_statement({"data_description": "x"})
        assert mock_llm.call_args.kwargs.get("temperature") == 0.0


@pytest.mark.asyncio
async def test_audit_statement_uses_low_temperature(agent):
    with patch.object(
        agent, "call_llm", new=AsyncMock(return_value="stub")
    ) as mock_llm:
        await agent.audit_statement({"statement": "x"})
        assert mock_llm.call_args.kwargs.get("temperature") == 0.0


@pytest.mark.asyncio
async def test_select_repository_uses_low_temperature(agent):
    with patch.object(
        agent, "call_llm", new=AsyncMock(return_value="stub")
    ) as mock_llm:
        await agent.select_repository({"data_type": "genomic"})
        assert mock_llm.call_args.kwargs.get("temperature") == 0.0


# ─────────────────────────────────────────────
# D10 回归：单例工厂
# ─────────────────────────────────────────────


def test_singleton_factory_returns_same_instance():
    a = get_data_availability_agent()
    b = get_data_availability_agent()
    assert a is b


def test_singleton_is_data_availability_agent():
    assert isinstance(get_data_availability_agent(), DataAvailabilityAgent)


# ─────────────────────────────────────────────
# D7 回归：类名已改为 DataAvailabilityAgent（不再与 data/ 的 DataAgent 冲突）
# ─────────────────────────────────────────────


def test_class_name_is_data_availability_agent():
    """D7 修复：类名应为 DataAvailabilityAgent，消除与 data/agent.py 的命名冲突"""
    assert DataAvailabilityAgent.__name__ == "DataAvailabilityAgent"

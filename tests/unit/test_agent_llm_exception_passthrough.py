"""回归：BaseAgent.call_llm 不得重包 LLM 异常（credibility-convergence 批次二）

历史缺陷：call_llm 把 LLMTimeoutException/LLMRateLimitException 一律
重包成通用 AgentException，classify_failure 依赖这两个类型判定
transient → workflow 的自动重试对 LLM 超时/限流永久失明
（workflow-error-recovery-v1 的 transient 语义被破坏）。

修复后：LLMException 及其子类原样穿透；其他异常仍包成 AgentException。
"""

import pytest

from app.agents.base import BaseAgent
from app.core.runs import FAILURE_TRANSIENT, classify_failure
from app.utils.exceptions import (
    AgentException,
    LLMRateLimitException,
    LLMTimeoutException,
    ValidationException,
)


class _PassthroughAgent(BaseAgent):
    """最小具体 Agent：仅用于驱动 call_llm 异常路径"""

    def __init__(self) -> None:
        super().__init__(name="passthrough")

    async def process(self, request: dict) -> dict:  # type: ignore[override]
        return {}


@pytest.fixture
def agent() -> _PassthroughAgent:
    return _PassthroughAgent()


@pytest.mark.asyncio
async def test_llm_timeout_passthrough_keeps_type(agent, monkeypatch):
    """LLM 超时异常保持类型 → classify_failure 判定 transient"""

    async def _raise(*args, **kwargs):
        raise LLMTimeoutException()

    monkeypatch.setattr(agent.llm, "generate", _raise)
    with pytest.raises(LLMTimeoutException):
        await agent.call_llm("prompt")
    assert classify_failure(LLMTimeoutException()) == FAILURE_TRANSIENT


@pytest.mark.asyncio
async def test_llm_rate_limit_passthrough_keeps_type(agent, monkeypatch):
    async def _raise(*args, **kwargs):
        raise LLMRateLimitException()

    monkeypatch.setattr(agent.llm, "generate", _raise)
    with pytest.raises(LLMRateLimitException):
        await agent.call_llm("prompt")


@pytest.mark.asyncio
async def test_non_llm_error_still_wrapped_as_agent_exception(agent, monkeypatch):
    class _WeirdError(Exception):
        pass

    async def _raise(*args, **kwargs):
        raise _WeirdError("boom")

    monkeypatch.setattr(agent.llm, "generate", _raise)
    with pytest.raises(AgentException):
        await agent.call_llm("prompt")


@pytest.mark.asyncio
async def test_validation_exception_wrapped_not_swallowed(agent, monkeypatch):
    """ValidationException 非 LLM 异常，仍应包装（分类 permanent 的输入由
    路由层抛出，不经过 call_llm）"""
    async def _raise(*args, **kwargs):
        raise ValidationException("bad input")

    monkeypatch.setattr(agent.llm, "generate", _raise)
    with pytest.raises(AgentException):
        await agent.call_llm("prompt")

"""Methods Agent 单元测试

本轮补齐：methods 模块此前零测试。覆盖任务分派、默认任务、
未知任务、确定性温度（mock call_llm 验证）。
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.methods.agent import MethodsAgent
from app.utils.exceptions import AgentException


@pytest.fixture
def agent():
    return MethodsAgent()


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
    """不带 task 时默认走 audit（study_type 默认 experimental）"""
    with patch.object(agent, "call_llm", new=AsyncMock(return_value="audit-result")):
        result = await agent.process({"content": "Methods 文本"})
    assert result["audit"] == "audit-result"
    assert result["study_type"] == "experimental"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "task,key,study_type",
    [
        ("audit", "audit", "clinical"),
        ("draft", "draft", None),
        ("check_ethics", "ethics_check", None),
        ("remove_vague", "revised", None),
    ],
)
async def test_known_tasks_dispatch(agent, task, key, study_type):
    """四个已知 task 正确分派到对应 handler（返回键映射）"""
    request = {"task": task, "content": "Methods 文本"}
    if study_type:
        request["study_type"] = study_type
    with patch.object(agent, "call_llm", new=AsyncMock(return_value="stub")):
        result = await agent.process(request)
    assert result[key] == "stub"
    if key == "audit":
        assert result["study_type"] == study_type


# ─────────────────────────────────────────────
# 确定性温度 + 凭据透传
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_audit_uses_zero_temperature(agent):
    """Methods 审计是确定性任务，call_llm 应以 temperature=0.0 调用"""
    with patch.object(agent, "call_llm", new=AsyncMock(return_value="stub")) as mock_llm:
        await agent.audit({"content": "x"})
    assert mock_llm.call_args.kwargs["temperature"] == 0.0


@pytest.mark.asyncio
async def test_audit_forwards_user_api(agent):
    """_user_api_* 透传给 call_llm（E2 契约，与 citation/cover 一致）"""
    with patch.object(agent, "call_llm", new=AsyncMock(return_value="stub")) as mock_llm:
        await agent.audit(
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

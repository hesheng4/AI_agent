"""SubmissionPackage Agent 单元测试

本轮补齐：submission_package 模块此前零测试。覆盖任务分派、
默认任务、未知任务、确定性温度（mock call_llm 验证）。
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.submission_package.agent import SubmissionPackageAgent
from app.utils.exceptions import AgentException


@pytest.fixture
def agent():
    return SubmissionPackageAgent()


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
async def test_default_task_is_checklist(agent):
    """不带 task 时默认走 checklist"""
    with patch.object(agent, "call_llm", new=AsyncMock(return_value="stub")):
        result = await agent.process({"artefacts": {"abstract": "x"}})
    assert result["checklist"] == "stub"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "task,key,field",
    [
        ("match_journal", "journal_matches", "abstract"),
        ("checklist", "checklist", "artefacts"),
        ("consistency_check", "consistency", "artefacts"),
    ],
)
async def test_known_tasks_dispatch(agent, task, key, field):
    """三个已知 task 正确分派到对应 handler（返回键映射）"""
    request = {"task": task}
    if field == "abstract":
        request["abstract"] = "A novel machine learning study."
    else:
        request["artefacts"] = {"abstract": "x"}
    with patch.object(agent, "call_llm", new=AsyncMock(return_value="stub")):
        result = await agent.process(request)
    assert result[key] == "stub"


# ─────────────────────────────────────────────
# 确定性温度
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_match_journal_uses_zero_temperature(agent):
    """期刊匹配是确定性任务，call_llm 应以 temperature=0.0 调用"""
    with patch.object(agent, "call_llm", new=AsyncMock(return_value="stub")) as mock_llm:
        await agent.match_journal({"abstract": "x"})
    assert mock_llm.call_args.kwargs["temperature"] == 0.0

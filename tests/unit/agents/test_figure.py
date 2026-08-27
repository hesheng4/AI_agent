"""Figure Agent 单元测试

本轮补齐：figure 模块此前仅被 P1-7 一致性测试间接触达。覆盖任务分派
（含 generate 别名）、契约校验（原型/backend 白名单）、未知任务。
FigureAgent 刻意不继承 BaseAgent（纯 matplotlib，零 LLM），无需 mock。
"""

import pytest

from app.agents.figure.agent import FigureAgent
from app.utils.exceptions import ToolException


@pytest.fixture
def agent():
    return FigureAgent()


# ─────────────────────────────────────────────
# 任务分派
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_contract_returns_contract_fields(agent):
    """create_contract 返回契约 dict（conclusion/archetype/backend/export_spec）"""
    result = await agent.process(
        {
            "task": "create_contract",
            "conclusion": "处理组显著优于对照组",
            "evidence_chain": ["e1", "e2"],
            "archetype": "comparison",
        }
    )
    assert result["conclusion"] == "处理组显著优于对照组"
    assert result["evidence_chain"] == ["e1", "e2"]
    assert result["archetype"] == "comparison"
    assert result["backend"] == "python"  # 默认 backend
    assert result["export_spec"]  # 期刊导出规范随契约返回


@pytest.mark.asyncio
async def test_generate_alias_equals_create_contract(agent):
    """'generate' 是工作流模板（write_from_scratch 第 7 步）的任务名，等价 create_contract"""
    result = await agent.process(
        {"task": "generate", "conclusion": "c", "evidence_chain": []}
    )
    assert result["conclusion"] == "c"
    assert result["archetype"] == "comparison"  # 默认原型


@pytest.mark.asyncio
async def test_unknown_task_raises_tool_exception(agent):
    """未知 task 应抛 ToolException（与 BaseAgent 家族的 AgentException 区分）"""
    with pytest.raises(ToolException, match="未知任务"):
        await agent.process({"task": "non-existent"})


# ─────────────────────────────────────────────
# 契约校验
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invalid_archetype_rejected(agent):
    """原型不在白名单 → ValueError（拒绝猜测）"""
    with pytest.raises(ValueError, match="未知图原型"):
        await agent.process(
            {
                "task": "create_contract",
                "conclusion": "c",
                "evidence_chain": [],
                "archetype": "banana",
            }
        )


@pytest.mark.asyncio
async def test_invalid_backend_rejected(agent):
    """backend 非 python/r → ValueError（必须明确选择）"""
    with pytest.raises(ValueError, match="backend"):
        await agent.process(
            {
                "task": "create_contract",
                "conclusion": "c",
                "evidence_chain": [],
                "archetype": "comparison",
                "backend": "java",
            }
        )

"""Coordinator 路由一致性回归测试（体检报告 P1-7）

锁住三类脱节，任一再现即测试失败：
1. SKILL_KEYWORD_MAP / CAPABILITY_MAP / WORKFLOW_TEMPLATES 引用的
   agent 必须都在 Agent 注册表中（figure 曾不在注册表 → 必然崩溃）。
2. 关键词特异性：「数据可用性」→ data_agent，不再拖上通用的 data
   （data 收到 statement 任务曾必然抛「未知任务类型」）。
3. 工作流模板的任务名必须被对应 agent 的分派表接受。
"""

import pytest

from app.agents.coordinator.planner import (
    CAPABILITY_MAP,
    SKILL_KEYWORD_MAP,
    WORKFLOW_TEMPLATES,
    TaskPlanner,
)
from app.agents.registry import get_agent_registry

# ---------------------------------------------------------------------------
# 1. 三张表 ↔ 注册表 一致性
# ---------------------------------------------------------------------------


def test_keyword_map_agents_in_registry():
    registry = get_agent_registry()
    missing = [name for name, *_ in SKILL_KEYWORD_MAP if name not in registry]
    assert not missing, f"SKILL_KEYWORD_MAP 引用了未注册 agent: {missing}"


def test_capability_map_agents_in_registry():
    registry = get_agent_registry()
    missing = [name for name in CAPABILITY_MAP if name not in registry]
    assert not missing, f"CAPABILITY_MAP 引用了未注册 agent: {missing}"


def test_workflow_agents_in_registry():
    registry = get_agent_registry()
    missing = [
        step["agent"]
        for wf in WORKFLOW_TEMPLATES.values()
        for step in wf["steps"]
        if step["agent"] not in registry
    ]
    assert not missing, f"WORKFLOW_TEMPLATES 引用了未注册 agent: {sorted(set(missing))}"


def test_coordinator_can_load_every_registered_agent():
    """注册表中的每个条目都能被 coordinator 懒加载（模块路径/类名有效）。"""
    from app.agents.coordinator.agent import CoordinatorAgent

    coord = CoordinatorAgent()
    for name in get_agent_registry():
        agent = coord.get_agent(name)  # 不存在的条目会抛 AgentException
        assert agent is not None


# ---------------------------------------------------------------------------
# 2. 关键词路由正确性
# ---------------------------------------------------------------------------


def test_data_availability_routes_to_data_agent_only():
    planner = TaskPlanner(agents={})
    agents = planner.identify_agents({"task": "生成数据可用性声明"})
    assert "data_agent" in agents
    assert "data" not in agents, (
        f"「数据可用性」不应再路由到通用 data agent: {agents}"
    )


def test_data_analysis_still_routes_to_data():
    planner = TaskPlanner(agents={})
    assert planner.identify_agents({"task": "数据分析"}) == ["data"]


def test_figure_keyword_routes():
    planner = TaskPlanner(agents={})
    assert "figure" in planner.identify_agents({"task": "帮我作图"})


# ---------------------------------------------------------------------------
# 3. 工作流任务名 ↔ agent 分派表
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_figure_agent_accepts_workflow_generate_task():
    """write_from_scratch 第 7 步用 task=generate 调 figure。"""
    from app.agents.figure.agent import FigureAgent

    result = await FigureAgent().process(
        {"task": "generate", "conclusion": "c", "evidence_chain": []}
    )
    assert "conclusion" in result  # create_contract 返回 contract 字典


def test_data_agent_accepts_generate_statement():
    """write_from_scratch 第 8 步用 task=generate-statement 调 data_agent。"""
    from app.agents.data_agent.agent import DataAvailabilityAgent

    agent = DataAvailabilityAgent()
    assert "generate-statement" in agent._task_handlers

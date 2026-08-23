"""Coordinator Agent 单元测试

本轮新建：coordinator 此前零测试。覆盖关键词路由、任务分解、依赖分析、
循环依赖检测、懒加载（CO1 回归）、单例（CO7）。
"""

from unittest.mock import MagicMock, patch

import pytest

from app.agents.coordinator import CoordinatorAgent, get_coordinator_agent
from app.agents.coordinator.planner import TaskPlanner
from app.agents.registry import get_agent_registry
from app.utils.exceptions import AgentException


@pytest.fixture
def coordinator():
    return CoordinatorAgent()


@pytest.fixture
def planner():
    return TaskPlanner()


# ─────────────────────────────────────────────
# planner: 关键词路由
# ─────────────────────────────────────────────


def test_identify_agents_exact_match(planner):
    """精确匹配 task 字段"""
    result = planner.identify_agents({"task": "citation"})
    assert "citation" in result


def test_identify_agents_alias(planner):
    """别名匹配"""
    result = planner.identify_agents({"task": "cite"})
    assert "citation" in result


def test_identify_agents_keyword_scan(planner):
    """task 含关键词"""
    result = planner.identify_agents({"task": "我需要参考文献格式化"})
    assert "citation" in result


def test_identify_agents_fallback_full_request(planner):
    """task 无匹配时扫描整个 request"""
    result = planner.identify_agents({"task": "", "content": "请帮我做统计分析"})
    assert "stats" in result


def test_identify_agents_no_match_returns_empty(planner):
    """无任何匹配返回空列表"""
    result = planner.identify_agents({"task": "xyz", "content": ""})
    assert result == []


def test_identify_agents_dedupe(planner):
    """多关键词命中同一 agent 应去重"""
    result = planner.identify_agents({"task": "citation cite 引用"})
    # citation 应只出现一次
    assert result.count("citation") == 1


# ─────────────────────────────────────────────
# planner: 任务分解与依赖
# ─────────────────────────────────────────────


def test_decompose_task(planner):
    subtasks = planner.decompose_task({"task": "x"}, ["citation", "cover"])
    assert len(subtasks) == 2
    assert subtasks[0]["agent"] == "citation"
    assert subtasks[1]["agent"] == "cover"
    assert subtasks[0]["dependencies"] == []


def test_analyze_dependencies(planner):
    subtasks = [{"agent": "writing", "request": {}, "dependencies": []}]
    plan = planner.analyze_dependencies(subtasks)
    # writing 依赖 literature/reader
    assert "literature" in plan[0]["dependencies"]
    assert "reader" in plan[0]["dependencies"]


# ─────────────────────────────────────────────
# coordinator: 循环依赖检测
# ─────────────────────────────────────────────


def test_group_by_level_detects_cycle(coordinator):
    """循环依赖应抛 AgentException"""
    # 构造 a 依赖 b、b 依赖 a 的循环
    plan = [
        {"agent": "a", "dependencies": ["b"], "request": {}},
        {"agent": "b", "dependencies": ["a"], "request": {}},
    ]
    with pytest.raises(AgentException, match="循环依赖"):
        coordinator._group_by_level(plan)


def test_group_by_level_normal(coordinator):
    """正常依赖应分层"""
    plan = [
        {"agent": "a", "dependencies": [], "request": {}},
        {"agent": "b", "dependencies": ["a"], "request": {}},
    ]
    levels = coordinator._group_by_level(plan)
    assert len(levels) == 2
    assert levels[0][0]["agent"] == "a"
    assert levels[1][0]["agent"] == "b"


# ─────────────────────────────────────────────
# CO1 回归：懒加载
# ─────────────────────────────────────────────


def test_lazy_loading_no_instances_at_init(coordinator):
    r"""CO1 修复：__init__ 后不应预建任何子 agent 实例

    旧版 __init__ 立即实例化全部 16 个子 agent（每个含 LLMClient）。
    修复后懒加载，__init__ 后实例缓存应为空。
    """
    assert coordinator._agent_instances == {}


def test_get_agent_lazy_loads(coordinator):
    """首次 get_agent 应触发实例化并缓存"""
    # 先完成注册表扫描（用真实类注册），再 patch 子模块类：
    # coordinator.get_agent 经 registry 动态
    # importlib.import_module("app.agents.citation.agent") 后取类，
    # 包级导出 app.agents.citation.CitationAgent 不是真实加载路径；
    # 若在 patch 后才首次扫描，mock 类无法通过 inspect.isclass 注册。
    get_agent_registry()
    with patch("app.agents.citation.agent.CitationAgent") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        # 清缓存确保首次调用
        coordinator._agent_instances.clear()
        result = coordinator.get_agent("citation")
        assert result is mock_instance
        assert "citation" in coordinator._agent_instances


def test_get_agent_unknown_raises(coordinator):
    with pytest.raises(AgentException, match="未知Agent"):
        coordinator.get_agent("non_existent")


def test_get_agent_caches(coordinator):
    """同一 agent 第二次调用应返回缓存实例"""
    coordinator._agent_instances.clear()
    first = coordinator.get_agent("citation")
    second = coordinator.get_agent("citation")
    assert first is second


# ─────────────────────────────────────────────
# CO7 回归：单例工厂
# ─────────────────────────────────────────────


def test_singleton_factory_returns_same_instance():
    a = get_coordinator_agent()
    b = get_coordinator_agent()
    assert a is b


def test_singleton_is_coordinator_agent():
    assert isinstance(get_coordinator_agent(), CoordinatorAgent)


# ─────────────────────────────────────────────
# process_simple：未知任务抛错
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_process_simple_unknown_task_raises(coordinator):
    with pytest.raises(AgentException, match="未知任务类型"):
        await coordinator.process_simple({"task": "xyz_no_match"})


# ─────────────────────────────────────────────
# _integrate_results
# ─────────────────────────────────────────────


def test_integrate_results_success(coordinator):
    results = [
        {"agent": "a", "result": {"x": 1}, "status": "success"},
        {"agent": "b", "result": {"y": 2}, "status": "success"},
    ]
    integrated = coordinator._integrate_results(results)
    assert integrated["status"] == "success"
    assert integrated["agents_used"] == ["a", "b"]
    assert integrated["results"]["a"] == {"x": 1}
    assert integrated["failed_agents"] == []


def test_integrate_results_partial_failure(coordinator):
    results = [
        {"agent": "a", "result": {"x": 1}, "status": "success"},
        {"agent": "b", "result": {"error": "e"}, "status": "failed"},
    ]
    integrated = coordinator._integrate_results(results)
    assert integrated["status"] == "partial_failure"
    assert integrated["failed_agents"] == ["b"]

"""workflow_to_execution_plan DAG 校验回归测试（架构文档差距 #9）

锁住三重校验的异常类型契约：API 层（api/v1/workflows.py run 端点）
只捕获 ValueError 转 400，任何分支抛其他类型都会漏成 500。

历史缺陷：「重复 agent 名」分支 f-string 后误带 `(`，把字符串当函数
调用，触发时抛 TypeError（2026-08-27 实测复现）。
"""

import pytest

from app.core.workflows import workflow_to_execution_plan

# ---------------------------------------------------------------------------
# 1. 重复 agent 名（原 TypeError 缺陷分支）
# ---------------------------------------------------------------------------


def test_duplicate_agent_raises_value_error():
    """重复 agent 名必须抛 ValueError（API 层靠它转 400），而非 TypeError。"""
    wf = {
        "nodes": [
            {"id": "a1", "agent": "data", "task": "analyze"},
            {"id": "b1", "agent": "data", "task": "visualize"},
        ],
        "edges": [],
    }
    with pytest.raises(ValueError, match="重复 agent 名"):
        workflow_to_execution_plan(wf)


def test_duplicate_agent_message_names_both_nodes():
    """错误信息应指明冲突的两个节点 id，便于用户定位。"""
    wf = {
        "nodes": [
            {"id": "n10", "agent": "writing"},
            {"id": "n20", "agent": "writing"},
        ],
        "edges": [],
    }
    with pytest.raises(ValueError) as exc_info:
        workflow_to_execution_plan(wf)
    msg = str(exc_info.value)
    assert "n10" in msg and "n20" in msg


# ---------------------------------------------------------------------------
# 2. 自环 / 循环（W4a/W4b，防回归：修 #9 时别把这两条弄坏）
# ---------------------------------------------------------------------------


def test_self_loop_raises_value_error():
    wf = {
        "nodes": [{"id": "a1", "agent": "data"}],
        "edges": [{"source": "a1", "target": "a1"}],
    }
    with pytest.raises(ValueError, match="自环依赖"):
        workflow_to_execution_plan(wf)


def test_cycle_raises_value_error():
    wf = {
        "nodes": [
            {"id": "a1", "agent": "data"},
            {"id": "b1", "agent": "stats"},
        ],
        "edges": [
            {"source": "a1", "target": "b1"},
            {"source": "b1", "target": "a1"},
        ],
    }
    with pytest.raises(ValueError, match="循环依赖"):
        workflow_to_execution_plan(wf)


# ---------------------------------------------------------------------------
# 3. 缺失字段与合法计划（边界 + 正向）
# ---------------------------------------------------------------------------


def test_missing_agent_field_raises_value_error():
    wf = {
        "nodes": [{"id": "a1", "task": "analyze"}],
        "edges": [],
    }
    with pytest.raises(ValueError, match="缺少 agent 字段"):
        workflow_to_execution_plan(wf)


def test_valid_plan_maps_edges_to_dependencies():
    """合法 DAG：edges 的 source 映射为目标节点 request.dependencies（agent 名）。"""
    wf = {
        "nodes": [
            {"id": "a1", "agent": "literature", "task": "search"},
            {"id": "b1", "agent": "writing", "task": "draft"},
        ],
        "edges": [{"source": "a1", "target": "b1"}],
    }
    plan = workflow_to_execution_plan(wf)
    assert {t["agent"]: t["dependencies"] for t in plan} == {
        "literature": [],
        "writing": ["literature"],
    }

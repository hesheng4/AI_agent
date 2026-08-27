"""差距 #3 回归：上游结果字段级注入 = 声明式 UPSTREAM_FIELD_MAP

重构前 _inject_upstream 是 4 组硬编码 if 链，且零测试覆盖；本次把映射
提为 planner.py 的 UPSTREAM_FIELD_MAP（{下游 agent: {目标字段: (上游,
源字段)}}），本文件锁定其契约：

1. upstream_results 整体可见（所有命中依赖的上游结果）；
2. writing ← literature 的 papers/summaries；
   data ← literature 的 papers + experiment 的 plan；
3. 调用方显式传入的字段优先（只补缺失字段）；
4. 源字段缺失/上游结果为 None 时不注入空值；
5. 映射表引用的 agent 必须都在注册表（P1-7 式表↔注册表一致性）。
"""

import pytest

from app.agents.coordinator import CoordinatorAgent
from app.agents.coordinator.planner import UPSTREAM_FIELD_MAP
from app.agents.registry import get_agent_registry


@pytest.fixture
def coordinator():
    return CoordinatorAgent()


# ─────────────────────────────────────────────
# 基础语义
# ─────────────────────────────────────────────


def test_no_deps_returns_task_unchanged(coordinator):
    """无依赖 → 原样返回，不重建 dict"""
    task = {"agent": "writing", "request": {"content": "x"}, "dependencies": []}
    assert coordinator._inject_upstream(task, {}) is task


def test_deps_absent_from_context_copies_but_injects_nothing(coordinator):
    """依赖未在 context（未执行成功）→ 复制语义保留，不注入任何字段"""
    task = {"agent": "writing", "request": {"content": "x"}, "dependencies": ["literature"]}
    out = coordinator._inject_upstream(task, {})
    assert out is not task
    assert out["request"] == {"content": "x"}
    assert "upstream_results" not in out["request"]


def test_upstream_results_contains_all_deps_in_context(coordinator):
    """upstream_results 聚合所有命中依赖的上游结果"""
    task = {"agent": "writing", "request": {}, "dependencies": ["literature", "reader"]}
    context = {"literature": {"papers": ["p1"]}, "reader": {"paper_md": "t"}}
    out = coordinator._inject_upstream(task, context)
    assert set(out["request"]["upstream_results"]) == {"literature", "reader"}


# ─────────────────────────────────────────────
# 字段级注入（声明式映射行为）
# ─────────────────────────────────────────────


def test_writing_receives_papers_and_summaries(coordinator):
    task = {"agent": "writing", "request": {}, "dependencies": ["literature", "reader"]}
    context = {"literature": {"papers": ["p1"], "summaries": {"p1": "s1"}}}
    out = coordinator._inject_upstream(task, context)
    assert out["request"]["papers"] == ["p1"]
    assert out["request"]["summaries"] == {"p1": "s1"}


def test_data_receives_papers_and_experiment_plan(coordinator):
    task = {
        "agent": "data",
        "request": {},
        "dependencies": ["experiment", "literature"],
    }
    context = {"experiment": {"plan": "plan-A"}, "literature": {"papers": ["p9"]}}
    out = coordinator._inject_upstream(task, context)
    assert out["request"]["experiment_plan"] == "plan-A"
    assert out["request"]["papers"] == ["p9"]


def test_explicit_request_fields_take_priority(coordinator):
    """显式传入优先：已存在的字段不覆盖，缺失的仍补"""
    task = {
        "agent": "writing",
        "request": {"papers": ["mine"]},
        "dependencies": ["literature"],
    }
    context = {"literature": {"papers": ["theirs"], "summaries": {"a": "s"}}}
    out = coordinator._inject_upstream(task, context)
    assert out["request"]["papers"] == ["mine"]
    assert out["request"]["summaries"] == {"a": "s"}


def test_missing_source_field_not_injected(coordinator):
    """源字段缺失 → 目标字段保持不存在（不注入空值）"""
    task = {"agent": "writing", "request": {}, "dependencies": ["literature"]}
    context = {"literature": {"papers": ["p1"]}}  # 无 summaries
    out = coordinator._inject_upstream(task, context)
    assert out["request"]["papers"] == ["p1"]
    assert "summaries" not in out["request"]


def test_none_upstream_result_treated_as_empty(coordinator):
    """上游结果为 None（防御）→ 视为空，不注入；整体仍可见"""
    task = {"agent": "data", "request": {}, "dependencies": ["experiment"]}
    out = coordinator._inject_upstream(task, {"experiment": None})
    assert out["request"]["upstream_results"] == {"experiment": None}
    assert "experiment_plan" not in out["request"]


def test_agent_without_mapping_gets_whole_visibility_only(coordinator):
    """映射表外的 agent：只有 upstream_results 整体，无字段注入"""
    task = {"agent": "reviewer", "request": {}, "dependencies": ["writing"]}
    out = coordinator._inject_upstream(task, {"writing": {"draft": "d"}})
    assert out["request"] == {"upstream_results": {"writing": {"draft": "d"}}}


# ─────────────────────────────────────────────
# 映射表一致性（P1-7 式：表 ↔ 注册表）
# ─────────────────────────────────────────────


def test_map_agents_registered():
    """映射表引用的下游/上游 agent 必须都在注册表（防拼写漂移）"""
    registry = get_agent_registry()
    for down_agent, fields in UPSTREAM_FIELD_MAP.items():
        assert down_agent in registry, f"下游 {down_agent} 未在注册表"
        for up_agent, _ in fields.values():
            assert up_agent in registry, f"上游 {up_agent} 未在注册表"

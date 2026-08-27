"""TaskPlanner.complete_upstream 上游补全回归测试（架构文档差距：静态依赖表闭包问题）

锁住两类行为：
1. 传递闭包：命中 writing 时自动补 literature/reader；命中 reviewer 时
   沿 reviewer → writing → literature/reader 补齐整条链。
2. 只补不删不改序：显式命中的 agent 保持原顺序，补全的上游追加在尾部
   （_group_by_level 按依赖拓扑分层，顺序不影响正确性，但保序让日志可读）。
"""

from app.agents.coordinator.planner import TaskPlanner


def test_complete_writing_pulls_literature_and_reader():
    planner = TaskPlanner(agents={})
    assert planner.complete_upstream(["writing"]) == [
        "writing",
        "literature",
        "reader",
    ]


def test_complete_reviewer_pulls_full_transitive_chain():
    """reviewer → writing → literature/reader，stats/methods 自身无依赖。"""
    planner = TaskPlanner(agents={})
    assert planner.complete_upstream(["reviewer"]) == [
        "reviewer",
        "writing",
        "stats",
        "methods",
        "literature",
        "reader",
    ]


def test_complete_response_chain():
    """response → reviewer → writing/stats/methods → literature/reader。"""
    planner = TaskPlanner(agents={})
    assert planner.complete_upstream(["response"]) == [
        "response",
        "reviewer",
        "writing",
        "stats",
        "methods",
        "literature",
        "reader",
    ]


def test_complete_preserves_order_and_dedupes():
    planner = TaskPlanner(agents={})
    # 显式已含部分上游 → 不重复补；命中顺序保留
    assert planner.complete_upstream(["writing", "literature"]) == [
        "writing",
        "literature",
        "reader",
    ]
    assert planner.complete_upstream(["literature", "reader", "writing"]) == [
        "literature",
        "reader",
        "writing",
    ]
    # 空输入
    assert planner.complete_upstream([]) == []


def test_complete_no_cycle_in_static_table():
    """静态依赖表本身无环，闭包必然终止且集合确定。"""
    planner = TaskPlanner(agents={})
    everything = planner.complete_upstream(
        ["writing", "data", "polishing", "reviewer", "cover",
         "submission_package", "response"]
    )
    # 幂等：对已补全集合再补一遍不变
    assert planner.complete_upstream(everything) == everything
    # data → experiment 也被带上
    assert "experiment" in everything

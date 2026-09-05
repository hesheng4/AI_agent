"""E6 运行记录存储回归：签名 / 分类 / 状态机 / 并发守卫 / cap-on-write / resume 集合

设计契约: docs/plans/workflow-error-recovery-v1.md（grill 逐项决策）
- plan_signature: 同计划同签名（有序 (agent, task) 对），request 内部字段不影响
- classify_failure: hint-only transient | permanent | unknown，不挂任何行为
- 状态机: 仅 failed →(claim)→ running；running/succeeded 不可接管（并发 resume 409）
- cap-on-write: 超出 RUN_RETENTION_LIMIT 裁剪最旧，刚写入的永不被裁
- compute_resume_sets: 重执行 = failed ∪ pending ∪ 传递依赖下游；
  已完成 = success 且不在重执行集合（其载荷预注入，不重复 LLM 工作）
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.config import get_settings
from app.core import runs
from app.core.runs import (
    RUN_FAILED,
    RUN_RUNNING,
    RUN_SUCCEEDED,
    claim_run_for_resume,
    classify_failure,
    compute_resume_sets,
    create_run,
    finalize_run,
    get_run,
    list_run_summaries,
    plan_signature,
)
from app.utils.exceptions import (
    AgentException,
    AppException,
    LLMRateLimitException,
    LLMTimeoutException,
    StepTimeoutError,
    ToolException,
    ValidationException,
)


@pytest.fixture
def runs_dir(tmp_path, monkeypatch):
    """隔离 data/runs/ 到临时目录，防污染真实存储"""
    d = tmp_path / "runs"
    monkeypatch.setattr(runs, "_RUNS_DIR", d)
    return d


def _chain_plan():
    return [
        {"agent": "a", "request": {"task": "t1"}, "dependencies": []},
        {"agent": "b", "request": {"task": "t2"}, "dependencies": ["a"]},
        {"agent": "c", "request": {"task": "t3"}, "dependencies": ["a", "b"]},
    ]


def _step(record: dict, agent: str) -> dict:
    return next(s for s in record["steps"] if s["agent"] == agent)


# ─────────────────────────────────────────────
# plan_signature
# ─────────────────────────────────────────────


def test_plan_signature_stable_and_order_sensitive():
    p1 = _chain_plan()
    p2 = _chain_plan()
    assert plan_signature(p1) == plan_signature(p2)
    reordered = list(reversed(p1))
    assert plan_signature(reordered) != plan_signature(p1)


def test_plan_signature_ignores_request_fields():
    """签名只含 (agent, task)：request 内部字段（凭据/自由文本）不影响"""
    p1 = [{"agent": "a", "request": {"task": "t1", "content": "x"}, "dependencies": []}]
    p2 = [{"agent": "a", "request": {"task": "t1"}, "dependencies": []}]
    assert plan_signature(p1) == plan_signature(p2)


def test_plan_signature_task_text_matters():
    p1 = [{"agent": "a", "request": {"task": "t1"}, "dependencies": []}]
    p2 = [{"agent": "a", "request": {"task": "changed"}, "dependencies": []}]
    assert plan_signature(p1) != plan_signature(p2)


# ─────────────────────────────────────────────
# classify_failure（hint-only）
# ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (LLMRateLimitException(), "transient"),
        (LLMTimeoutException(), "transient"),
        (StepTimeoutError("超时"), "transient"),
        (TimeoutError(), "transient"),
        (ValidationException("bad"), "permanent"),
        (AgentException("boom", "a"), "unknown"),
        (ToolException("boom"), "unknown"),
        (ValueError("boom"), "unknown"),
        (AppException("boom", code="LLM_RATE_LIMIT"), "transient"),
        (AppException("boom", code="VALIDATION_ERROR"), "permanent"),
        (None, "unknown"),
    ],
)
def test_classify_failure_mapping(exc, expected):
    assert classify_failure(exc) == expected


# ─────────────────────────────────────────────
# 记录生命周期
# ─────────────────────────────────────────────


def test_create_run_initializes_pending_steps(runs_dir):
    rec = create_run(
        "u1",
        {"kind": "template", "template_id": "revise"},
        {"task": "x"},
        _chain_plan(),
    )
    record = get_run("u1", rec.run_id)
    assert record["status"] == RUN_RUNNING
    assert record["plan_signature"] == plan_signature(_chain_plan())
    assert [s["status"] for s in record["steps"]] == ["pending"] * 3
    # 冻结请求不含 _ 前缀字段由调用方负责；此处存的是传入原样
    assert record["request"] == {"task": "x"}


def test_step_finished_success_and_failure(runs_dir):
    rec = create_run(
        "u1", {"kind": "workflow", "workflow_id": "a" * 12}, {}, _chain_plan()
    )
    rec.step_finished("a", status="success", result={"out": 1}, started_at="t0")
    rec.step_finished("b", status="failed", error="boom", failure_class="transient")
    record = get_run("u1", rec.run_id)
    a, b = _step(record, "a"), _step(record, "b")
    assert a["status"] == "success" and a["result"] == {"out": 1}
    assert a["attempts"] == 1 and a["started_at"] == "t0"
    assert b["status"] == "failed" and b["error"] == "boom"
    assert b["failure_class"] == "transient"


def test_step_reexecution_increments_attempts(runs_dir):
    rec = create_run(
        "u1", {"kind": "workflow", "workflow_id": "a" * 12}, {}, _chain_plan()
    )
    rec.step_finished("a", status="failed", error="x", failure_class="transient")
    rec.step_finished("a", status="success", result={"ok": True})
    record = get_run("u1", rec.run_id)
    a = _step(record, "a")
    assert a["attempts"] == 2 and a["status"] == "success" and a["error"] == ""
    # v2 自动重试：失败尝试证据链保全（成功后仍可追溯）
    assert len(a["attempt_errors"]) == 1
    assert a["attempt_errors"][0]["failure_class"] == "transient"


def test_get_run_user_isolation(runs_dir):
    rec = create_run(
        "u1", {"kind": "workflow", "workflow_id": "a" * 12}, {}, _chain_plan()
    )
    assert get_run("u2", rec.run_id) is None
    assert get_run("u1", rec.run_id) is not None


def test_list_run_summaries_newest_first_without_payloads(runs_dir):
    r1 = create_run(
        "u1", {"kind": "workflow", "workflow_id": "a" * 12}, {}, _chain_plan()
    )
    r2 = create_run(
        "u1", {"kind": "workflow", "workflow_id": "b" * 12}, {}, _chain_plan()
    )
    r2.step_finished("a", status="success", result={"big": "payload"})
    summaries = list_run_summaries("u1")
    assert [s["run_id"] for s in summaries] == [r2.run_id, r1.run_id]
    assert all("result" not in step for s in summaries for step in s["steps"])


def test_finalize_validates_status(runs_dir):
    rec = create_run(
        "u1", {"kind": "workflow", "workflow_id": "a" * 12}, {}, _chain_plan()
    )
    with pytest.raises(ValueError):
        finalize_run("u1", rec.run_id, status="bogus")


# ─────────────────────────────────────────────
# 并发守卫（failed → running 原子接管）
# ─────────────────────────────────────────────


def test_claim_guard_only_failed(runs_dir):
    rec = create_run(
        "u1", {"kind": "workflow", "workflow_id": "a" * 12}, {}, _chain_plan()
    )
    # running 状态不可接管
    assert claim_run_for_resume("u1", rec.run_id, "task1") is False
    finalize_run("u1", rec.run_id, status=RUN_SUCCEEDED)
    assert claim_run_for_resume("u1", rec.run_id) is False
    # failed → running 成功；二次 claim（已是 running）被拒
    finalize_run("u1", rec.run_id, status=RUN_FAILED, error="x")
    assert claim_run_for_resume("u1", rec.run_id, "task2") is True
    record = get_run("u1", rec.run_id)
    assert record["status"] == RUN_RUNNING
    assert "task2" in record["task_ids"]
    assert claim_run_for_resume("u1", rec.run_id) is False


def test_prune_cap_on_write(runs_dir, monkeypatch):
    monkeypatch.setattr(get_settings(), "RUN_RETENTION_LIMIT", 2)
    r1 = create_run(
        "u1", {"kind": "workflow", "workflow_id": "a" * 12}, {}, _chain_plan()
    )
    r2 = create_run(
        "u1", {"kind": "workflow", "workflow_id": "b" * 12}, {}, _chain_plan()
    )
    r3 = create_run(
        "u1", {"kind": "workflow", "workflow_id": "c" * 12}, {}, _chain_plan()
    )
    assert get_run("u1", r1.run_id) is None  # 最旧被裁
    assert get_run("u1", r2.run_id) is not None
    assert get_run("u1", r3.run_id) is not None


# ─────────────────────────────────────────────
# compute_resume_sets
# ─────────────────────────────────────────────


def _diamond_plan():
    return [
        {"agent": "a", "request": {}, "dependencies": []},
        {"agent": "b", "request": {}, "dependencies": ["a"]},
        {"agent": "c", "request": {}, "dependencies": ["a"]},
        {"agent": "d", "request": {}, "dependencies": ["b", "c"]},
    ]


def test_resume_sets_failed_and_transitive_dependents(runs_dir):
    """菱形 DAG：b 失败 → d 依赖 b 必须重跑；独立分支 c 的成功产出保留"""
    rec = create_run(
        "u1", {"kind": "workflow", "workflow_id": "a" * 12}, {}, _diamond_plan()
    )
    rec.step_finished("a", status="success", result={"x": 1})
    rec.step_finished("b", status="failed", error="boom", failure_class="unknown")
    rec.step_finished("c", status="success", result={"y": 2})
    rec.step_finished("d", status="success", result={"z": 3})  # 曾带缺失上游跑过
    rerun, completed = compute_resume_sets(get_run("u1", rec.run_id))
    assert rerun == ["b", "d"]
    assert completed == [
        {"agent": "a", "result": {"x": 1}},
        {"agent": "c", "result": {"y": 2}},
    ]


def test_resume_sets_includes_pending_steps(runs_dir):
    """fail-fast 中止产生的 pending 步骤（未执行过）全部纳入重执行"""
    rec = create_run(
        "u1", {"kind": "workflow", "workflow_id": "a" * 12}, {}, _chain_plan()
    )
    rec.step_finished("a", status="success", result={"x": 1})
    rec.step_finished("b", status="failed", error="boom", failure_class="transient")
    # c 因 fail-fast 未执行，保持 pending
    rerun, completed = compute_resume_sets(get_run("u1", rec.run_id))
    assert rerun == ["b", "c"]
    assert completed == [{"agent": "a", "result": {"x": 1}}]


# ─────────────────────────────────────────────
# v2: 进程中断遗留的 running 记录接管
# ─────────────────────────────────────────────


def _backdate_record(runs_dir, user_id: str, run_id: str, hours: float) -> None:
    """把记录 updated_at 回写为 hours 小时前（模拟进程中断后无活动）

    绕过 _save_run 直写文件：_save_run 每次落盘都会重刷 updated_at
    （活动语义），会把回写覆盖掉。
    """
    import json

    path = runs_dir / f"{user_id}_{run_id}.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["updated_at"] = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")


def test_claim_stale_running_record(runs_dir, monkeypatch):
    """E6 v2：中断遗留的 running（超期无活动）可接管；活跃 running 拒绝"""
    monkeypatch.setattr(get_settings(), "RUN_STALE_AFTER", 3600)
    rec = create_run(
        "u1", {"kind": "workflow", "workflow_id": "a" * 12}, {}, _chain_plan()
    )
    # 活跃 running（updated_at = 刚刚）→ 不可接管，避免双跑
    assert (
        claim_run_for_resume("u1", rec.run_id, "t1", allow_stale_running=True) is False
    )

    _backdate_record(runs_dir, "u1", rec.run_id, hours=2)
    assert (
        claim_run_for_resume("u1", rec.run_id, "t2", allow_stale_running=True) is True
    )
    assert get_run("u1", rec.run_id)["status"] == RUN_RUNNING


def test_stale_claim_disabled_when_nonpositive(runs_dir, monkeypatch):
    """RUN_STALE_AFTER<=0 关闭接管（严格 v1：仅 failed 可恢复）"""
    monkeypatch.setattr(get_settings(), "RUN_STALE_AFTER", 0)
    rec = create_run(
        "u1", {"kind": "workflow", "workflow_id": "a" * 12}, {}, _chain_plan()
    )
    _backdate_record(runs_dir, "u1", rec.run_id, hours=99)
    assert (
        claim_run_for_resume("u1", rec.run_id, "t", allow_stale_running=True) is False
    )


def test_stale_claim_requires_opt_in(runs_dir, monkeypatch):
    """allow_stale_running=False（默认）时过期 running 仍不可接管"""
    monkeypatch.setattr(get_settings(), "RUN_STALE_AFTER", 3600)
    rec = create_run(
        "u1", {"kind": "workflow", "workflow_id": "a" * 12}, {}, _chain_plan()
    )
    _backdate_record(runs_dir, "u1", rec.run_id, hours=2)
    assert claim_run_for_resume("u1", rec.run_id, "t") is False

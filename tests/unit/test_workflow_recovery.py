"""E6 coordinator 恢复链路回归：checkpoint 落盘 / 步级超时 / resume 跳过已完成步

设计契约: docs/plans/workflow-error-recovery-v1.md
- 模板 fail-fast 失败 → run 记录 failed（failed 步含 failure_class，下游 pending）
- resume 预注入已完成载荷 → 已完成 agent 零重跑，失败步及其下游重执行
- 自定义 DAG partial_failure 语义保持；resume 重跑 failed 及其传递下游
- 步级墙钟超时合成 StepTimeoutError → 分类 transient → 正常 checkpoint
- v2 瞬态自动重试（opt-in，AGENT_STEP_MAX_RETRIES）：仅 transient 重试，
  中间失败尝试落盘 attempt_errors；无 recorder / 预算 0 时不重试
"""

import asyncio

import pytest

from app.agents.coordinator import CoordinatorAgent
from app.config import get_settings
from app.core import runs
from app.core.runs import (
    RUN_FAILED,
    RunRecorder,
    claim_run_for_resume,
    classify_failure,
    compute_resume_sets,
    create_run,
    finalize_run,
    get_run,
    plan_signature,
)
from app.utils.exceptions import (
    AgentException,
    LLMRateLimitException,
    LLMTimeoutException,
)


@pytest.fixture
def runs_dir(tmp_path, monkeypatch):
    d = tmp_path / "runs"
    monkeypatch.setattr(runs, "_RUNS_DIR", d)
    return d


class FakeAgent:
    """脚本化 Agent：按调用次数依序执行行为脚本，记录调用数"""

    def __init__(self, name: str, behaviors: list):
        self.name = name
        self.behaviors = (
            behaviors  # ("ok", payload) | ("raise", exc) | ("sleep", seconds)
        )
        self.calls = 0

    async def process(self, request: dict) -> dict:
        self.calls += 1
        action = self.behaviors[min(self.calls - 1, len(self.behaviors) - 1)]
        kind, value = action
        if kind == "sleep":
            await asyncio.sleep(value)
            return {"done": True}
        if kind == "raise":
            raise value
        return value


@pytest.fixture
def coordinator(monkeypatch):
    coord = CoordinatorAgent()
    fakes: dict[str, FakeAgent] = {}

    def _get_agent(name: str) -> FakeAgent:
        return fakes[name]

    coord._fakes = fakes
    monkeypatch.setattr(coord, "get_agent", _get_agent)
    return coord


def _recorder_for(plan: list[dict]) -> RunRecorder:
    return create_run("u_test", {"kind": "workflow", "workflow_id": "f" * 12}, {}, plan)


# ─────────────────────────────────────────────
# fail-fast 链：失败 checkpoint → resume 跳过已完成
# ─────────────────────────────────────────────


def _chain_plan():
    return [
        {"agent": "a", "request": {"task": "t1"}, "dependencies": []},
        {"agent": "b", "request": {"task": "t2"}, "dependencies": ["a"]},
        {"agent": "c", "request": {"task": "t3"}, "dependencies": ["a", "b"]},
    ]


@pytest.mark.asyncio
async def test_failfast_checkpoints_then_resume_skips_completed(coordinator, runs_dir):
    """b 首跑失败（transient）→ checkpoint failed；resume 后 a 零重跑、b/c 补齐"""
    fakes = coordinator._fakes
    fakes["a"] = FakeAgent("a", [("ok", {"step": "a-out"})])
    fakes["b"] = FakeAgent(
        "b", [("raise", LLMTimeoutException()), ("ok", {"step": "b-out"})]
    )
    fakes["c"] = FakeAgent("c", [("ok", {"step": "c-out"})])
    plan = _chain_plan()

    rec = create_run("u_test", {"kind": "template", "template_id": "revise"}, {}, plan)
    results = await coordinator._execute_plan_parallel(
        plan, "", fail_fast=True, run_recorder=rec
    )
    final1 = coordinator._integrate_results(results, fail_fast=True)
    assert final1["status"] == "failed"
    finalize_run("u_test", rec.run_id, status=RUN_FAILED, error=final1.get("error", ""))

    record = get_run("u_test", rec.run_id)
    assert record["status"] == RUN_FAILED
    by_agent = {s["agent"]: s for s in record["steps"]}
    assert by_agent["a"]["status"] == "success"
    assert by_agent["b"]["status"] == "failed"
    assert by_agent["b"]["failure_class"] == "transient"
    assert by_agent["c"]["status"] == "pending"
    assert fakes["c"].calls == 0, "fail-fast 后下游不应执行"
    assert record["plan_signature"] == plan_signature(plan)

    # resume：接管 + 预注入已完成结果
    rerun, completed_entries = compute_resume_sets(record)
    assert rerun == ["b", "c"]
    assert completed_entries == [{"agent": "a", "result": {"step": "a-out"}}]
    assert claim_run_for_resume("u_test", rec.run_id, "task-resume") is True

    results2 = await coordinator._execute_plan_parallel(
        plan,
        "task-resume",
        fail_fast=True,
        run_recorder=RunRecorder("u_test", rec.run_id),
        completed_results=completed_entries,
    )
    final2 = coordinator._integrate_results(results2, fail_fast=True)
    assert final2["status"] == "success"
    finalize_run("u_test", rec.run_id, status="succeeded")

    # 核心断言：a 未被重复执行（LLM 工作零重复），b 补跑成功，c 首次执行
    assert fakes["a"].calls == 1
    assert fakes["b"].calls == 2
    assert fakes["c"].calls == 1
    record2 = get_run("u_test", rec.run_id)
    by_agent2 = {s["agent"]: s for s in record2["steps"]}
    assert by_agent2["a"]["attempts"] == 1, "已完成步不应被 resume 触碰"
    assert by_agent2["b"]["attempts"] == 2 and by_agent2["b"]["status"] == "success"
    assert by_agent2["c"]["attempts"] == 1 and by_agent2["c"]["status"] == "success"


# ─────────────────────────────────────────────
# 自定义 DAG：partial_failure 语义保持 + 传递下游重跑
# ─────────────────────────────────────────────


def _diamond_plan():
    return [
        {"agent": "a", "request": {}, "dependencies": []},
        {"agent": "b", "request": {}, "dependencies": []},
        {"agent": "c", "request": {}, "dependencies": ["a", "b"]},
    ]


@pytest.mark.asyncio
async def test_custom_dag_partial_failure_then_resume_reruns_dependents(
    coordinator, runs_dir
):
    """并行层部分失败 → partial_failure 不中断；resume 重跑 failed 及其下游，
    独立成功分支不重跑"""
    fakes = coordinator._fakes
    fakes["a"] = FakeAgent(
        "a",
        [("raise", AgentException("deterministic boom", "a")), ("ok", {"step": "a2"})],
    )
    fakes["b"] = FakeAgent("b", [("ok", {"step": "b-out"})])
    fakes["c"] = FakeAgent(
        "c", [("ok", {"step": "c-run1"}), ("ok", {"step": "c-run2"})]
    )
    plan = _diamond_plan()

    rec = _recorder_for(plan)
    results = await coordinator._execute_plan_parallel(
        plan, "", fail_fast=False, run_recorder=rec
    )
    final1 = coordinator._integrate_results(results, fail_fast=False)
    assert final1["status"] == "partial_failure"
    assert final1["failed_agents"] == ["a"]
    run_status = "failed" if final1.get("failed_agents") else "succeeded"
    finalize_run("u_test", rec.run_id, status=run_status, error="")

    record = get_run("u_test", rec.run_id)
    by_agent = {s["agent"]: s for s in record["steps"]}
    assert by_agent["a"]["failure_class"] == classify_failure(
        AgentException("deterministic boom", "a")
    )
    # c 在 a 失败的情况下仍然执行过（partial_failure 语义保持）
    assert by_agent["c"]["status"] == "success" and fakes["c"].calls == 1

    rerun, completed_entries = compute_resume_sets(record)
    assert rerun == ["a", "c"], "c 消费过缺失上游，属传递下游必须重跑"
    assert claim_run_for_resume("u_test", rec.run_id, "task-resume") is True

    results2 = await coordinator._execute_plan_parallel(
        plan,
        "task-resume",
        fail_fast=False,
        run_recorder=RunRecorder("u_test", rec.run_id),
        completed_results=completed_entries,
    )
    final2 = coordinator._integrate_results(results2, fail_fast=False)
    assert final2["status"] == "success"
    assert fakes["a"].calls == 2
    assert fakes["b"].calls == 1, "独立成功分支不重跑"
    assert fakes["c"].calls == 2


# ─────────────────────────────────────────────
# 步级墙钟超时
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_step_timeout_synthesizes_transient_failure(
    coordinator, runs_dir, monkeypatch
):
    """挂死步超时 → StepTimeoutError（transient）→ checkpoint failed，可 resume"""
    monkeypatch.setattr(get_settings(), "AGENT_STEP_TIMEOUT", 0.05)
    fakes = coordinator._fakes
    fakes["a"] = FakeAgent("a", [("sleep", 1.0)])
    plan = [{"agent": "a", "request": {}, "dependencies": []}]

    rec = _recorder_for(plan)
    results = await coordinator._execute_plan_parallel(
        plan, "", fail_fast=True, run_recorder=rec
    )
    final = coordinator._integrate_results(results, fail_fast=True)
    assert final["status"] == "failed"

    record = get_run("u_test", rec.run_id)
    step = record["steps"][0]
    assert step["status"] == "failed"
    assert step["failure_class"] == "transient"
    assert "超过" in step["error"]


@pytest.mark.asyncio
async def test_step_timeout_disabled_when_nonpositive(
    coordinator, runs_dir, monkeypatch
):
    """AGENT_STEP_TIMEOUT<=0 关闭步级超时（回退无限等待）"""
    monkeypatch.setattr(get_settings(), "AGENT_STEP_TIMEOUT", 0)
    fakes = coordinator._fakes
    fakes["a"] = FakeAgent("a", [("ok", {"slow": "but-fine"})])
    plan = [{"agent": "a", "request": {}, "dependencies": []}]
    results = await coordinator._execute_plan_parallel(plan, "", fail_fast=True)
    assert results[0]["status"] == "success"


# ─────────────────────────────────────────────
# process() 模板钩子：run 记录创建 + run_id 回传
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_process_template_creates_run_record(coordinator, runs_dir):
    """process(workflow_template) 带 _user_id 时创建 run 记录并在结果回传 run_id"""
    fakes = coordinator._fakes
    for name in ("reader", "reviewer", "response", "writing", "polishing"):
        fakes[name] = FakeAgent(name, [("ok", {"agent": name, "out": True})])

    final = await coordinator.process(
        {
            "task": "根据审稿意见修订论文",
            "content": "# Abstract\n占位。",
            "workflow_template": "revise",
            "_user_id": "u_test",
            "_user_api_key": "sk-secret",
        }
    )
    assert final["status"] == "success"
    assert final["run_id"]

    record = get_run("u_test", final["run_id"])
    assert record["status"] == "succeeded"
    assert record["source"] == {"kind": "template", "template_id": "revise"}
    # 凭据不落盘：冻结请求不得携带 _ 前缀字段
    assert all(not k.startswith("_") for k in record["request"])
    assert "_user_api_key" not in record["request"]
    assert all(s["status"] == "success" for s in record["steps"])


# ─────────────────────────────────────────────
# v2 瞬态失败自动重试（opt-in：AGENT_STEP_MAX_RETRIES）
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_transient_failure_retried_then_succeeds(
    coordinator, runs_dir, monkeypatch
):
    """瞬态失败（LLM 限流）→ 自动重试后成功；attempts 累加 + 证据链保全"""
    monkeypatch.setattr(get_settings(), "AGENT_STEP_MAX_RETRIES", 1)
    monkeypatch.setattr(get_settings(), "AGENT_STEP_RETRY_DELAY", 0.01)
    fakes = coordinator._fakes
    fakes["a"] = FakeAgent(
        "a", [("raise", LLMRateLimitException()), ("ok", {"step": "a2"})]
    )
    plan = [{"agent": "a", "request": {}, "dependencies": []}]

    rec = _recorder_for(plan)
    results = await coordinator._execute_plan_parallel(
        plan, "", fail_fast=True, run_recorder=rec
    )
    assert results[0]["status"] == "success"
    assert fakes["a"].calls == 2

    record = get_run("u_test", rec.run_id)
    step = record["steps"][0]
    assert step["attempts"] == 2 and step["status"] == "success"
    assert len(step["attempt_errors"]) == 1
    assert step["attempt_errors"][0]["failure_class"] == "transient"


@pytest.mark.asyncio
async def test_permanent_failure_never_retried(coordinator, runs_dir, monkeypatch):
    """permanent/unknown 失败直抛不重试——盲目重试只会掩盖根因"""
    monkeypatch.setattr(get_settings(), "AGENT_STEP_MAX_RETRIES", 3)
    fakes = coordinator._fakes
    fakes["a"] = FakeAgent(
        "a", [("raise", AgentException("deterministic", "a")), ("ok", {})]
    )
    plan = [{"agent": "a", "request": {}, "dependencies": []}]

    rec = _recorder_for(plan)
    results = await coordinator._execute_plan_parallel(
        plan, "", fail_fast=True, run_recorder=rec
    )
    assert results[0]["status"] == "failed"
    assert fakes["a"].calls == 1


@pytest.mark.asyncio
async def test_no_retry_without_recorder(coordinator, runs_dir):
    """无 run_recorder（ad-hoc 路径）不重试，语义零变化"""
    fakes = coordinator._fakes
    fakes["a"] = FakeAgent("a", [("raise", LLMTimeoutException()), ("ok", {})])
    plan = [{"agent": "a", "request": {}, "dependencies": []}]

    with pytest.raises(LLMTimeoutException):
        await coordinator._execute_plan_parallel(plan, "", fail_fast=False)
    assert fakes["a"].calls == 1


@pytest.mark.asyncio
async def test_retry_budget_exhausted_checkpoints_final_failure(
    coordinator, runs_dir, monkeypatch
):
    """预算耗尽 → 最终失败正常 checkpoint（fail-fast 生效，下游不执行）"""
    monkeypatch.setattr(get_settings(), "AGENT_STEP_MAX_RETRIES", 1)
    monkeypatch.setattr(get_settings(), "AGENT_STEP_RETRY_DELAY", 0.01)
    fakes = coordinator._fakes
    fakes["a"] = FakeAgent("a", [("raise", LLMRateLimitException())])
    fakes["b"] = FakeAgent("b", [("ok", {})])
    plan = [
        {"agent": "a", "request": {}, "dependencies": []},
        {"agent": "b", "request": {}, "dependencies": ["a"]},
    ]

    rec = _recorder_for(plan)
    results = await coordinator._execute_plan_parallel(
        plan, "", fail_fast=True, run_recorder=rec
    )
    assert results[-1]["status"] == "failed"
    assert fakes["b"].calls == 0, "fail-fast：预算耗尽后下游不执行"

    record = get_run("u_test", rec.run_id)
    step = record["steps"][0]
    assert step["attempts"] == 2  # 中间失败 + 最终失败
    assert len(step["attempt_errors"]) == 2
    assert step["failure_class"] == "transient"


@pytest.mark.asyncio
async def test_zero_budget_disables_retry(coordinator, runs_dir):
    """AGENT_STEP_MAX_RETRIES=0（默认）→ 回退 v1 纯手动恢复语义"""
    fakes = coordinator._fakes
    fakes["a"] = FakeAgent("a", [("raise", LLMTimeoutException()), ("ok", {})])
    plan = [{"agent": "a", "request": {}, "dependencies": []}]

    rec = _recorder_for(plan)
    results = await coordinator._execute_plan_parallel(
        plan, "", fail_fast=True, run_recorder=rec
    )
    assert results[0]["status"] == "failed"
    assert fakes["a"].calls == 1

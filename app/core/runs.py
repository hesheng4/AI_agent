"""E6: 工作流运行记录（checkpoint）— fail-fast / partial_failure 之后的恢复基础

设计契约: docs/plans/workflow-error-recovery-v1.md（grill 会话逐项决策）

存储: data/runs/ 每 run 一个 JSON 文件（W5 原子写，同 data/workflows/ 模式）
状态机: running → succeeded | failed；resume 仅允许 failed → running
步骤条目: {agent, status: pending|success|failed, result, error,
          failure_class, attempts, started_at, finished_at}
签名: 对有序 (agent, task) 对取 sha256 — resume 时防计划漂移（漂移 → 409）
分类: hint-only transient | permanent | unknown，仅作 triage 提示，不挂行为
保留: cap-on-write，每用户超出 RUN_RETENTION_LIMIT 裁剪最旧

已知限制（与 data/workflows/ 一致）: 单进程假设；进程崩溃遗留的
running 记录 v1 不可 resume（只能等人工删除或过期裁剪）。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.utils.exceptions import (
    AppException,
    LLMRateLimitException,
    LLMTimeoutException,
    ValidationException,
)
from app.utils.logger import get_logger

logger = get_logger("core.runs")

_RUNS_DIR = Path("data/runs")

# 与 data/workflows 相同的安全约束: user_id 限安全字符，run_id 限 12 位 hex
_USER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_RUN_ID_RE = re.compile(r"^[0-9a-f]{12}$")

# 失败分类取值（hint-only，v1 不挂任何自动行为）
FAILURE_TRANSIENT = "transient"
FAILURE_PERMANENT = "permanent"
FAILURE_UNKNOWN = "unknown"

STEP_PENDING = "pending"
STEP_SUCCESS = "success"
STEP_FAILED = "failed"

RUN_RUNNING = "running"
RUN_SUCCEEDED = "succeeded"
RUN_FAILED = "failed"


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _validate_user_id(user_id: str) -> str:
    if not user_id or not _USER_ID_RE.match(user_id):
        raise ValueError(f"非法 user_id: {user_id!r}")
    return user_id


def _validate_run_id(run_id: str) -> str:
    if not run_id or not _RUN_ID_RE.match(run_id):
        raise ValueError(f"非法 run_id: {run_id!r}")
    return run_id


def _ensure_dir() -> None:
    _RUNS_DIR.mkdir(parents=True, exist_ok=True)


def _run_path(user_id: str, run_id: str) -> Path:
    return _RUNS_DIR / f"{_validate_user_id(user_id)}_{_validate_run_id(run_id)}.json"


# ---------------------------------------------------------------------------
# 计划签名与失败分类（纯函数）
# ---------------------------------------------------------------------------


def _plan_task_text(t: dict[str, Any]) -> str:
    """步骤任务文本：优先顶层 task，缺省读 request.task

    两种计划格式的 task 都在 request 内（planner 子任务与
    workflow_to_execution_plan 产物），顶层仅作兼容兜底。
    """
    task = t.get("task")
    if task:
        return str(task)
    return str((t.get("request") or {}).get("task", ""))


def plan_signature(execution_plan: list[dict[str, Any]]) -> str:
    """对执行计划取签名：sha256(有序 [agent, task] 对)

    只含 agent 名与步骤任务文本 — 不含 request 其他内部字段（用户凭据、
    自由文本），保证模板展开/自定义 DAG 编译在 resume 时可复算比对。
    模板步骤文本来自模板定义，自定义 DAG 的 task 来自节点定义，
    二者均不随请求自由文本变化，签名稳定。
    """
    pairs = [[t.get("agent", ""), _plan_task_text(t)] for t in execution_plan]
    payload = json.dumps(pairs, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def classify_failure(exc: BaseException | None) -> str:
    """失败分类（hint-only）：异常类型/编码 → transient | permanent | unknown

    - LLM 限流/超时、步级墙钟超时 → transient（重跑大概率成功）
    - 输入校验类 → permanent（重跑必然同样失败）
    - 其余（Agent/Tool 内部错误、未知异常）→ unknown，由人判断
    v1 不挂任何自动行为；未来自动重试接入同一信号。
    """
    if exc is None:
        return FAILURE_UNKNOWN
    if isinstance(exc, (LLMRateLimitException, LLMTimeoutException)):
        return FAILURE_TRANSIENT
    if isinstance(exc, TimeoutError):  # 含 StepTimeoutError（步级超时合成）
        return FAILURE_TRANSIENT
    if isinstance(exc, ValidationException):
        return FAILURE_PERMANENT
    if isinstance(exc, AppException):
        code = getattr(exc, "code", "")
        if code in {"LLM_RATE_LIMIT", "LLM_TIMEOUT"}:
            return FAILURE_TRANSIENT
        if code == "VALIDATION_ERROR":
            return FAILURE_PERMANENT
    return FAILURE_UNKNOWN


# ---------------------------------------------------------------------------
# 存储操作（同步文件 IO；单事件循环内调用，读写间无 await 即原子）
# ---------------------------------------------------------------------------


def _save_run(user_id: str, run_id: str, record: dict[str, Any]) -> None:
    """W5: 原子写 — tmp + os.replace；default=str 兜底非 JSON 序列化对象"""
    _ensure_dir()
    path = _run_path(user_id, run_id)
    tmp_path = _RUNS_DIR / f".{path.name}.tmp"
    record["updated_at"] = _utcnow()
    payload = json.dumps(record, ensure_ascii=False, indent=2, default=str)
    tmp_path.write_text(payload, encoding="utf-8")
    try:
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink()
        except Exception:
            pass
        raise


def _read_run(user_id: str, run_id: str) -> dict[str, Any] | None:
    path = _run_path(user_id, run_id)
    if not path.exists():
        return None
    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data
    except Exception as e:
        logger.warning(f"run 记录解析失败 (视为不存在): {path.name}, err={e}")
        return None


def _prune_runs(user_id: str) -> None:
    """cap-on-write: 每用户仅保留最近 RUN_RETENTION_LIMIT 条（按 created_at）"""
    limit = get_settings().RUN_RETENTION_LIMIT
    if limit <= 0:
        return
    uid = _validate_user_id(user_id)
    entries = []
    for f in _RUNS_DIR.iterdir():
        if not f.name.startswith(f"{uid}_") or not f.name.endswith(".json"):
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            entries.append((data.get("created_at", ""), f))
        except Exception:
            continue
    if len(entries) <= limit:
        return
    entries.sort(key=lambda x: x[0])
    for _, f in entries[: len(entries) - limit]:
        try:
            f.unlink()
            logger.info(f"run 记录裁剪（超上限 {limit}）: {f.name}")
        except Exception as e:
            logger.warning(f"run 记录裁剪失败: {f.name}, err={e}")


def _init_steps(execution_plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"agent": t["agent"], "status": STEP_PENDING, "attempts": 0}
        for t in execution_plan
    ]


def create_run(
    user_id: str,
    source: dict[str, str],
    request: dict[str, Any],
    execution_plan: list[dict[str, Any]],
) -> RunRecorder:
    """创建 run 记录（status=running，步骤全 pending），返回更新句柄

    source: {"kind": "template", "template_id": ...}
          | {"kind": "workflow", "workflow_id": ..., "name": ...}
    request: 冻结的原始请求 — 调用方须先剔除 _ 前缀内部字段（含用户凭据）
    """
    _ensure_dir()
    uid = _validate_user_id(user_id)
    run_id = uuid.uuid4().hex[:12]
    now = _utcnow()
    record = {
        "run_id": run_id,
        "user_id": uid,
        "status": RUN_RUNNING,
        "source": source,
        "request": request,
        "plan_signature": plan_signature(execution_plan),
        "plan": [
            {
                "agent": t.get("agent", ""),
                "task": _plan_task_text(t),
                "dependencies": list(t.get("dependencies", [])),
            }
            for t in execution_plan
        ],
        "steps": _init_steps(execution_plan),
        "task_ids": [],
        "error": "",
        "created_at": now,
        "updated_at": now,
    }
    _save_run(uid, run_id, record)
    _prune_runs(uid)
    logger.info(
        f"run 记录创建: run_id={run_id}, kind={source.get('kind')}, "
        f"steps={len(record['steps'])}"
    )
    return RunRecorder(uid, run_id)


def get_run(user_id: str, run_id: str) -> dict[str, Any] | None:
    """读取 run 记录（路径含 user_id，天然隔离他人记录）"""
    return _read_run(user_id, run_id)


# 历史：此处曾有 find_run_any_user(run_id) 跨用户查找入口（注释称
# 「仅限运维/CLI，API 不得使用」）。全仓无调用方，属越权读取隐患，
# 已移除（credibility-convergence 批次二 triage）。


def list_run_summaries(user_id: str) -> list[dict[str, Any]]:
    """列出用户的 run 记录摘要（不含步骤 result 载荷），新→旧"""
    _ensure_dir()
    uid = _validate_user_id(user_id)
    prefix = f"{uid}_"
    summaries: list[dict[str, Any]] = []
    for f in _RUNS_DIR.iterdir():
        if not f.name.startswith(prefix) or not f.name.endswith(".json"):
            continue
        try:
            data: dict[str, Any] = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"run 记录解析失败 (跳过): {f.name}, err={e}")
            continue
        summaries.append(
            {
                "run_id": data.get("run_id"),
                "status": data.get("status"),
                "source": data.get("source"),
                "error": data.get("error", ""),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
                "steps": [
                    {"agent": s.get("agent"), "status": s.get("status")}
                    for s in data.get("steps", [])
                ],
            }
        )
    return sorted(summaries, key=lambda x: x.get("created_at", ""), reverse=True)


def record_is_stale(record: dict[str, Any], stale_after: float) -> bool:
    """running 记录是否已过期（updated_at 距今超过 stale_after 秒无活动）

    updated_at 每次步进都会重写，因此过期 = 自最后活动起无进展，
    即进程大概率已中断。解析失败按未过期处理（保守，不误杀活跃 run）。
    """
    if stale_after <= 0:
        return False
    try:
        updated = datetime.fromisoformat(str(record.get("updated_at", "")))
        elapsed = (datetime.now(UTC) - updated).total_seconds()
    except (ValueError, TypeError):
        return False
    return elapsed > stale_after


def claim_run_for_resume(
    user_id: str,
    run_id: str,
    task_id: str = "",
    allow_stale_running: bool = False,
    stale_after: float | None = None,
) -> bool:
    """resume 并发守卫: failed → running 迁移（或接管过期的 running）成功返回 True

    E6 v2 起允许接管 running 记录（allow_stale_running=True 且超过
    stale_after 秒无活动）——进程中断遗留的孤儿 run 从此可恢复；
    活跃 run（近期有步进）仍拒绝，避免双跑。stale_after 缺省读
    RUN_STALE_AFTER 配置。

    同步读-改-写、中间无 await，在单事件循环内为原子；多进程部署
    （与 data/workflows 相同假设破坏时）不保证互斥。
    """
    if stale_after is None:
        stale_after = float(get_settings().RUN_STALE_AFTER)
    record = _read_run(user_id, run_id)
    if not record:
        return False
    status = record.get("status")
    if status == RUN_FAILED:
        pass
    elif (
        status == RUN_RUNNING
        and allow_stale_running
        and record_is_stale(record, stale_after)
    ):
        logger.warning(
            f"接管疑似中断的 running run（超 {stale_after}s 无活动）: "
            f"run_id={run_id}"
        )
    else:
        return False
    record["status"] = RUN_RUNNING
    if task_id:
        record.setdefault("task_ids", []).append(task_id)
    _save_run(user_id, run_id, record)
    logger.info(f"run 记录接管的 resume: run_id={run_id}, task_id={task_id}")
    return True


def finalize_run(user_id: str, run_id: str, status: str, error: str = "") -> None:
    """终态落盘: succeeded | failed（调用方据 failed_agents 判定）"""
    if status not in {RUN_SUCCEEDED, RUN_FAILED}:
        raise ValueError(f"非法 run 终态: {status!r}")
    record = _read_run(user_id, run_id)
    if not record:
        logger.warning(f"finalize 跳过: run 记录不存在 {user_id}/{run_id}")
        return
    record["status"] = status
    record["error"] = error
    _save_run(user_id, run_id, record)
    logger.info(f"run 记录终态: run_id={run_id}, status={status}")


def compute_resume_sets(
    record: dict[str, Any],
) -> tuple[list[str], list[dict[str, Any]]]:
    """由 run 记录推导 resume 的重执行集合与已完成结果

    规则（模板链与自定义 DAG 统一）:
      重执行 = failed ∪ pending(未执行) ∪ failed 的传递依赖下游
    已完成 = status=success 且不在重执行集合 — 其 result 载荷作为
    上游上下文预注入，resume 不重复任何成功的 LLM 工作。

    返回 (sorted 重执行 agent 列表, 已完成步骤条目列表)。
    """
    steps = record.get("steps", [])
    rerun: set[str] = {
        s["agent"] for s in steps if s.get("status") in {STEP_FAILED, STEP_PENDING}
    }
    # 传递依赖下游: 依赖图中任何依赖重执行集合的节点一并重跑
    # （其既有产出消费了缺失/失效的上游，不可信）
    dep_map = {
        t.get("agent", ""): list(t.get("dependencies", []))
        for t in record.get("plan", [])
    }
    changed = True
    while changed:
        changed = False
        for agent, deps in dep_map.items():
            if agent not in rerun and any(d in rerun for d in deps):
                rerun.add(agent)
                changed = True
    completed_entries: list[dict[str, Any]] = [
        {
            "agent": s["agent"],
            "result": s.get("result") or {},
        }
        for s in steps
        if s.get("status") == STEP_SUCCESS and s["agent"] not in rerun
    ]
    return sorted(rerun), completed_entries


class RunRecorder:
    """run 记录更新句柄 — coordinator 执行期间逐步落盘"""

    def __init__(self, user_id: str, run_id: str):
        self.user_id = _validate_user_id(user_id)
        self.run_id = _validate_run_id(run_id)

    def _mutate(self, mutate: Callable[[dict[str, Any]], None]) -> None:
        record = _read_run(self.user_id, self.run_id)
        if not record:
            logger.warning(f"run 记录更新跳过 (不存在): {self.run_id}")
            return
        mutate(record)
        _save_run(self.user_id, self.run_id, record)

    def step_finished(
        self,
        agent: str,
        *,
        status: str,
        result: dict[str, Any] | None = None,
        error: str = "",
        failure_class: str = FAILURE_UNKNOWN,
        started_at: str | None = None,
    ) -> None:
        """记录一步完成（重执行时 attempts 累加，最新状态覆盖旧值）"""

        def mutate(record: dict[str, Any]) -> None:
            entry = next(
                (s for s in record.get("steps", []) if s.get("agent") == agent), None
            )
            if entry is None:
                logger.warning(f"run 步骤条目缺失 (追加兜底): agent={agent}")
                entry = {"agent": agent, "status": STEP_PENDING, "attempts": 0}
                record.setdefault("steps", []).append(entry)
            entry["status"] = status
            entry["attempts"] = entry.get("attempts", 0) + 1
            entry["result"] = result
            entry["error"] = error
            entry["failure_class"] = failure_class if status == STEP_FAILED else ""
            entry["finished_at"] = _utcnow()
            if started_at:
                entry["started_at"] = started_at
            # v2 自动重试：保全每次失败尝试的证据（成功后仍可追溯）
            if status == STEP_FAILED:
                entry.setdefault("attempt_errors", []).append(
                    {"error": error, "failure_class": failure_class, "at": _utcnow()}
                )

        self._mutate(mutate)

    def add_task_id(self, task_id: str) -> None:
        if not task_id:
            return
        self._mutate(lambda r: r.setdefault("task_ids", []).append(task_id))

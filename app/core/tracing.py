"""O5: 链路追踪 — 基于 contextvars 的 trace_id/span_id 透传

用法:
    # 中间件入口
    with trace_context(request_id):
        await coordinator.process(...)  # 内部所有日志自动带 trace_id

    # Agent span
    with span("writing"):
        result = await writing_agent.process(...)
        # 自动记录 agent + duration_ms
"""

from __future__ import annotations

import contextvars
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

# contextvars：异步安全的上下文传播（每个 Task 独立副本）
_trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "trace_id", default=""
)
_span_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "span_id", default=""
)
_agent_var: contextvars.ContextVar[str] = contextvars.ContextVar("agent", default="")


def get_trace_id() -> str:
    return _trace_id_var.get()


def get_span_id() -> str:
    return _span_id_var.get()


def get_agent() -> str:
    return _agent_var.get()


@contextmanager
def trace_context(trace_id: str | None = None) -> Iterator[str]:
    """设置 trace_id 上下文（请求级，贯穿整个调用链）

    若不传 trace_id 则自动生成。返回 trace_id 供中间件写入响应头。
    """
    tid = trace_id or uuid.uuid4().hex[:16]
    token = _trace_id_var.set(tid)
    try:
        yield tid
    finally:
        _trace_id_var.reset(token)


@contextmanager
def span(agent_name: str) -> Iterator[None]:
    """记录 Agent 执行 span（含 agent 名 + 耗时）

    与 logger 配合，日志自动带 trace_id/span_id/agent。
    """
    span_id = uuid.uuid4().hex[:8]
    start = time.perf_counter()
    token_span = _span_id_var.set(span_id)
    token_agent = _agent_var.set(agent_name)
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        _span_id_var.reset(token_span)
        _agent_var.reset(token_agent)
        # span 结束日志（供链路分析）
        from app.utils.logger import get_logger

        get_logger("tracing").debug(
            f"span end agent={agent_name} span_id={span_id} "
            f"trace_id={get_trace_id()} duration={duration_ms:.0f}ms"
        )


def trace_dict() -> dict[str, Any]:
    """返回当前 trace 上下文（供事件总线 / WS 推送附加元数据）"""
    return {
        "trace_id": get_trace_id(),
        "span_id": get_span_id(),
        "agent": get_agent(),
    }

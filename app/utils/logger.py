import logging
import sys
from pathlib import Path

from app.config import get_settings
from app.core.tracing import get_agent, get_span_id, get_trace_id

settings = get_settings()

# 日志目录
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# O5: 结构化日志格式 — 含 trace_id/span_id/agent（空值时不显示）
LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d"
    " | trace=%(trace_id)s span=%(span_id)s agent=%(agent)s | %(message)s"
)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class _TraceContextFilter(logging.Filter):
    """注入当前 contextvars 中的 trace_id/span_id/agent 到每条日志"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_trace_id() or "-"
        record.span_id = get_span_id() or "-"
        record.agent = get_agent() or "-"
        return True


def get_logger(name: str) -> logging.Logger:
    """获取 logger 实例（O5: 自动注入 trace 上下文）"""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    logger.addFilter(_TraceContextFilter())

    fmt = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    # 控制台 handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    # 文件 handler
    file_handler = logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    # 错误文件 handler
    error_handler = logging.FileHandler(LOG_DIR / "error.log", encoding="utf-8")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(fmt)
    logger.addHandler(error_handler)

    return logger

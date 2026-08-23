import logging
import re
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

# PII 脱敏（体检报告 P2-16）：登录/注册等日志会带真实用户邮箱
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")


def _redact_pii(message: str) -> str:
    """邮箱保留首字符与域名：alice@example.com → a***@example.com"""
    if "@" not in message:
        return message
    return _EMAIL_RE.sub(lambda m: f"{m.group(0)[0]}***@{m.group(1)}", message)


class _TraceContextFilter(logging.Filter):
    """注入当前 contextvars 中的 trace_id/span_id/agent 到每条日志"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_trace_id() or "-"
        record.span_id = get_span_id() or "-"
        record.agent = get_agent() or "-"
        return True


class _PIIRedactFilter(logging.Filter):
    """日志落盘/输出前脱敏邮箱（在格式化前改写 msg，args 已合并）"""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.args:
            record.msg = record.getMessage()
            record.args = None
        if isinstance(record.msg, str):
            record.msg = _redact_pii(record.msg)
        return True


def get_logger(name: str) -> logging.Logger:
    """获取 logger 实例（O5: 自动注入 trace 上下文）"""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    logger.addFilter(_TraceContextFilter())
    logger.addFilter(_PIIRedactFilter())

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

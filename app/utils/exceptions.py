"""自定义异常"""


class AppException(Exception):  # noqa: N818 — 重命名为 AppError 是破坏性变更
    """应用基础异常"""

    def __init__(self, message: str, code: str = "APP_ERROR", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class LLMException(AppException):
    """LLM调用异常"""

    def __init__(self, message: str, code: str = "LLM_ERROR"):
        super().__init__(message, code, status_code=502)


class LLMRateLimitException(LLMException):
    """LLM速率限制"""

    def __init__(self, message: str = "LLM速率限制，请稍后重试"):
        super().__init__(message, code="LLM_RATE_LIMIT")


class LLMTimeoutException(LLMException):
    """LLM超时"""

    def __init__(self, message: str = "LLM请求超时"):
        super().__init__(message, code="LLM_TIMEOUT")


class AgentException(AppException):
    """Agent处理异常"""

    def __init__(self, message: str, agent_name: str = "unknown"):
        super().__init__(
            message=f"Agent[{agent_name}] {message}",
            code="AGENT_ERROR",
            status_code=500,
        )


class ValidationException(AppException):
    """输入验证异常"""

    def __init__(self, message: str):
        super().__init__(message, code="VALIDATION_ERROR", status_code=400)


class ToolException(AppException):
    """工具调用异常"""

    def __init__(self, message: str, tool_name: str = "unknown"):
        super().__init__(
            message=f"Tool[{tool_name}] {message}", code="TOOL_ERROR", status_code=500
        )


class StepTimeoutError(TimeoutError):
    """步骤级墙钟超时（工作流单步超过 AGENT_STEP_TIMEOUT）

    继承 TimeoutError 而非 AppException：失败分类器据此归为
    transient，checkpoint 落盘后可 resume 重试。
    """

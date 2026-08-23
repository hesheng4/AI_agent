from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from app.config import get_settings
from app.utils.exceptions import AgentException, ToolException, ValidationException
from app.utils.llm import LLMClient
from app.utils.logger import get_logger


class BaseAgent(ABC):
    def __init__(self, name: str, tools: list[str] | None = None):
        self.name = name
        self.tools = tools or []
        self.llm = LLMClient()
        self.logger = get_logger(f"agent.{name}")

    def _resolve_model(self, user_api_model: str | None = None) -> str | None:
        """P1-O3: 解析当前 Agent 应使用的模型

        优先级: 显式传入 > AGENT_CREDENTIAL_OVERRIDES[model]
        > AGENT_MODEL_OVERRIDES > 全局
        """
        if user_api_model:
            return user_api_model
        creds = get_settings().AGENT_CREDENTIAL_OVERRIDES.get(self.name, {})
        if creds.get("model"):
            return creds["model"]
        overrides = get_settings().AGENT_MODEL_OVERRIDES
        return overrides.get(self.name)

    def _resolve_credentials(
        self,
        user_api_key: str | None = None,
        user_api_base_url: str | None = None,
        user_api_model: str | None = None,
    ) -> tuple[str | None, str | None, str | None]:
        """E2: 解析当前 Agent 的完整凭证三元组 (api_key, base_url, model)

        优先级: 显式传入 > AGENT_CREDENTIAL_OVERRIDES > 全局配置
        用于多团队/多供应商隔离：不同 Agent 走不同 API Key + endpoint + model。
        """
        creds = get_settings().AGENT_CREDENTIAL_OVERRIDES.get(self.name, {})
        resolved_key = user_api_key or creds.get("api_key")
        resolved_url = user_api_base_url or creds.get("base_url")
        resolved_model = self._resolve_model(user_api_model)
        return resolved_key, resolved_url, resolved_model

    def _get_tool_handler(self, tool_name: str):
        """查找工具处理函数，支持自身方法或 tools_handler 委托"""
        # 检查自身 _tool_{name} 方法
        handler = getattr(self, f"_tool_{tool_name}", None)
        if handler is not None and callable(handler):
            return handler
        # 检查 tools_handler 上的 {name} 方法
        handler_obj = getattr(self, "tools_handler", None)
        if handler_obj is not None:
            handler = getattr(handler_obj, tool_name, None)
            if handler is not None and callable(handler):
                return handler
        return None

    @abstractmethod
    async def process(self, request: dict[str, Any]) -> dict[str, Any]:
        """处理请求"""
        pass

    async def call_llm(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        user_api_key: str | None = None,
        user_api_base_url: str | None = None,
        user_api_model: str | None = None,
    ) -> str:
        """调用LLM，带错误处理，支持用户级API配置覆盖

        P1-O3: 自动应用 Agent 级模型覆盖 + token 预算
        E2: 自动应用 Agent 级凭证隔离 (api_key + base_url + model)
        """
        r_key, r_url, r_model = self._resolve_credentials(
            user_api_key, user_api_base_url, user_api_model
        )
        capped_max_tokens = self._apply_token_budget(max_tokens)
        try:
            self.logger.debug(f"调用LLM，prompt长度: {len(prompt)}, agent={self.name}")
            result = await self.llm.generate(
                prompt,
                system_prompt,
                temperature,
                capped_max_tokens,
                user_api_key=r_key,
                user_api_base_url=r_url,
                user_api_model=r_model,
            )
            self.logger.debug(f"LLM返回 {len(result)} 字符")
            return result
        except Exception as e:
            self.logger.error(f"LLM调用失败: {e}", exc_info=True)
            raise AgentException(f"LLM调用失败: {str(e)}", self.name) from e

    def _apply_token_budget(self, max_tokens: int | None) -> int | None:
        """P1-O3: 应用 Agent 级 token 预算上限，取传入值与预算的较小值"""
        budgets = get_settings().AGENT_TOKEN_BUDGETS
        budget = budgets.get(self.name)
        if budget is None:
            return max_tokens
        if max_tokens is None:
            return budget
        return min(max_tokens, budget)

    async def call_llm_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        user_api_key: str | None = None,
        user_api_base_url: str | None = None,
        user_api_model: str | None = None,
    ) -> AsyncIterator[str]:
        """P1-O3: 流式 LLM 输出，逐 chunk 返回文本

        E2: 自动应用 Agent 级凭证隔离。
        适用于写作/润色等长文本场景，前端可逐字渲染。
        """
        r_key, r_url, r_model = self._resolve_credentials(
            user_api_key, user_api_base_url, user_api_model
        )
        capped_max_tokens = self._apply_token_budget(max_tokens)
        try:
            async for chunk in self.llm.generate_stream(
                prompt,
                system_prompt,
                temperature,
                capped_max_tokens,
                user_api_key=r_key,
                user_api_base_url=r_url,
                user_api_model=r_model,
            ):
                yield chunk
        except Exception as e:
            self.logger.error(f"LLM流式调用失败: {e}", exc_info=True)
            raise AgentException(f"LLM流式调用失败: {str(e)}", self.name) from e

    async def use_tool(self, tool_name: str, **kwargs) -> Any:
        """使用工具，带验证"""
        if tool_name not in self.tools:
            raise ToolException(f"工具不可用: {tool_name}", tool_name=tool_name)

        handler = self._get_tool_handler(tool_name)
        if handler is None:
            raise ToolException(f"工具未实现: {tool_name}", tool_name=tool_name)

        try:
            self.logger.debug(f"调用工具 {tool_name}，参数: {kwargs}")
            result = await handler(**kwargs)
            self.logger.debug(f"工具 {tool_name} 执行成功")
            return result
        except ToolException:
            raise
        except Exception as e:
            self.logger.error(f"工具 {tool_name} 执行失败: {e}", exc_info=True)
            raise ToolException(f"执行失败: {str(e)}", tool_name=tool_name) from e

    def validate_request(
        self, request: dict[str, Any], required_fields: list[str]
    ) -> None:
        """验证请求字段"""
        missing = [f for f in required_fields if f not in request]
        if missing:
            raise ValidationException(f"缺少必填字段: {', '.join(missing)}")

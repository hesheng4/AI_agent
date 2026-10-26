import asyncio
import hashlib
from collections import OrderedDict
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from openai import APIError, APITimeoutError, AsyncOpenAI, RateLimitError

from app.config import get_settings
from app.core.cache import cache
from app.utils.exceptions import (
    LLMException,
    LLMRateLimitException,
    LLMTimeoutException,
)
from app.utils.logger import get_logger

if TYPE_CHECKING:
    from app.core.ascend import VLLMAscendClient

logger = get_logger("llm")
settings = get_settings()

# 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # 秒
RETRY_BACKOFF = 2.0  # 指数退避倍数

# LLM 客户端复用缓存：避免每次请求新建 AsyncOpenAI 实例（httpx 连接池复用）
# 键为 (api_key_hash, base_url) 元组，避免明文密钥长期驻留内存。
# OrderedDict：LRU 逐出需要 move_to_end（普通 dict 无此方法）。
_user_client_cache: OrderedDict[tuple[str, str], AsyncOpenAI] = OrderedDict()
_USER_CLIENT_CACHE_MAX = 100
# 缓存读写锁，防止并发清空导致使用中的客户端被销毁
_client_cache_lock = asyncio.Lock()


def _aclose_client_quietly(client: AsyncOpenAI) -> None:
    """后台关闭被逐出的客户端连接池；无事件循环时交给 GC。"""

    async def _close() -> None:
        try:
            await client.close()
        except Exception:  # noqa: BLE001 — 逐出关闭失败不影响业务
            pass

    try:
        asyncio.get_running_loop().create_task(_close())
    except RuntimeError:
        pass


class LLMClient:
    """统一 LLM 客户端 - 支持远程 API 和本地昇腾 NPU 推理

    通过 LLM_MODE 配置切换:
    - "remote": 使用远程 OpenAI 兼容 API
    - "ascend": 使用本地 vLLM-Ascend 推理服务

    支持用户级 API 配置覆盖（api_key, api_base_url, api_model）。
    """

    def __init__(self) -> None:
        self._mode = settings.LLM_MODE
        self._remote_client: AsyncOpenAI | None = None
        self._ascend_client: VLLMAscendClient | None = None
        self.model = self._get_model_name()

    def _get_model_name(self) -> str:
        """获取当前模型名称"""
        if self._mode == "ascend":
            return settings.ASCEND_LLM_MODEL
        return settings.OPENAI_MODEL

    def _get_remote_client(
        self, user_api_key: str | None = None, user_base_url: str | None = None
    ) -> AsyncOpenAI:
        """懒初始化远程 OpenAI 客户端，支持用户级覆盖

        用户级配置时复用同 (api_key_hash, base_url) 的客户端实例，
        避免 httpx 连接池浪费。
        使用 SHA-256 哈希后的 api_key 作为缓存键，避免明文密钥长期驻留全局字典。
        """
        if user_api_key and user_base_url:
            # 哈希 api_key 作为缓存键，避免明文密钥驻留
            api_key_hash = hashlib.sha256(user_api_key.encode()).hexdigest()[:32]
            cache_key = (api_key_hash, user_base_url)
            client = _user_client_cache.get(cache_key)
            if client is None:
                # 容量满时 LRU 逐出最旧条目并显式关闭其连接池。
                # 旧实现整体 clear() 且不 close：被清出的 AsyncOpenAI
                # httpx 连接池既不释放又造成抖动；dict 操作在单事件循环内
                # 天然原子，无需加锁。
                while len(_user_client_cache) >= _USER_CLIENT_CACHE_MAX:
                    oldest_key, oldest = next(iter(_user_client_cache.items()))
                    _user_client_cache.pop(oldest_key)
                    _aclose_client_quietly(oldest)
                client = AsyncOpenAI(
                    api_key=user_api_key, base_url=user_base_url, timeout=60.0
                )
                _user_client_cache[cache_key] = client
            else:
                _user_client_cache.move_to_end(cache_key)  # LRU 命中刷新
            return client
        if self._remote_client is None:
            self._remote_client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
                timeout=60.0,
            )
        return self._remote_client

    def _get_ascend_client(self) -> VLLMAscendClient:
        """懒初始化 vLLM-Ascend 客户端"""
        if self._ascend_client is None:
            from app.core.ascend import get_vllm_client

            self._ascend_client = get_vllm_client()
        return self._ascend_client

    async def close(self) -> None:
        """关闭底层远程客户端连接池"""
        if self._remote_client is not None:
            await self._remote_client.close()
            self._remote_client = None

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        use_cache: bool = True,
        user_api_key: str | None = None,
        user_api_base_url: str | None = None,
        user_api_model: str | None = None,
    ) -> str:
        """调用LLM生成，带重试、缓存和错误处理

        支持用户级 API 配置覆盖：当传入 user_api_key / user_api_base_url /
        user_api_model 时，
        使用用户个人配置代替系统默认配置。

        返回生成的文本。如需 token 用量，请用 generate_with_usage。
        """
        text, _ = await self.generate_with_usage(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            use_cache=use_cache,
            user_api_key=user_api_key,
            user_api_base_url=user_api_base_url,
            user_api_model=user_api_model,
        )
        return text

    async def generate_with_usage(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        use_cache: bool = True,
        user_api_key: str | None = None,
        user_api_base_url: str | None = None,
        user_api_model: str | None = None,
    ) -> tuple[str, dict[str, int]]:
        """同 generate，但额外返回 token 用量 dict

        返回 (text, usage)，usage 形如：
            {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
        缺失字段以 0 填充。
        """
        effective_model = user_api_model or self.model

        # 检查缓存（仅缓存temperature=0的确定性调用，且仅系统配置时缓存）
        if use_cache and temperature == 0 and not user_api_key:
            cache_key = cache._make_key(
                "llm",
                {
                    "prompt": prompt,
                    "system": system_prompt,
                    "model": effective_model,
                    "mode": self._mode,
                },
            )
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                logger.info("LLM缓存命中")
                # 缓存命中时无 usage 信息
                return cached_result, {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        if self._mode == "ascend" and not user_api_key:
            result, usage = await self._call_ascend(messages, temperature, max_tokens)
        else:
            result, usage = await self._call_with_retry(
                messages,
                temperature,
                max_tokens,
                user_api_key=user_api_key,
                user_api_base_url=user_api_base_url,
                user_api_model=user_api_model,
            )

        # 写入缓存（仅文本，不缓存 usage）
        if use_cache and temperature == 0 and not user_api_key:
            await cache.set(cache_key, result, settings.LLM_CACHE_TTL)

        return result, usage

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        user_api_key: str | None = None,
        user_api_base_url: str | None = None,
        user_api_model: str | None = None,
    ) -> str:
        """多轮对话，带重试和错误处理"""
        if self._mode == "ascend" and not user_api_key:
            text, _ = await self._call_ascend(messages, temperature, max_tokens)
            return text
        text, _ = await self._call_with_retry(
            messages,
            temperature,
            max_tokens,
            user_api_key=user_api_key,
            user_api_base_url=user_api_base_url,
            user_api_model=user_api_model,
        )
        return text

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        user_api_key: str | None = None,
        user_api_base_url: str | None = None,
        user_api_model: str | None = None,
    ) -> AsyncIterator[str]:
        """P1-O3: 流式 LLM 输出，逐 chunk 返回文本片段

        仅远程 API 模式支持流式；ascend 模式降级为整段返回（vLLM-Ascend 流式支持待补）。
        缓存对流式无意义，故不启用。
        """

        effective_model = user_api_model or self.model
        messages: list[Any] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # ascend 模式降级为整段返回（一次性 yield）
        if self._mode == "ascend" and not user_api_key:
            text, _ = await self._call_ascend(messages, temperature, max_tokens)
            yield text
            return

        client = self._get_remote_client(
            user_api_key=user_api_key, user_base_url=user_api_base_url
        )
        try:
            stream = await client.chat.completions.create(
                model=effective_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    yield delta
        except Exception as e:
            logger.error(f"LLM流式调用失败: {e}", exc_info=True)
            raise LLMException(f"LLM流式调用失败: {str(e)}") from e

    # ========== 昇腾 NPU 推理路径 ==========

    async def _call_ascend(
        self, messages: list[dict[str, str]], temperature: float, max_tokens: int | None
    ) -> tuple[str, dict[str, int]]:
        """通过 vLLM-Ascend 本地推理"""
        last_exception = None

        for attempt in range(MAX_RETRIES):
            try:
                logger.debug(f"vLLM-Ascend 调用尝试 {attempt + 1}/{MAX_RETRIES}")

                client = self._get_ascend_client()
                result, usage = await client.chat_completions_with_usage(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                logger.debug(f"vLLM-Ascend 返回 {len(result)} 字符")
                return result, usage

            except Exception as e:
                last_exception = e
                logger.warning(
                    f"vLLM-Ascend 调用失败 (尝试 {attempt + 1}/{MAX_RETRIES}): {e}"
                )
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAY * (RETRY_BACKOFF**attempt)
                    await asyncio.sleep(delay)

        raise LLMException(
            f"vLLM-Ascend 调用失败，已重试{MAX_RETRIES}次: {str(last_exception)}"
        )

    # ========== 远程 API 推理路径 ==========

    async def _call_with_retry(
        self,
        messages: list[Any],
        temperature: float,
        max_tokens: int | None,
        user_api_key: str | None = None,
        user_api_base_url: str | None = None,
        user_api_model: str | None = None,
    ) -> tuple[str, dict[str, int]]:
        """带重试的远程API调用，支持用户级配置覆盖

        返回 (text, usage)
        """
        last_exception: APIError | None = None
        effective_model = user_api_model or self.model

        for attempt in range(MAX_RETRIES):
            try:
                logger.debug(f"LLM调用尝试 {attempt + 1}/{MAX_RETRIES}")

                client = self._get_remote_client(
                    user_api_key=user_api_key, user_base_url=user_api_base_url
                )
                response = await client.chat.completions.create(
                    model=effective_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                result = response.choices[0].message.content
                # 防御性检查：工具调用响应可能返回空 choices 或 None content
                if result is None:
                    result = ""
                # 提取 token 用量，缺失字段补 0
                usage_obj = getattr(response, "usage", None)
                usage = {
                    "prompt_tokens": getattr(usage_obj, "prompt_tokens", 0) or 0,
                    "completion_tokens": getattr(usage_obj, "completion_tokens", 0)
                    or 0,
                    "total_tokens": getattr(usage_obj, "total_tokens", 0) or 0,
                }
                logger.debug(
                    f"LLM调用成功，返回 {len(result)} 字符，"
                    f"tokens={usage['total_tokens']}"
                )
                return result, usage

            except APITimeoutError as e:
                last_exception = e
                logger.warning(f"LLM超时，尝试 {attempt + 1}/{MAX_RETRIES}: {e}")
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAY * (RETRY_BACKOFF**attempt)
                    await asyncio.sleep(delay)

            except RateLimitError as e:
                last_exception = e
                logger.warning(f"LLM速率限制，尝试 {attempt + 1}/{MAX_RETRIES}: {e}")
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAY * (RETRY_BACKOFF**attempt) * 2  # 速率限制等更久
                    await asyncio.sleep(delay)

            except APIError as e:
                last_exception = e
                # 4xx 错误（除 429 限流）不可重试，立即失败
                status_code = getattr(e, "status_code", None) or 0
                if 400 <= status_code < 500 and status_code != 429:
                    logger.error(f"LLM 不可恢复错误 ({status_code}): {e}")
                    raise LLMException(f"LLM请求错误 ({status_code}): {str(e)}")
                logger.warning(
                    f"LLM API错误 ({status_code})，"
                    f"尝试 {attempt + 1}/{MAX_RETRIES}: {e}"
                )
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAY * (RETRY_BACKOFF**attempt)
                    await asyncio.sleep(delay)

            except Exception as e:
                logger.error(f"LLM未知错误: {e}", exc_info=True)
                raise LLMException(f"LLM调用失败: {str(e)}") from e

        # 所有重试失败
        if isinstance(last_exception, APITimeoutError):
            raise LLMTimeoutException()
        elif isinstance(last_exception, RateLimitError):
            raise LLMRateLimitException()
        else:
            raise LLMException(
                f"LLM调用失败，已重试{MAX_RETRIES}次: {str(last_exception)}"
            )


async def close_user_llm_clients() -> None:
    """关闭用户级 LLM 客户端缓存中的连接池"""
    async with _client_cache_lock:
        for client in _user_client_cache.values():
            await client.close()
        _user_client_cache.clear()

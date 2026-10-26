import asyncio
from typing import TYPE_CHECKING, cast

from openai import APIError, APITimeoutError, AsyncOpenAI, RateLimitError

from app.config import get_settings
from app.core.cache import cache
from app.utils.exceptions import AppException
from app.utils.logger import get_logger

if TYPE_CHECKING:
    from app.core.ascend import NPULocalEmbedding, VLLMAscendClient

logger = get_logger("embedding")
settings = get_settings()

# 缓存TTL
EMBEDDING_CACHE_TTL = 3600  # 1小时

# 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 1.0
RETRY_BACKOFF = 2.0


class EmbeddingException(AppException):
    """Embedding异常"""

    def __init__(self, message: str):
        super().__init__(message, code="EMBEDDING_ERROR", status_code=502)


class EmbeddingClient:
    """统一文本向量化客户端 - 支持远程 API 和昇腾 NPU 推理

    通过 EMBEDDING_MODE 配置切换:
    - "remote": 使用远程 OpenAI 兼容 Embedding API
    - "ascend_api": 使用 vLLM-Ascend 的 Embedding 端点
    - "ascend_local": 使用 torch_npu 本地推理（sentence-transformers）
    """

    def __init__(self) -> None:
        self._mode = settings.EMBEDDING_MODE
        self._remote_client: AsyncOpenAI | None = None
        self._ascend_client: VLLMAscendClient | None = None
        self._npu_local: NPULocalEmbedding | None = None
        self.model = self._get_model_name()

    def _get_model_name(self) -> str:
        """获取当前模型名称"""
        if self._mode in ("ascend_api", "ascend_local"):
            return settings.ASCEND_EMBEDDING_MODEL
        return settings.EMBEDDING_MODEL

    def _get_remote_client(self) -> AsyncOpenAI:
        """懒初始化远程客户端（带 timeout）"""
        if self._remote_client is None:
            api_key = settings.EMBEDDING_API_KEY or settings.OPENAI_API_KEY
            base_url = settings.EMBEDDING_BASE_URL or settings.OPENAI_BASE_URL
            self._remote_client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=60.0,
            )
        return self._remote_client

    def _get_ascend_client(self) -> VLLMAscendClient:
        """懒初始化 vLLM-Ascend 客户端"""
        if self._ascend_client is None:
            from app.core.ascend import get_vllm_client

            self._ascend_client = get_vllm_client()
        return self._ascend_client

    def _get_npu_local(self) -> NPULocalEmbedding | None:
        """懒初始化 NPU 本地 Embedding"""
        if self._npu_local is None:
            from app.core.ascend import get_npu_embedding

            self._npu_local = get_npu_embedding()
        return self._npu_local

    async def close(self) -> None:
        """关闭远程 Embedding 客户端连接池"""
        if self._remote_client is not None:
            await self._remote_client.close()
            self._remote_client = None

    async def embed(self, text: str) -> list[float]:
        """单文本向量化"""
        # 检查缓存（await）
        cache_key = cache._make_key(
            "embedding", {"text": text, "model": self.model, "mode": self._mode}
        )
        cached_result = await cache.get(cache_key)
        if cached_result is not None:
            logger.debug("Embedding缓存命中")
            # 缓存里存的就是 float 列表（set 侧已保证）
            return cast("list[float]", cached_result)

        if self._mode == "ascend_local":
            result = await self._embed_npu_local([text])
            embedding = result[0]
        elif self._mode == "ascend_api":
            result = await self._embed_ascend_api([text])
            embedding = result[0]
        else:
            result = await self._embed_remote([text])
            embedding = result[0]

        # 写入缓存（await）
        await cache.set(cache_key, embedding, EMBEDDING_CACHE_TTL)
        return embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量向量化"""
        if not texts:
            return []

        if self._mode == "ascend_local":
            return await self._embed_npu_local_batch(texts)
        elif self._mode == "ascend_api":
            return await self._embed_ascend_api_batch(texts)
        else:
            return await self._embed_remote_batch(texts)

    # ========== 远程 API 路径 ==========

    async def _embed_remote(self, texts: list[str]) -> list[list[float]]:
        """远程 Embedding API（带重试）"""
        last_exception: APIError | None = None
        for attempt in range(MAX_RETRIES):
            try:
                client = self._get_remote_client()
                response = await client.embeddings.create(model=self.model, input=texts)
                return [item.embedding for item in response.data]
            except (APITimeoutError, RateLimitError) as e:
                last_exception = e
                logger.warning(
                    f"远程Embedding超时/限流 (尝试 {attempt + 1}/{MAX_RETRIES}): {e}"
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (RETRY_BACKOFF**attempt))
            except APIError as e:
                # 4xx 错误（除 429）不可重试
                if (
                    hasattr(e, "status_code")
                    and 400 <= (e.status_code or 0) < 500
                    and e.status_code != 429
                ):
                    raise EmbeddingException(f"Embedding请求错误: {str(e)}")
                last_exception = e
                logger.warning(
                    f"远程Embedding API错误 (尝试 {attempt + 1}/{MAX_RETRIES}): {e}"
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (RETRY_BACKOFF**attempt))
            except Exception as e:
                logger.error(f"远程Embedding失败: {e}")
                raise EmbeddingException(f"Embedding失败: {str(e)}")

        raise EmbeddingException(
            f"Embedding失败，已重试{MAX_RETRIES}次: {str(last_exception)}"
        )

    async def _embed_remote_batch(self, texts: list[str]) -> list[list[float]]:
        """远程批量 Embedding"""
        # 检查缓存（await）
        results = []
        uncached_texts = []
        uncached_indices = []

        for i, text in enumerate(texts):
            cache_key = cache._make_key(
                "embedding", {"text": text, "model": self.model, "mode": self._mode}
            )
            cached = await cache.get(cache_key)
            if cached is not None:
                results.append((i, cached))
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)

        # 批量处理未缓存的
        if uncached_texts:
            try:
                batch_size = 100
                for batch_start in range(0, len(uncached_texts), batch_size):
                    batch = uncached_texts[batch_start : batch_start + batch_size]
                    embeddings = await self._embed_remote(batch)

                    for j, embedding in enumerate(embeddings):
                        idx = uncached_indices[batch_start + j]
                        cache_key = cache._make_key(
                            "embedding",
                            {
                                "text": uncached_texts[batch_start + j],
                                "model": self.model,
                                "mode": self._mode,
                            },
                        )
                        await cache.set(cache_key, embedding, EMBEDDING_CACHE_TTL)
                        results.append((idx, embedding))

            except Exception as e:
                logger.error(f"批量Embedding失败: {e}")
                raise EmbeddingException(f"批量Embedding失败: {str(e)}")

        results.sort(key=lambda x: x[0])
        return [r[1] for r in results]

    # ========== vLLM-Ascend Embedding API 路径 ==========

    async def _embed_ascend_api(self, texts: list[str]) -> list[list[float]]:
        """通过 vLLM-Ascend Embedding 端点"""
        try:
            client = self._get_ascend_client()
            return await client.embeddings(texts, model=self.model)
        except Exception as e:
            logger.error(f"vLLM-Ascend Embedding失败: {e}")
            raise EmbeddingException(f"昇腾Embedding失败: {str(e)}")

    async def _embed_ascend_api_batch(self, texts: list[str]) -> list[list[float]]:
        """通过 vLLM-Ascend 批量 Embedding"""
        # 检查缓存（await）
        results = []
        uncached_texts = []
        uncached_indices = []

        for i, text in enumerate(texts):
            cache_key = cache._make_key(
                "embedding", {"text": text, "model": self.model, "mode": self._mode}
            )
            cached = await cache.get(cache_key)
            if cached is not None:
                results.append((i, cached))
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)

        if uncached_texts:
            try:
                batch_size = 64
                for batch_start in range(0, len(uncached_texts), batch_size):
                    batch = uncached_texts[batch_start : batch_start + batch_size]
                    embeddings = await self._embed_ascend_api(batch)

                    for j, embedding in enumerate(embeddings):
                        idx = uncached_indices[batch_start + j]
                        cache_key = cache._make_key(
                            "embedding",
                            {
                                "text": uncached_texts[batch_start + j],
                                "model": self.model,
                                "mode": self._mode,
                            },
                        )
                        await cache.set(cache_key, embedding, EMBEDDING_CACHE_TTL)
                        results.append((idx, embedding))
            except Exception as e:
                logger.error(f"vLLM-Ascend 批量Embedding失败: {e}")
                raise EmbeddingException(f"昇腾批量Embedding失败: {str(e)}")

        results.sort(key=lambda x: x[0])
        return [r[1] for r in results]

    # ========== torch_npu 本地推理路径 ==========

    async def _embed_npu_local(self, texts: list[str]) -> list[list[float]]:
        """通过 torch_npu 本地 Embedding 推理"""
        try:
            npu_local = self._get_npu_local()
            if npu_local is None:
                raise EmbeddingException("NPU 本地 Embedding 未启用")
            return await npu_local.encode_async(texts)
        except Exception as e:
            logger.error(f"NPU本地Embedding失败: {e}")
            raise EmbeddingException(f"NPU本地Embedding失败: {str(e)}")

    async def _embed_npu_local_batch(self, texts: list[str]) -> list[list[float]]:
        """通过 torch_npu 本地批量 Embedding"""
        # 检查缓存（await）
        results = []
        uncached_texts = []
        uncached_indices = []

        for i, text in enumerate(texts):
            cache_key = cache._make_key(
                "embedding", {"text": text, "model": self.model, "mode": self._mode}
            )
            cached = await cache.get(cache_key)
            if cached is not None:
                results.append((i, cached))
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)

        if uncached_texts:
            try:
                npu_local = self._get_npu_local()
                if npu_local is None:
                    raise EmbeddingException("NPU 本地 Embedding 未启用")
                embeddings = await npu_local.encode_async(uncached_texts)

                for j, embedding in enumerate(embeddings):
                    idx = uncached_indices[j]
                    cache_key = cache._make_key(
                        "embedding",
                        {
                            "text": uncached_texts[j],
                            "model": self.model,
                            "mode": self._mode,
                        },
                    )
                    await cache.set(cache_key, embedding, EMBEDDING_CACHE_TTL)
                    results.append((idx, embedding))
            except Exception as e:
                logger.error(f"NPU本地批量Embedding失败: {e}")
                raise EmbeddingException(f"NPU本地批量Embedding失败: {str(e)}")

        results.sort(key=lambda x: x[0])
        return [r[1] for r in results]


# 全局实例
embedding_client = EmbeddingClient()


def get_embedding_client() -> EmbeddingClient:
    """获取Embedding客户端"""
    return embedding_client


async def close_embedding_client() -> None:
    """关闭全局 Embedding 客户端连接池"""
    await embedding_client.close()

"""昇腾 NPU 适配核心模块

提供基于 vLLM-Ascend 的本地 LLM 推理服务和 NPU Embedding 服务，
替代远程 OpenAI API 调用，实现全本地化的行业 Agent 推理能力。

架构说明：
- LLM 推理：通过本地 vLLM-Ascend 服务（兼容 OpenAI API 协议）
- Embedding：通过本地 vLLM-Ascend 的 embedding 端点或 torch_npu 本地推理
- 硬件要求：Ascend 910B/910C 系列 NPU
"""

import asyncio
import os
from typing import Any

import httpx

from app.utils.exceptions import AppException
from app.utils.logger import get_logger

logger = get_logger("ascend")


class AscendException(AppException):
    """昇腾 NPU 异常"""

    def __init__(self, message: str):
        super().__init__(message, code="ASCEND_ERROR", status_code=503)


class AscendNPUManager:
    """昇腾 NPU 管理器 - 环境检测与资源管理"""

    _initialized = False
    _npu_available = False
    _device_count = 0

    @classmethod
    def check_environment(cls) -> dict[str, Any]:
        """检测昇腾 NPU 环境"""
        result: dict[str, Any] = {
            "torch_npu_installed": False,
            "npu_available": False,
            "device_count": 0,
            "cann_version": None,
            "torch_version": None,
        }

        # 检测 torch_npu
        try:
            import torch

            result["torch_version"] = torch.__version__

            import torch_npu  # noqa: F401

            result["torch_npu_installed"] = True

            # 检测 NPU 设备
            result["npu_available"] = torch.npu.is_available()
            result["device_count"] = torch.npu.device_count()

            if result["npu_available"]:
                # 获取 CANN 版本
                try:
                    result["cann_version"] = torch.npu.version.cann
                except Exception:
                    result["cann_version"] = "unknown"

                logger.info(
                    f"昇腾 NPU 就绪: {result['device_count']} 卡, "
                    f"CANN {result['cann_version']}, "
                    f"PyTorch {result['torch_version']}"
                )
            else:
                logger.warning("torch_npu 已安装但无可用 NPU 设备")

        except ImportError as e:
            result["missing_module"] = str(e)
            logger.warning(f"昇腾环境不完整: {e}")

        cls._npu_available = result["npu_available"]
        cls._device_count = result["device_count"]
        cls._initialized = True

        return result

    @classmethod
    def is_npu_available(cls) -> bool:
        """NPU 是否可用"""
        if not cls._initialized:
            cls.check_environment()
        return cls._npu_available

    @classmethod
    def get_device_count(cls) -> int:
        """获取 NPU 设备数量"""
        if not cls._initialized:
            cls.check_environment()
        return cls._device_count

    @classmethod
    def set_visible_devices(cls, device_ids: list[int]) -> None:
        """设置可见 NPU 设备（校验 ID 有效性）"""
        if not device_ids:
            raise ValueError("device_ids 不能为空")
        # 范围校验
        for d in device_ids:
            if not isinstance(d, int) or d < 0:
                raise ValueError(f"非法设备 ID: {d}，必须为非负整数")
        # 检测设备数后校验
        device_count = cls.get_device_count()
        if device_count > 0:
            invalid = [d for d in device_ids if d >= device_count]
            if invalid:
                raise ValueError(f"设备 ID 超出范围（共 {device_count} 卡）: {invalid}")
        os.environ["ASCEND_RT_VISIBLE_DEVICES"] = ",".join(str(d) for d in device_ids)
        logger.info(f"设置可见 NPU: {device_ids}")

    @classmethod
    def get_recommended_tp_size(cls) -> int:
        """根据模型规模推荐张量并行度"""
        count = cls.get_device_count()
        if count >= 8:
            return 8  # 大模型 70B+
        elif count >= 4:
            return 4  # 中模型 30B+
        elif count >= 2:
            return 2  # 小模型 7B-14B
        return 1


class VLLMAscendClient:
    """vLLM-Ascend 推理客户端

    通过 OpenAI 兼容协议与本地 vLLM-Ascend 服务通信。
    vLLM-Ascend 部署方式：
        vllm serve <model_path> \\
            --tensor-parallel-size <TP> \\
            --dtype bfloat16 \\
            --max-model-len 8192 \\
            --port 8001
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8001/v1",
        api_key: str = "EMPTY",
        model: str = "default",
        timeout: float = 120.0,
    ):
        self.base_url = base_url
        self.model = model
        self._api_key = api_key
        self._timeout = timeout
        self._client: Any = None
        self._client_lock = asyncio.Lock()

    async def _ensure_client(self) -> Any:
        """懒初始化 httpx 客户端（带并发保护）"""
        if self._client is None:
            async with self._client_lock:
                if self._client is None:
                    self._client = httpx.AsyncClient(
                        base_url=self.base_url,
                        timeout=httpx.Timeout(self._timeout, connect=30.0),
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {self._api_key}",
                        },
                    )
        return self._client

    async def chat_completions(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        """调用 vLLM-Ascend 的 Chat Completions API

        仅返回文本内容；如需 token 用量，请用 chat_completions_with_usage。
        """
        text, _ = await self.chat_completions_with_usage(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        return text

    async def chat_completions_with_usage(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> tuple[str, dict[str, int]]:
        """调用 vLLM-Ascend 的 Chat Completions API，返回 (text, usage)

        usage 形如 {"prompt_tokens": x, "completion_tokens": y, "total_tokens": z}，
        后端未返回时全部为 0。
        """
        client = await self._ensure_client()

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        # 昇腾推理优化：启用前缀缓存和调度优化
        if kwargs.get("enable_prefix_caching", True):
            payload["extra_body"] = {"enable_prefix_caching": True}

        try:
            response = await client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            text = data["choices"][0]["message"]["content"]
            usage_obj = data.get("usage") or {}
            usage = {
                "prompt_tokens": int(usage_obj.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(usage_obj.get("completion_tokens", 0) or 0),
                "total_tokens": int(usage_obj.get("total_tokens", 0) or 0),
            }
            return text, usage
        except httpx.HTTPStatusError as e:
            logger.error(
                f"vLLM-Ascend API 错误: {e.response.status_code} - {e.response.text}"
            )
            raise AscendException(
                f"vLLM-Ascend 推理失败: HTTP {e.response.status_code}"
            )
        except httpx.ConnectError:
            raise AscendException(
                "无法连接 vLLM-Ascend 服务，请确认服务已启动 "
                "(vllm serve <model> --port 8001)"
            )
        except Exception as e:
            logger.error(f"vLLM-Ascend 调用异常: {e}")
            raise AscendException(f"vLLM-Ascend 调用失败: {str(e)}")

    async def embeddings(
        self,
        input_texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """调用 vLLM-Ascend 的 Embeddings API"""
        client = await self._ensure_client()

        payload = {
            "model": model or self.model,
            "input": input_texts,
        }

        try:
            response = await client.post("/embeddings", json=payload)
            response.raise_for_status()
            data = response.json()
            return [item["embedding"] for item in data["data"]]
        except httpx.HTTPStatusError as e:
            logger.error(f"vLLM-Ascend Embedding 错误: {e.response.status_code}")
            raise AscendException(f"Embedding 失败: HTTP {e.response.status_code}")
        except httpx.ConnectError:
            raise AscendException("无法连接 vLLM-Ascend Embedding 服务")
        except Exception as e:
            logger.error(f"vLLM-Ascend Embedding 异常: {e}")
            raise AscendException(f"Embedding 失败: {str(e)}")

    async def check_health(self) -> bool:
        """检查 vLLM-Ascend 服务是否就绪"""
        client = await self._ensure_client()
        try:
            response: httpx.Response = await client.get("/models")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        """关闭客户端"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None


class NPULocalEmbedding:
    """基于 torch_npu 的本地 Embedding 推理

    当 vLLM-Ascend 不提供 embedding 端点时，
    可通过 torch_npu 直接加载 sentence-transformers 模型进行本地推理。
    """

    def __init__(
        self, model_name: str = "BAAI/bge-small-zh-v1.5", device: str = "npu:0"
    ):
        self.model_name = model_name
        self.device = device
        self._model: Any = None
        self._tokenizer = None

    async def _load_model_async(self) -> None:
        """异步加载模型到 NPU（在线程池中执行，避免阻塞事件循环）"""
        if self._model is not None:
            return
        await asyncio.to_thread(self._load_model_sync)

    def _load_model_sync(self) -> None:
        """同步加载模型（阻塞调用，应通过 _load_model_async 调用）"""
        if self._model is not None:
            return

        try:
            import torch  # noqa: F401
            import torch_npu  # noqa: F401
            from sentence_transformers import SentenceTransformer

            logger.info(f"加载 Embedding 模型到 {self.device}: {self.model_name}")
            self._model = SentenceTransformer(self.model_name, device=self.device)
            logger.info("Embedding 模型加载成功")

        except ImportError as e:
            raise AscendException(
                f"缺少依赖: {e}，请安装: pip install sentence-transformers torch_npu"
            )
        except Exception as e:
            logger.error(f"Embedding 模型加载失败: {e}")
            raise AscendException(f"Embedding 模型加载失败: {str(e)}")

    def encode(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """文本向量化（同步接口，会阻塞事件循环，建议用 encode_async）"""
        if self._model is None:
            self._load_model_sync()

        try:
            import torch

            all_embeddings = []
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                with torch.no_grad():
                    embeddings = self._model.encode(
                        batch,
                        normalize_embeddings=True,
                        show_progress_bar=False,
                    )
                all_embeddings.extend(embeddings.tolist())

            return all_embeddings

        except Exception as e:
            logger.error(f"Embedding 推理失败: {e}")
            raise AscendException(f"Embedding 推理失败: {str(e)}")

    async def encode_async(self, texts: list[str]) -> list[list[float]]:
        """文本向量化（异步接口，在线程池中执行）"""
        # 异步加载模型（首次调用时）
        await self._load_model_async()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.encode, texts)

    async def close(self) -> None:
        """释放模型资源（含 NPU 显存回收）"""
        if self._model is not None:
            try:
                # 显式释放 PyTorch 模型张量
                del self._model
                self._model = None
                # 触发 NPU 显存回收
                try:
                    import torch
                    import torch_npu  # noqa: F401

                    if hasattr(torch, "npu") and hasattr(torch.npu, "empty_cache"):
                        torch.npu.empty_cache()
                        logger.info("NPU 显存已回收")
                except ImportError:
                    pass
                logger.info("Embedding 模型资源已释放")
            except Exception as e:
                logger.warning(f"释放 Embedding 模型失败: {e}")


# 全局实例
_npu_manager = AscendNPUManager()
_vllm_client: VLLMAscendClient | None = None
_npu_embedding: NPULocalEmbedding | None = None


def get_vllm_client() -> VLLMAscendClient:
    """获取 vLLM-Ascend 客户端"""
    global _vllm_client
    if _vllm_client is None:
        from app.config import get_settings

        settings = get_settings()
        _vllm_client = VLLMAscendClient(
            base_url=settings.ASCEND_VLLM_BASE_URL,
            model=settings.ASCEND_LLM_MODEL,
            timeout=settings.ASCEND_VLLM_TIMEOUT,
        )
    return _vllm_client


def get_npu_embedding() -> NPULocalEmbedding | None:
    """获取 NPU 本地 Embedding 实例（仅在配置启用时创建）"""
    global _npu_embedding
    if _npu_embedding is None:
        from app.config import get_settings

        settings = get_settings()
        if settings.ASCEND_EMBEDDING_LOCAL:
            _npu_embedding = NPULocalEmbedding(
                model_name=settings.ASCEND_EMBEDDING_MODEL,
                device=f"npu:{settings.ASCEND_EMBEDDING_DEVICE}",
            )
    return _npu_embedding

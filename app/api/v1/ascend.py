"""昇腾 NPU 状态 API - 提供设备信息、服务健康状态"""

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.config import get_settings
from app.utils.logger import get_logger

router = APIRouter(dependencies=[Depends(get_current_user)])
logger = get_logger("ascend_api")
settings = get_settings()


class SwitchModeRequest(BaseModel):
    llm_mode: Literal["remote", "ascend"] = Field(
        ..., description="LLM 推理模式：remote=远程API, ascend=昇腾NPU"
    )


@router.get("/info")
async def ascend_info() -> dict[str, Any]:
    """获取昇腾 NPU 环境信息"""
    info: dict[str, Any] = {
        "llm_mode": settings.LLM_MODE,
        "embedding_mode": settings.EMBEDDING_MODE,
    }

    # NPU 硬件信息
    try:
        from app.core.ascend import AscendNPUManager

        env = AscendNPUManager.check_environment()
        info["npu"] = {
            "available": env["npu_available"],
            "device_count": env["device_count"],
            "cann_version": env.get("cann_version"),
            "torch_version": env.get("torch_version"),
            "torch_npu_installed": env["torch_npu_installed"],
        }
    except Exception as e:
        info["npu"] = {"error": str(e)}

    # vLLM-Ascend 服务状态
    if settings.LLM_MODE == "ascend":
        try:
            from app.core.ascend import get_vllm_client

            client = get_vllm_client()
            healthy = await client.check_health()
            info["vllm_ascend"] = {
                "healthy": healthy,
                "base_url": settings.ASCEND_VLLM_BASE_URL,
                "model": settings.ASCEND_LLM_MODEL,
                "tp_size": settings.ASCEND_TP_SIZE,
                "max_model_len": settings.ASCEND_MAX_MODEL_LEN,
            }
        except Exception as e:
            info["vllm_ascend"] = {"error": str(e)}

    # Embedding 服务状态
    if settings.EMBEDDING_MODE in ("ascend_api", "ascend_local"):
        info["embedding"] = {
            "mode": settings.EMBEDDING_MODE,
            "model": settings.ASCEND_EMBEDDING_MODEL,
            "local_enabled": settings.ASCEND_EMBEDDING_LOCAL,
        }

    # 性能优化配置
    info["optimization"] = {
        "acl_graph": settings.ASCEND_ENABLE_ACL_GRAPH,
        "task_queue": settings.ASCEND_TASK_QUEUE_ENABLE,
        "cpu_affinity": settings.ASCEND_CPU_AFFINITY,
        "alloc_conf": settings.ASCEND_ALLOC_CONF,
    }

    return info


@router.get("/vllm-health")
async def vllm_health() -> dict[str, Any]:
    """检查 vLLM-Ascend 服务健康状态"""
    try:
        from app.core.ascend import get_vllm_client

        client = get_vllm_client()
        healthy = await client.check_health()
        return {"healthy": healthy, "url": settings.ASCEND_VLLM_BASE_URL}
    except Exception as e:
        return {"healthy": False, "error": str(e)}


@router.post("/warmup")
async def warmup_ascend() -> dict[str, Any]:
    """预热昇腾推理服务（首次推理较慢，提前触发编译缓存）"""
    results: dict[str, Any] = {}

    # LLM 预热
    if settings.LLM_MODE == "ascend":
        try:
            from app.utils.llm import LLMClient

            client = LLMClient()
            response = await client.generate(
                prompt="Hello",
                temperature=0,
                max_tokens=10,
                use_cache=False,
            )
            results["llm_warmup"] = "ok"
            results["llm_response_preview"] = response[:50]
        except Exception as e:
            results["llm_warmup"] = f"failed: {str(e)}"

    # Embedding 预热
    if settings.EMBEDDING_MODE in ("ascend_api", "ascend_local"):
        try:
            from app.utils.embedding import get_embedding_client

            client = get_embedding_client()
            embedding = await client.embed("测试文本")
            results["embedding_warmup"] = "ok"
            results["embedding_dim"] = len(embedding)
        except Exception as e:
            results["embedding_warmup"] = f"failed: {str(e)}"

    return results


@router.put("/mode")
async def switch_llm_mode(request: SwitchModeRequest) -> dict[str, Any]:
    """运行时切换 LLM 推理模式（remote / ascend）"""
    new_mode = request.llm_mode

    # 切换到 ascend 时检查 NPU 可用性
    if new_mode == "ascend":
        try:
            from app.core.ascend import AscendNPUManager

            env = AscendNPUManager.check_environment()
            if not env["npu_available"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "昇腾 NPU 不可用，无法切换到 ascend 模式。"
                        "请检查 CANN 驱动和 torch_npu 安装。"
                    ),
                )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"NPU 环境检查失败: {str(e)}",
            )

    # 更新运行时配置
    old_mode = settings.LLM_MODE
    settings.LLM_MODE = new_mode
    logger.info(f"LLM 模式切换: {old_mode} → {new_mode}")

    # 重新初始化 LLMClient：重置内部客户端引用，下次调用时按新模式创建

    # 清除用户级客户端缓存（可能使用旧模式的连接）
    from app.utils.llm import _user_client_cache

    _user_client_cache.clear()

    # 返回更新后的状态
    result: dict[str, Any] = {
        "llm_mode": settings.LLM_MODE,
        "embedding_mode": settings.EMBEDDING_MODE,
        "previous_mode": old_mode,
    }

    # 附加 NPU 信息
    try:
        from app.core.ascend import AscendNPUManager

        env = AscendNPUManager.check_environment()
        result["npu"] = {
            "available": env["npu_available"],
            "device_count": env["device_count"],
            "cann_version": env.get("cann_version"),
            "torch_npu_installed": env["torch_npu_installed"],
        }
    except Exception as e:
        result["npu"] = {"available": False, "error": str(e)}

    # 附加 vLLM-Ascend 状态
    if new_mode == "ascend":
        try:
            from app.core.ascend import get_vllm_client

            client = get_vllm_client()
            healthy = await client.check_health()
            result["vllm_ascend"] = {
                "healthy": healthy,
                "base_url": settings.ASCEND_VLLM_BASE_URL,
                "model": settings.ASCEND_LLM_MODEL,
            }
        except Exception as e:
            result["vllm_ascend"] = {"healthy": False, "error": str(e)}

    return result

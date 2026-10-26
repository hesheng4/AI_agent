"""昇腾 NPU Profiling API 端点

提供 Profiling 配置查询、脚本生成、采集触发和结果查看等功能。

端点:
    GET  /profiling/status       — 查看 Profiling 模块状态
    GET  /profiling/levels       — 查看采集级别说明
    POST /profiling/generate     — 生成 Profiling 采集脚本
    POST /profiling/run          — 触发 Profiling 采集（实际执行）
    GET  /profiling/task-status  — 查询当前采集任务状态
    POST /profiling/stop         — 终止当前采集任务
    GET  /profiling/results      — 查看采集结果（扫描文件系统）
    GET  /profiling/checklist    — 获取分析检查清单
    GET  /profiling/env-check    — 环境预检
    POST /profiling/generate-deepspeed — 生成 DeepSpeed 多卡采集脚本
"""

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.profiling import (
    ProfilingConfig,
    ProfilingLevel,
    ProfilingScenario,
    execute_profiling,
    generate_deepspeed_script,
    generate_gpu_comparison_script,
    generate_hf_trainer_callback,
    generate_lightning_callback,
    generate_profiling_script,
    query_profiling_status,
    scan_profiling_results,
    stop_profiling,
)

router = APIRouter(dependencies=[Depends(get_current_user)])


# ========== 请求模型 ==========


class ProfilingGenerateRequest(BaseModel):
    """脚本生成请求"""

    level: str = Field(default="L0", description="采集级别: L0/L1/L2")
    scenario: str = Field(default="inference", description="场景: training/inference")
    output_dir: str = Field(default="./profiling_output", description="输出目录")
    skip_first: int = Field(default=20, description="跳过前N步（训练场景）")
    wait: int = Field(default=1, description="等待步数")
    warmup: int = Field(default=1, description="预热步数")
    active: int = Field(default=1, description="记录步数")
    repeat: int = Field(default=1, description="重复轮数")
    num_inference_steps: int = Field(default=5, description="推理步数（推理场景）")


class ProfilingRunRequest(BaseModel):
    """采集执行请求"""

    level: str = Field(default="L0", description="采集级别: L0/L1/L2")
    target: str = Field(default="vllm", description="目标: vllm/embedding")
    output_dir: str = Field(default="./profiling_output", description="输出目录")
    num_steps: int = Field(default=5, description="采集步数")


class GPUComparisonRequest(BaseModel):
    """GPU 对比脚本生成请求"""

    output_dir: str = Field(default="./gpu-profiling-output", description="输出目录")
    skip_first: int = Field(default=20, description="跳过前N步")
    wait: int = Field(default=1, description="等待步数")
    warmup: int = Field(default=1, description="预热步数")
    active: int = Field(default=1, description="记录步数")
    repeat: int = Field(default=1, description="重复轮数")


class DeepSpeedScriptRequest(BaseModel):
    """DeepSpeed 多卡采集脚本生成请求"""

    output_dir: str = Field(default="./npu-profiling-deepspeed", description="输出目录")
    skip_first: int = Field(default=20, description="跳过前N步")
    wait: int = Field(default=1, description="等待步数")
    warmup: int = Field(default=1, description="预热步数")
    active: int = Field(default=1, description="记录步数")
    repeat: int = Field(default=1, description="重复轮数")


# ========== 状态存储（简化实现） ==========

_profiling_results: list[dict[str, Any]] = []
_current_profiling: dict[str, Any] | None = None


# ========== 端点 ==========


@router.get("/status")
async def get_profiling_status() -> dict[str, Any]:
    """查看 Profiling 模块状态"""
    # 检查 torch_npu 是否可用
    npu_available = False
    profiler_available = False
    error_msg = None

    try:
        import torch_npu

        npu_available = True
        try:
            import torch_npu.profiler  # noqa: F401

            profiler_available = True
        except ImportError:
            error_msg = "torch_npu.profiler 不可用"
    except ImportError:
        error_msg = "torch_npu 未安装"

    # 检查环境变量
    env_status = {
        "CPU_AFFINITY_CONF": os.environ.get("CPU_AFFINITY_CONF", "未设置"),
        "TASK_QUEUE_ENABLE": os.environ.get("TASK_QUEUE_ENABLE", "未设置"),
    }

    return {
        "npu_available": npu_available,
        "profiler_available": profiler_available,
        "error": error_msg,
        "env_vars": env_status,
        "current_profiling": _current_profiling,
        "completed_count": len(_profiling_results),
    }


@router.get("/levels")
async def get_profiling_levels() -> dict[str, Any]:
    """查看采集级别说明"""
    return {
        "levels": [
            {
                "name": "L0",
                "description": "最小膨胀采集（仅 NPU 活动）",
                "data_size": "小",
                "use_case": "快速定位热点、整体耗时分布",
                "is_default": True,
            },
            {
                "name": "L1",
                "description": "算子级采集（CPU + NPU + 算子详情）",
                "data_size": "中",
                "use_case": "分析 Cube/Vector/MatMul/Conv 算子耗时",
                "is_default": False,
            },
            {
                "name": "L2",
                "description": "完整调用栈 + 内存采集",
                "data_size": "大",
                "use_case": "深度分析调用链、内存瓶颈",
                "is_default": False,
            },
        ],
        "note": (
            "默认采集 L0 级别。仅当明确需要算子分析、调用栈、内存分析时才升级到 L1/L2。"
        ),
    }


@router.post("/generate")
async def generate_profiling(req: ProfilingGenerateRequest) -> dict[str, Any]:
    """生成 Profiling 采集脚本"""
    try:
        level = ProfilingLevel(req.level)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的采集级别: {req.level}")

    try:
        scenario = ProfilingScenario(req.scenario)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的场景: {req.scenario}")

    config = ProfilingConfig(
        level=level,
        scenario=scenario,
        output_dir=req.output_dir,
        skip_first=req.skip_first,
        wait=req.wait,
        warmup=req.warmup,
        active=req.active,
        repeat=req.repeat,
        num_inference_steps=req.num_inference_steps,
    )

    script = generate_profiling_script(config)

    return {
        "level": req.level,
        "scenario": req.scenario,
        "config": config.to_dict(),
        "script": script,
        "usage": (
            f"python scripts/run_profiling.py --level {req.level} "
            f"--scenario {req.scenario} --target script"
        ),
    }


@router.post("/run")
async def run_profiling(req: ProfilingRunRequest) -> dict[str, Any]:
    """触发 Profiling 采集（实际执行）

    在后台子进程中启动采集任务，立即返回任务句柄。
    通过 GET /profiling/task-status 轮询任务状态，
    通过 POST /profiling/stop 终止任务。
    """
    try:
        ProfilingLevel(req.level)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的采集级别: {req.level}")

    try:
        task = execute_profiling(
            level=req.level,
            target=req.target,
            output_dir=req.output_dir,
            num_steps=req.num_steps,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return task


@router.get("/task-status")
async def get_task_status() -> dict[str, Any]:
    """查询当前采集任务状态"""
    return query_profiling_status()


@router.post("/stop")
async def stop_current_task() -> dict[str, Any]:
    """终止当前采集任务"""
    return stop_profiling()


@router.get("/results")
async def get_profiling_results(
    output_dir: str = "./profiling_output"
) -> dict[str, Any]:
    """查看采集结果（扫描文件系统）"""
    results = scan_profiling_results(output_dir)
    return {
        "count": len(results),
        "output_dir": output_dir,
        "results": results,
    }


@router.get("/checklist")
async def get_analysis_checklist() -> dict[str, Any]:
    """获取分析检查清单"""
    return {
        "template_path": "docs/references/analysis-checklist.md",
        "bottleneck_criteria": [
            {
                "type": "计算瓶颈",
                "criteria": "Cube 算子占比 > 70%",
                "action": "优化算子实现、考虑融合算子",
            },
            {
                "type": "通信瓶颈",
                "criteria": "通信算子占比 > 30%",
                "action": "优化通信拓扑、梯度压缩",
            },
            {
                "type": "内存瓶颈",
                "criteria": "内存使用率 > 90% 或碎片率高",
                "action": "优化内存分配策略、梯度检查点",
            },
            {
                "type": "Host 瓶颈",
                "criteria": "CPU 算子耗时占比 > 40%",
                "action": "开启 TASK_QUEUE_ENABLE、CPU 绑核",
            },
            {
                "type": "IO 瓶颈",
                "criteria": "数据搬运耗时占比 > 20%",
                "action": "优化数据加载、预取策略",
            },
        ],
    }


@router.get("/env-check")
async def check_profiling_env() -> dict[str, Any]:
    """环境预检"""

    checks: dict[str, dict[str, Any]] = {
        "torch_npu": {"available": False, "detail": None},
        "profiler": {"available": False, "detail": None},
        "npu_device": {"available": False, "detail": None},
        "env_vars": {},
    }

    # 检查 torch_npu
    try:
        import torch_npu

        checks["torch_npu"]["available"] = True
        checks["torch_npu"]["detail"] = getattr(torch_npu, "__version__", "unknown")

        # 检查 profiler
        try:
            import torch_npu.profiler

            checks["profiler"]["available"] = True
            checks["profiler"]["detail"] = "torch_npu.profiler 可用"
        except ImportError:
            checks["profiler"]["detail"] = "torch_npu.profiler 不可用"

        # 检查 NPU 设备
        try:
            import torch

            checks["npu_device"]["available"] = torch.npu.is_available()
            checks["npu_device"]["detail"] = f"设备数: {torch.npu.device_count()}"
        except Exception as e:
            checks["npu_device"]["detail"] = str(e)

    except ImportError:
        checks["torch_npu"]["detail"] = "torch_npu 未安装（非 NPU 环境）"

    # 环境变量
    checks["env_vars"] = {
        "CPU_AFFINITY_CONF": os.environ.get("CPU_AFFINITY_CONF", "未设置"),
        "TASK_QUEUE_ENABLE": os.environ.get("TASK_QUEUE_ENABLE", "未设置"),
        "ASCEND_HOME_PATH": os.environ.get("ASCEND_HOME_PATH", "未设置"),
    }

    # 总体状态
    all_ok = (
        checks["torch_npu"]["available"]
        and checks["profiler"]["available"]
        and checks["npu_device"]["available"]
    )

    return {
        "all_checks_passed": all_ok,
        "checks": checks,
        "recommendation": (
            "环境就绪，可以开始 Profiling 采集"
            if all_ok
            else (
                "部分检查未通过。在非 NPU 环境下，请通过 CLI 脚本在目标机器上执行采集。"
            )
        ),
    }


@router.post("/generate-gpu-comparison")
async def generate_gpu_comparison(req: GPUComparisonRequest) -> dict[str, Any]:
    """生成 GPU 对比采集脚本

    GPU 采集使用原生 torch.profiler，与 NPU 的区别：
    1. 使用 torch.profiler.profile 而非 torch_npu.profiler.profile
    2. 使用 torch.profiler.ProfilerActivity.CUDA 而非 NPU
    3. 不使用 experimental_config 参数
    """
    script = generate_gpu_comparison_script(
        output_dir=req.output_dir,
        skip_first=req.skip_first,
        wait=req.wait,
        warmup=req.warmup,
        active=req.active,
        repeat=req.repeat,
    )

    return {
        "output_dir": req.output_dir,
        "script": script,
        "differences_from_npu": [
            "使用 torch.profiler.profile 而非 torch_npu.profiler.profile",
            "使用 ProfilerActivity.CUDA 而非 ProfilerActivity.NPU",
            "不使用 experimental_config 参数（GPU 无此参数）",
        ],
    }


@router.post("/generate-lightning-callback")
async def generate_lightning_callback_api(
    output_dir: str = "./npu-profiling",
    level: str = "L0",
    skip_first: int = 20,
) -> dict[str, Any]:
    """生成 PyTorch Lightning Profiling Callback"""
    if level not in ("L0", "L1", "L2"):
        raise HTTPException(status_code=400, detail=f"无效的采集级别: {level}")

    code = generate_lightning_callback(
        output_dir=output_dir,
        level=level,
        skip_first=skip_first,
    )

    return {
        "level": level,
        "callback_code": code,
        "usage": "将 Callback 加入 Trainer 的 callbacks 列表",
    }


@router.post("/generate-hf-callback")
async def generate_hf_callback_api(
    output_dir: str = "./npu-profiling",
    skip_first: int = 20,
) -> dict[str, Any]:
    """生成 HuggingFace Transformers Trainer Profiling Callback"""
    code = generate_hf_trainer_callback(
        output_dir=output_dir,
        skip_first=skip_first,
    )

    return {
        "callback_code": code,
        "usage": "将 Callback 加入 Trainer 的 callbacks 列表",
    }


@router.post("/generate-deepspeed")
async def generate_deepspeed_script_api(req: DeepSpeedScriptRequest) -> dict[str, Any]:
    """生成 DeepSpeed 多卡 Profiling 采集脚本

    遵循 skill 4.3 节规范：
    - 仅在 rank 0 上采集以减少数据量
    - prof.step() 必须在 model_engine.step() 之后调用
    """
    script = generate_deepspeed_script(
        output_dir=req.output_dir,
        skip_first=req.skip_first,
        wait=req.wait,
        warmup=req.warmup,
        active=req.active,
        repeat=req.repeat,
    )

    return {
        "output_dir": req.output_dir,
        "script": script,
        "key_points": [
            "仅在 rank 0 上采集以减少数据量",
            "prof.step() 必须在 model_engine.step() 之后调用",
            "不修改训练脚本中的 CUDA 代码，torch_npu 自动迁移",
        ],
        "usage": "deepspeed --num_gpus=N train.py --deepspeed_config ds_config.json",
    }

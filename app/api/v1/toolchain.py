"""昇腾 NPU 推理工具链 API 端点

遵循 quantify-agent skill 规范：
- 启动前先执行硬件检查
- 设置必要环境变量
- 覆盖安装、运行、量化、评测全流程
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.toolchain import (
    AISBenchConfig,
    ModelArchitecture,
    QuantizationConfig,
    QuantizationFormat,
    VLLMRunConfig,
    check_npu_hardware,
    diagnose_vllm_error,
    generate_aisbench_script,
    generate_quantization_script,
    generate_sensitivity_script,
    generate_vllm_launch_command,
    get_common_env_setup,
    get_recommended_vllm_config,
    get_vllm_install_guide,
    validate_path_safety,
    verify_ascend_environment,
)

router = APIRouter(dependencies=[Depends(get_current_user)])


# ========== Request Models ==========


class NPUCheckRequest(BaseModel):
    """硬件检查请求"""

    device_ids: str = Field(default="0,1,2,3", description="NPU 设备 ID（逗号分隔）")
    auto_kill_stale: bool = Field(
        default=False, description="自动清理非本任务进程（需确认）"
    )


class VLLMLaunchRequest(BaseModel):
    """vLLM 启动命令生成请求"""

    model: str = Field(description="模型名称或路径")
    tp_size: int = Field(default=4, ge=1, description="张量并行度")
    ep_size: int = Field(default=0, ge=0, description="专家并行度（MoE）")
    dp_size: int = Field(default=1, ge=1, description="数据并行度")
    max_model_len: int = Field(default=8192, description="最大序列长度")
    quantization: str | None = Field(default=None, description="量化格式")
    enable_chunked_prefill: bool = Field(default=False, description="分块预填充")
    enable_prefix_caching: bool = Field(default=True, description="前缀缓存")
    gpu_memory_utilization: float = Field(
        default=0.9, ge=0.1, le=0.99, description="显存利用率"
    )
    max_num_seqs: int = Field(default=256, ge=1, description="最大并发序列数")
    port: int = Field(default=8001, ge=1024, le=65535, description="服务端口")
    extra_args: dict[str, Any] | None = Field(default=None, description="额外参数")


class VLLMDiagnoseRequest(BaseModel):
    """vLLM 错误诊断请求"""

    error_output: str = Field(description="vLLM 错误输出文本")


class QuantizationRequest(BaseModel):
    """量化请求"""

    model_path: str = Field(description="模型路径")
    output_path: str = Field(description="输出路径")
    format: str = Field(default="w8a8", description="量化格式: w8a8 / w4a16 / w8a16")
    dataset: str = Field(default="random", description="校准数据集")
    num_samples: int = Field(default=128, ge=1, description="校准样本数")
    seq_length: int = Field(default=2048, ge=128, description="序列长度")
    batch_size: int = Field(default=1, ge=1, description="批大小")
    anti_overflow: bool = Field(default=True, description="防溢出")
    w16a16_ref: bool = Field(default=False, description="使用 W16A16 参考实现")


class SensitivityRequest(BaseModel):
    """敏感度分析请求"""

    model_path: str = Field(description="模型路径")
    output_dir: str = Field(default="./sensitivity_results", description="输出目录")
    quant_format: str = Field(default="w8a8", description="量化格式")


class AISBenchRequest(BaseModel):
    """AISBench 评测请求"""

    model_name: str = Field(description="模型名称")
    benchmark: str = Field(default="gsm8k", description="评测基准")
    num_fewshot: int = Field(default=5, ge=0, description="Few-shot 数量")
    batch_size: int = Field(default=1, ge=1, description="批大小")
    max_tokens: int = Field(default=1024, ge=1, description="最大生成 token 数")
    temperature: float = Field(default=0.0, ge=0.0, le=2.0, description="温度")
    vllm_url: str = Field(
        default="http://127.0.0.1:8001/v1", description="vLLM 服务地址"
    )


class RecommendedConfigRequest(BaseModel):
    """推荐配置请求"""

    model_name: str = Field(description="模型名称")
    npu_count: int = Field(default=4, ge=1, description="NPU 卡数")
    model_arch: str = Field(default="dense", description="模型架构: dense / moe")
    quant_format: str | None = Field(default=None, description="量化格式")


# ========== API Endpoints ==========


@router.get("/status")
async def toolchain_status() -> dict[str, Any]:
    """推理工具链状态"""
    return {
        "module": "ascend_toolchain",
        "status": "active",
        "description": "昇腾 NPU 推理工具链",
        "features": [
            "硬件检查 (npu-smi info)",
            "vLLM-Ascend 安装引导",
            "vLLM 启动命令生成",
            "vLLM 错误诊断",
            "msmodelslim 量化",
            "敏感度分析",
            "AISBench 评测",
            "环境验证",
        ],
        "workflow": [
            "1. 硬件检查: GET /toolchain/hardware-check",
            "2. 安装 vLLM: GET /toolchain/vllm-install-guide",
            "3. 生成启动命令: POST /toolchain/vllm-launch",
            "4. 运行 vLLM 服务",
            "5. 如遇错误: POST /toolchain/vllm-diagnose",
            "6. [可选] 量化模型: POST /toolchain/quantize",
            "7. [可选] 评测精度: POST /toolchain/aisbench",
        ],
    }


@router.get("/hardware-check")
async def hardware_check() -> dict[str, Any]:
    """执行 NPU 硬件检查

    遵循 quantify-agent skill 规范：在每次推理任务开始前执行。
    """
    result = check_npu_hardware()
    return result.to_dict()


@router.get("/env-setup")
async def env_setup(device_ids: str = "0,1,2,3") -> dict[str, Any]:
    """获取推荐的公共环境变量"""
    env_vars = get_common_env_setup(device_ids)
    return {
        "env_vars": env_vars,
        "apply_commands": [f"export {k}={v}" for k, v in env_vars.items()],
        "note": (
            "ASCEND_RT_VISIBLE_DEVICES 控制 vLLM 和 msmodelslim 可见的 NPU，"
            "设置后两个工具都会遵守"
        ),
    }


@router.get("/verify-environment")
async def verify_environment() -> dict[str, Any]:
    """验证完整的昇腾推理环境

    检查 CANN、NPU Driver、torch_npu、vllm_ascend、msmodelslim 安装状态
    和关键环境变量。
    """
    return verify_ascend_environment()


@router.get("/vllm-install-guide")
async def vllm_install_guide() -> dict[str, Any]:
    """获取 vLLM-Ascend 安装指引"""
    guide = get_vllm_install_guide()
    return guide.to_dict()


@router.post("/vllm-launch")
async def vllm_launch(req: VLLMLaunchRequest) -> dict[str, Any]:
    """生成 vLLM-Ascend 启动命令

    包含环境变量设置和优化参数。
    """
    # 校验 model 路径安全性
    validate_path_safety(req.model, "model")

    config = VLLMRunConfig(
        model=req.model,
        tp_size=req.tp_size,
        ep_size=req.ep_size,
        dp_size=req.dp_size,
        max_model_len=req.max_model_len,
        quantization=req.quantization,
        enable_chunked_prefill=req.enable_chunked_prefill,
        enable_prefix_caching=req.enable_prefix_caching,
        gpu_memory_utilization=req.gpu_memory_utilization,
        max_num_seqs=req.max_num_seqs,
        port=req.port,
        extra_args=req.extra_args or {},
    )
    command = generate_vllm_launch_command(config)
    return {
        "command": command,
        "config": config.to_dict(),
        "notes": [
            "启动前先运行硬件检查确认 NPU 状态",
            "首次推理较慢（算子编译），后续会加速",
            "可通过 /api/v1/ascend/warmup 预热模型",
        ],
    }


@router.post("/vllm-diagnose")
async def vllm_diagnose(req: VLLMDiagnoseRequest) -> dict[str, Any]:
    """诊断 vLLM-Ascend 运行错误"""
    diagnoses = diagnose_vllm_error(req.error_output)
    return {
        "diagnoses": diagnoses,
        "error_output_preview": (
            req.error_output[:500] if len(req.error_output) > 500 else req.error_output
        ),
    }


@router.post("/quantize")
async def quantize(req: QuantizationRequest) -> dict[str, Any]:
    """生成 msmodelslim 量化脚本

    量化为端到端迭代流程：
    1. 使用校准数据集对模型进行量化
    2. 评测量化后模型精度
    3. 如精度不达标，进行敏感度分析
    4. 跳过敏感层重新量化
    """
    try:
        q_format = QuantizationFormat(req.format)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=(
                f"不支持的量化格式: {req.format}，可选: w8a8, w4a16, w8a16, fp16, bf16"
            ),
        )

    # 校验路径安全性
    validate_path_safety(req.model_path, "model_path")
    validate_path_safety(req.output_path, "output_path")

    config = QuantizationConfig(
        model_path=req.model_path,
        output_path=req.output_path,
        format=q_format,
        dataset=req.dataset,
        num_samples=req.num_samples,
        seq_length=req.seq_length,
        batch_size=req.batch_size,
        anti_overflow=req.anti_overflow,
        w16a16_ref=req.w16a16_ref,
    )

    script = generate_quantization_script(config)

    return {
        "script": script,
        "config": config.to_dict(),
        "workflow": [
            "1. 运行量化脚本生成量化模型",
            "2. 启动量化后的 vLLM 服务进行推理验证",
            "3. 如精度不达标，使用 /toolchain/sensitivity 进行敏感度分析",
            "4. 根据敏感度结果，跳过敏感层重新量化",
            "5. 使用 /toolchain/aisbench 评测最终精度",
        ],
        "note": (
            "量化前先运行硬件检查确认 NPU 状态，确保 ASCEND_RT_VISIBLE_DEVICES 设置正确"
        ),
    }


@router.post("/sensitivity")
async def sensitivity(req: SensitivityRequest) -> dict[str, Any]:
    """生成敏感度分析脚本

    用于诊断量化精度下降，逐层分析敏感度。
    敏感层建议保持 FP16 精度。
    """
    # 校验路径安全性
    validate_path_safety(req.model_path, "model_path")
    validate_path_safety(req.output_dir, "output_dir")

    script = generate_sensitivity_script(
        model_path=req.model_path,
        output_dir=req.output_dir,
        quant_format=req.quant_format,
    )
    return {
        "script": script,
        "model_path": req.model_path,
        "output_dir": req.output_dir,
        "workflow": [
            "1. 运行脚本获取每层量化敏感度",
            "2. 查看 sensitivity_results.json 找出敏感层",
            "3. 在量化脚本中将敏感层加入 disable_names",
            "4. 重新量化并验证精度",
        ],
    }


@router.post("/aisbench")
async def aisbench(req: AISBenchRequest) -> dict[str, Any]:
    """生成 AISBench 评测脚本

    需要vLLM 服务已启动。
    """
    config = AISBenchConfig(
        model_name=req.model_name,
        benchmark=req.benchmark,
        num_fewshot=req.num_fewshot,
        batch_size=req.batch_size,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
        vllm_url=req.vllm_url,
    )
    script = generate_aisbench_script(config)
    return {
        "script": script,
        "config": config.to_dict(),
        "prerequisites": [
            f"vLLM 服务已启动（{req.vllm_url}）",
            "lm-eval-harness 已安装（脚本会自动安装）",
        ],
    }


@router.post("/recommended-config")
async def recommended_config(req: RecommendedConfigRequest) -> dict[str, Any]:
    """根据模型和硬件生成推荐的 vLLM 运行配置"""
    try:
        arch = ModelArchitecture(req.model_arch)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"不支持的架构: {req.model_arch}，可选: dense, moe"
        )

    q_format = None
    if req.quant_format:
        try:
            q_format = QuantizationFormat(req.quant_format)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"不支持的量化格式: {req.quant_format}"
            )

    config = get_recommended_vllm_config(
        model_name=req.model_name,
        npu_count=req.npu_count,
        model_arch=arch,
        quant_format=q_format,
    )

    command = generate_vllm_launch_command(config)

    return {
        "config": config.to_dict(),
        "launch_command": command,
    }


@router.get("/quick-reference")
async def quick_reference() -> dict[str, Any]:
    """推理工具链快速参考"""
    return {
        "workflow": [
            "1. 硬件检查: npu-smi info → GET /toolchain/hardware-check",
            "2. 环境设置: export VLLM_WORKER_MULTIPROC_METHOD=spawn 等",
            "3. 安装 vLLM: pip install vllm-ascend",
            "4. 启动服务: POST /toolchain/vllm-launch",
            "5. [可选] 量化: POST /toolchain/quantize",
            "6. [可选] 评测: POST /toolchain/aisbench",
        ],
        "required_env_vars": {
            "VLLM_WORKER_MULTIPROC_METHOD": "spawn（vLLM 多进程必需）",
            "VLLM_USE_MODELSCOPE": "true（国内推荐）",
            "ASCEND_RT_VISIBLE_DEVICES": "0,1,2,3（控制可见 NPU）",
            "TASK_QUEUE_ENABLE": "2（性能优化）",
            "PYTORCH_NPU_ALLOC_CONF": "expandable_segments（内存优化）",
            "ASCEND_ENABLE_ACL_GRAPH": "1（图编译加速）",
        },
        "common_troubleshooting": [
            {"issue": "OOM", "solution": "减小 max_model_len 或增大 TP"},
            {"issue": "HCCL 初始化失败", "solution": "HCCL_CONNECT_TIMEOUT=7200"},
            {
                "issue": "Worker 崩溃",
                "solution": "确认 VLLM_WORKER_MULTIPROC_METHOD=spawn",
            },
            {
                "issue": "torch_npu 导入失败",
                "solution": "pip install torch_npu，匹配 PyTorch 版本",
            },
        ],
        "source_debugging_tip": (
            "使用 pip show <package> 找到可编辑源码位置进行深度调试"
        ),
    }

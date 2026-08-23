"""昇腾模型适配验证 API 端点

遵循 verify-agent-plus skill 规范：
完整验证流水线：环境预检 → 模型部署 → 精度测试 → 性能基准 → 资源清理 → 报告生成
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.validator import (
    BenchmarkConfig,
    ValidationConfig,
    VLLMServerConfig,
    generate_vllm_serve_command,
    get_preset_config,
    list_supported_models,
    run_accuracy_test,
    run_benchmark_latency,
    run_benchmark_serve,
    run_benchmark_throughput,
    run_environment_check,
    run_validation,
)

router = APIRouter(dependencies=[Depends(get_current_user)])


# ========== Request Models ==========


class VLLMServerConfigRequest(BaseModel):
    """vLLM 服务器配置请求"""

    host: str = Field(default="0.0.0.0", description="服务监听地址")
    port: int = Field(default=8000, ge=1024, le=65535, description="服务端口")
    tensor_parallel_size: int = Field(default=2, ge=1, description="张量并行度")
    data_parallel_size: int = Field(default=1, ge=1, description="数据并行度")
    max_model_len: int = Field(default=133000, description="最大序列长度")
    gpu_memory_utilization: float = Field(
        default=0.90, ge=0.1, le=0.99, description="显存利用率"
    )
    max_num_seqs: int = Field(default=32, ge=1, description="最大并发序列数")
    max_num_batched_tokens: int = Field(default=8096, description="单步最大处理 tokens")
    seed: int = Field(default=1024, description="随机种子")
    trust_remote_code: bool = Field(default=True, description="信任远程代码")
    enable_prefix_caching: bool = Field(default=False, description="前缀缓存")
    compilation_config: dict[str, Any] | None = Field(
        default=None,
        description='图编译配置，如 {"cudagraph_mode": "FULL_DECODE_ONLY"}',
    )
    additional_config: dict[str, Any] | None = Field(
        default=None, description='额外配置，如 {"enable_cpu_binding": true}'
    )
    async_scheduling: bool = Field(default=True, description="异步调度")
    quantization: str | None = Field(default=None, description="量化方式，如 ascend")
    served_model_name: str | None = Field(default=None, description="服务模型名称")


class BenchmarkConfigRequest(BaseModel):
    """性能基准测试配置请求"""

    input_len: int = Field(default=200, ge=1, description="输入序列长度")
    output_len: int = Field(default=200, ge=1, description="输出序列长度")
    num_prompts: int = Field(default=200, ge=1, description="请求数量 (serve)")
    request_rate: int = Field(default=1, ge=1, description="请求速率 (serve)")
    num_iterations: int = Field(default=10, ge=1, description="迭代次数 (latency)")
    num_batches: int = Field(default=16, ge=1, description="批次数 (throughput)")
    dataset_name: str = Field(default="random", description="数据集名称")


class ValidationRequest(BaseModel):
    """完整验证请求"""

    model_path: str = Field(description="模型权重路径")
    model_name: str = Field(default="Qwen3.5-27B", description="模型标识")
    hardware_type: str = Field(default="Atlas 800 A2", description="硬件类型")
    is_quantized: bool = Field(default=True, description="是否量化模型")
    vllm_server_config: VLLMServerConfigRequest | None = Field(
        default=None, description="vLLM 服务器配置"
    )
    benchmark_config: BenchmarkConfigRequest | None = Field(
        default=None, description="性能测试配置"
    )
    run_accuracy_test: bool = Field(default=True, description="是否执行精度测试")
    run_performance_tests: list[str] | None = Field(
        default=None, description="性能测试类型: serve, latency, throughput"
    )
    report_output_dir: str = Field(
        default="./validation_reports", description="报告输出目录"
    )
    api_timeout: int = Field(default=60, ge=10, description="API 请求超时（秒）")
    api_retries: int = Field(default=2, ge=0, description="API 请求重试次数")
    server_startup_timeout: int = Field(
        default=300, ge=60, description="服务启动超时（秒）"
    )


class QuickAccuracyRequest(BaseModel):
    """快速精度验证请求"""

    model_name: str = Field(description="模型名称（served_model_name）")
    host: str = Field(default="0.0.0.0", description="服务地址")
    port: int = Field(default=8000, description="服务端口")
    timeout: int = Field(default=60, ge=10, description="超时（秒）")


class BenchmarkServeRequest(BaseModel):
    """serve 模式基准测试请求"""

    model_path: str = Field(description="模型路径")
    input_len: int = Field(default=200, ge=1)
    num_prompts: int = Field(default=200, ge=1)
    request_rate: int = Field(default=1, ge=1)
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)


class BenchmarkLatencyRequest(BaseModel):
    """latency 模式基准测试请求"""

    model_path: str = Field(description="模型路径")
    input_len: int = Field(default=200, ge=1)
    output_len: int = Field(default=200, ge=1)
    num_iterations: int = Field(default=10, ge=1)


class BenchmarkThroughputRequest(BaseModel):
    """throughput 模式基准测试请求"""

    model_path: str = Field(description="模型路径")
    input_len: int = Field(default=200, ge=1)
    output_len: int = Field(default=200, ge=1)
    num_batches: int = Field(default=16, ge=1)


# ========== API Endpoints ==========


@router.get("/status")
async def validator_status():
    """验证模块状态"""
    return {
        "module": "ascend_validator",
        "status": "active",
        "description": "昇腾模型适配验证",
        "workflow": [
            "1. 环境预检: GET /validator/env-check",
            "2. 模型部署: POST /validator/deploy-command",
            "3. 精度验证: POST /validator/accuracy",
            "4. 性能基准: POST /validator/benchmark/{serve|latency|throughput}",
            "5. 一键验证: POST /validator/run",
            "6. 支持模型: GET /validator/models",
        ],
        "supported_models": list_supported_models(),
    }


@router.get("/env-check")
async def env_check():
    """Step 1: 环境预检

    检查 NPU 驱动、vLLM 安装、昇腾设备可用性
    """
    result = run_environment_check()
    return result.to_dict()


@router.post("/deploy-command")
async def deploy_command(req: ValidationRequest):
    """Step 2: 生成 vLLM 服务启动命令

    生成包含环境变量和优化参数的完整启动命令
    """
    vllm_cfg = req.vllm_server_config
    server_config = VLLMServerConfig(
        host=vllm_cfg.host if vllm_cfg else "0.0.0.0",
        port=vllm_cfg.port if vllm_cfg else 8000,
        tensor_parallel_size=vllm_cfg.tensor_parallel_size if vllm_cfg else 2,
        data_parallel_size=vllm_cfg.data_parallel_size if vllm_cfg else 1,
        max_model_len=vllm_cfg.max_model_len if vllm_cfg else 133000,
        gpu_memory_utilization=vllm_cfg.gpu_memory_utilization if vllm_cfg else 0.90,
        max_num_seqs=vllm_cfg.max_num_seqs if vllm_cfg else 32,
        max_num_batched_tokens=vllm_cfg.max_num_batched_tokens if vllm_cfg else 8096,
        seed=vllm_cfg.seed if vllm_cfg else 1024,
        trust_remote_code=vllm_cfg.trust_remote_code if vllm_cfg else True,
        enable_prefix_caching=vllm_cfg.enable_prefix_caching if vllm_cfg else False,
        compilation_config=(
            vllm_cfg.compilation_config
            if vllm_cfg and vllm_cfg.compilation_config
            else {"cudagraph_mode": "FULL_DECODE_ONLY"}
        ),
        additional_config=(
            vllm_cfg.additional_config
            if vllm_cfg and vllm_cfg.additional_config
            else {"enable_cpu_binding": True}
        ),
        async_scheduling=vllm_cfg.async_scheduling if vllm_cfg else True,
        quantization=(
            vllm_cfg.quantization
            if vllm_cfg
            else ("ascend" if req.is_quantized else None)
        ),
        served_model_name=vllm_cfg.served_model_name if vllm_cfg else None,
    )

    config = ValidationConfig(
        model_path=req.model_path,
        model_name=req.model_name,
        hardware_type=req.hardware_type,
        is_quantized=req.is_quantized,
        vllm_server=server_config,
    )

    command = generate_vllm_serve_command(config)
    return {
        "command": command,
        "config": config.to_dict(),
        "qwen35_27b_reference": {
            "model_path": "Eco-Tech/Qwen3.5-27B-w8a8-mtp",
            "served_model_name": "qwen3.5",
            "tp_size": 2,
            "max_model_len": 133000,
            "gsm8k_accuracy": 96.74,
        },
    }


@router.post("/accuracy")
async def accuracy_test(req: QuickAccuracyRequest):
    """Step 3.1: 精度验证

    通过 chat/completions API 验证模型基本推理能力
    """
    result = run_accuracy_test(
        model_name=req.model_name,
        host=req.host,
        port=req.port,
        timeout=req.timeout,
    )
    return result.to_dict()


@router.post("/benchmark/serve")
async def benchmark_serve(req: BenchmarkServeRequest):
    """Step 3.2a: serve 模式在线吞吐测试 (QPS, TTFT, TPOT)"""
    benchmark = BenchmarkConfig(
        input_len=req.input_len,
        num_prompts=req.num_prompts,
        request_rate=req.request_rate,
    )
    result = run_benchmark_serve(
        model_path=req.model_path,
        benchmark=benchmark,
        host=req.host,
        port=req.port,
    )
    return result.to_dict()


@router.post("/benchmark/latency")
async def benchmark_latency(req: BenchmarkLatencyRequest):
    """Step 3.2b: latency 模式单请求延迟测试 (P50/P90/P99)"""
    benchmark = BenchmarkConfig(
        input_len=req.input_len,
        output_len=req.output_len,
        num_iterations=req.num_iterations,
    )
    result = run_benchmark_latency(
        model_path=req.model_path,
        benchmark=benchmark,
    )
    return result.to_dict()


@router.post("/benchmark/throughput")
async def benchmark_throughput(req: BenchmarkThroughputRequest):
    """Step 3.2c: throughput 模式离线吞吐测试 (tokens/sec)"""
    benchmark = BenchmarkConfig(
        input_len=req.input_len,
        output_len=req.output_len,
        num_batches=req.num_batches,
    )
    result = run_benchmark_throughput(
        model_path=req.model_path,
        benchmark=benchmark,
    )
    return result.to_dict()


@router.post("/run")
async def run_full_validation(req: ValidationRequest):
    """一键执行完整验证流水线

    环境预检 → 模型部署 → 精度测试 → 性能基准 → 资源清理 → 报告生成
    """
    # 构建配置
    vllm_cfg = req.vllm_server_config
    bench_cfg = req.benchmark_config

    server_config = VLLMServerConfig(
        host=vllm_cfg.host if vllm_cfg else "0.0.0.0",
        port=vllm_cfg.port if vllm_cfg else 8000,
        tensor_parallel_size=vllm_cfg.tensor_parallel_size if vllm_cfg else 2,
        data_parallel_size=vllm_cfg.data_parallel_size if vllm_cfg else 1,
        max_model_len=vllm_cfg.max_model_len if vllm_cfg else 133000,
        gpu_memory_utilization=vllm_cfg.gpu_memory_utilization if vllm_cfg else 0.90,
        max_num_seqs=vllm_cfg.max_num_seqs if vllm_cfg else 32,
        max_num_batched_tokens=vllm_cfg.max_num_batched_tokens if vllm_cfg else 8096,
        seed=vllm_cfg.seed if vllm_cfg else 1024,
        trust_remote_code=vllm_cfg.trust_remote_code if vllm_cfg else True,
        enable_prefix_caching=vllm_cfg.enable_prefix_caching if vllm_cfg else False,
        compilation_config=(
            vllm_cfg.compilation_config
            if vllm_cfg and vllm_cfg.compilation_config
            else {"cudagraph_mode": "FULL_DECODE_ONLY"}
        ),
        additional_config=(
            vllm_cfg.additional_config
            if vllm_cfg and vllm_cfg.additional_config
            else {"enable_cpu_binding": True}
        ),
        async_scheduling=vllm_cfg.async_scheduling if vllm_cfg else True,
        quantization=(
            vllm_cfg.quantization
            if vllm_cfg
            else ("ascend" if req.is_quantized else None)
        ),
        served_model_name=vllm_cfg.served_model_name if vllm_cfg else None,
    )

    benchmark_config = BenchmarkConfig(
        input_len=bench_cfg.input_len if bench_cfg else 200,
        output_len=bench_cfg.output_len if bench_cfg else 200,
        num_prompts=bench_cfg.num_prompts if bench_cfg else 200,
        request_rate=bench_cfg.request_rate if bench_cfg else 1,
        num_iterations=bench_cfg.num_iterations if bench_cfg else 10,
        num_batches=bench_cfg.num_batches if bench_cfg else 16,
        dataset_name=bench_cfg.dataset_name if bench_cfg else "random",
    )

    config = ValidationConfig(
        model_path=req.model_path,
        model_name=req.model_name,
        hardware_type=req.hardware_type,
        is_quantized=req.is_quantized,
        vllm_server=server_config,
        benchmark=benchmark_config,
        run_accuracy_test=req.run_accuracy_test,
        run_performance_tests=req.run_performance_tests
        or ["serve", "latency", "throughput"],
        report_output_dir=req.report_output_dir,
        api_timeout=req.api_timeout,
        api_retries=req.api_retries,
        server_startup_timeout=req.server_startup_timeout,
    )

    report = run_validation(config)
    return report.to_dict()


@router.get("/models")
async def supported_models():
    """列出支持的模型和预设配置"""
    return {
        "models": list_supported_models(),
        "presets": {
            "Qwen3.5-27B-w8a8": {
                "model_path": "Eco-Tech/Qwen3.5-27B-w8a8-mtp",
                "tp_size": 2,
                "max_model_len": 133000,
                "quantization": "ascend",
                "gsm8k_reference": 96.74,
                "vllm_serve_command": (
                    "vllm serve Eco-Tech/Qwen3.5-27B-w8a8-mtp \\\n"
                    "  --host 0.0.0.0 --port 8000 \\\n"
                    "  --tensor-parallel-size 2 --data-parallel-size 1 \\\n"
                    "  --seed 1024 --quantization ascend \\\n"
                    "  --served-model-name qwen3.5 \\\n"
                    "  --max-num-seqs 32 --max-model-len 133000 \\\n"
                    "  --max-num-batched-tokens 8096 \\\n"
                    "  --trust-remote-code --gpu-memory-utilization 0.90 \\\n"
                    "  --no-enable-prefix-caching \\\n"
                    "  --compilation-config "
                    '\'{"cudagraph_mode":"FULL_DECODE_ONLY"}\' \\\n'
                    "  --additional-config '{\"enable_cpu_binding\":true}' \\\n"
                    "  --async-scheduling"
                ),
            },
        },
    }


@router.post("/preset/{model_name}")
async def run_preset_validation(
    model_name: str, model_path: str = "", port: int = 8000
):
    """使用预设配置执行验证"""
    preset = get_preset_config(model_name)
    if not preset:
        raise HTTPException(
            status_code=404,
            detail=f"未找到预设配置: {model_name}，可用: Qwen3.5-27B, Qwen3.5-27B-w8a8",
        )

    if model_path:
        preset.model_path = model_path
    preset.vllm_server.port = port

    report = run_validation(preset)
    return report.to_dict()


@router.get("/quick-reference")
async def quick_reference():
    """验证快速参考"""
    return {
        "workflow": [
            "1. 环境预检: GET /validator/env-check",
            "2. 生成启动命令: POST /validator/deploy-command",
            "3. 精度验证: POST /validator/accuracy",
            "4. 性能基准: POST /validator/benchmark/{serve|latency|throughput}",
            "5. 一键验证: POST /validator/run",
        ],
        "qwen35_27b_reference": {
            "model_path": "Eco-Tech/Qwen3.5-27B-w8a8-mtp",
            "tp_size": 2,
            "max_model_len": 133000,
            "gsm8k_accuracy": 96.74,
        },
        "required_env_vars": {
            "VLLM_USE_MODELSCOPE": "true",
            "PYTORCH_NPU_ALLOC_CONF": "expandable_segments:True",
            "HCCL_BUFFSIZE": "512",
            "OMP_PROC_BIND": "false",
            "OMP_NUM_THREADS": "1",
            "TASK_QUEUE_ENABLE": "1",
        },
        "benchmark_modes": {
            "serve": "在线吞吐 (QPS, TTFT, TPOT)",
            "latency": "单请求延迟 (P50/P90/P99)",
            "throughput": "离线吞吐 (tokens/sec)",
        },
    }

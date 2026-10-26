"""昇腾模型适配验证核心模块

遵循 verify-agent-plus skill 规范：
完整验证流水线：环境预检 → 模型部署 → 精度测试 → 性能基准 → 资源清理 → 报告生成

支持模型：
- Qwen3.5-27B (w8a8 量化)
- DeepSeek-V3 等 vLLM-Ascend 支持的模型
"""

import json
import logging
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("ascend_validator")


def _shell_quote(value: object) -> str:
    return shlex.quote(str(value))


# ========== 枚举与数据结构 ==========


class ValidationPhase(Enum):
    """验证阶段"""

    ENV_CHECK = "env_check"
    DEPLOY = "deploy"
    ACCURACY = "accuracy"
    PERFORMANCE = "performance"
    CLEANUP = "cleanup"
    REPORT = "report"


class ValidationStatus(Enum):
    """验证状态"""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class BenchMode(Enum):
    """性能基准测试模式"""

    SERVE = "serve"
    LATENCY = "latency"
    THROUGHPUT = "throughput"


@dataclass
class VLLMServerConfig:
    """vLLM 服务器配置"""

    host: str = "0.0.0.0"
    port: int = 8000
    tensor_parallel_size: int = 2
    data_parallel_size: int = 1
    max_model_len: int = 133000
    gpu_memory_utilization: float = 0.90
    max_num_seqs: int = 32
    max_num_batched_tokens: int = 8096
    seed: int = 1024
    trust_remote_code: bool = True
    enable_prefix_caching: bool = False
    compilation_config: dict[str, Any] = field(
        default_factory=lambda: {"cudagraph_mode": "FULL_DECODE_ONLY"}
    )
    additional_config: dict[str, Any] = field(
        default_factory=lambda: {"enable_cpu_binding": True}
    )
    async_scheduling: bool = True
    quantization: str | None = None
    served_model_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "tensor_parallel_size": self.tensor_parallel_size,
            "data_parallel_size": self.data_parallel_size,
            "max_model_len": self.max_model_len,
            "gpu_memory_utilization": self.gpu_memory_utilization,
            "max_num_seqs": self.max_num_seqs,
            "max_num_batched_tokens": self.max_num_batched_tokens,
            "seed": self.seed,
            "trust_remote_code": self.trust_remote_code,
            "enable_prefix_caching": self.enable_prefix_caching,
            "compilation_config": self.compilation_config,
            "additional_config": self.additional_config,
            "async_scheduling": self.async_scheduling,
            "quantization": self.quantization,
            "served_model_name": self.served_model_name,
        }


@dataclass
class BenchmarkConfig:
    """性能基准测试配置"""

    input_len: int = 200
    output_len: int = 200
    num_prompts: int = 200
    request_rate: int = 1
    num_iterations: int = 10
    num_batches: int = 16
    dataset_name: str = "random"

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_len": self.input_len,
            "output_len": self.output_len,
            "num_prompts": self.num_prompts,
            "request_rate": self.request_rate,
            "num_iterations": self.num_iterations,
            "num_batches": self.num_batches,
            "dataset_name": self.dataset_name,
        }


@dataclass
class ValidationConfig:
    """完整验证配置"""

    model_path: str = ""
    model_name: str = "Qwen3.5-27B"
    hardware_type: str = "Atlas 800 A2"
    is_quantized: bool = True
    vllm_server: VLLMServerConfig = field(default_factory=VLLMServerConfig)
    benchmark: BenchmarkConfig = field(default_factory=BenchmarkConfig)
    run_accuracy_test: bool = True
    run_performance_tests: list[str] = field(
        default_factory=lambda: ["serve", "latency", "throughput"]
    )
    report_output_dir: str = "./validation_reports"
    api_timeout: int = 60
    api_retries: int = 2
    server_startup_timeout: int = 300

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_path": self.model_path,
            "model_name": self.model_name,
            "hardware_type": self.hardware_type,
            "is_quantized": self.is_quantized,
            "vllm_server": self.vllm_server.to_dict(),
            "benchmark": self.benchmark.to_dict(),
            "run_accuracy_test": self.run_accuracy_test,
            "run_performance_tests": self.run_performance_tests,
            "report_output_dir": self.report_output_dir,
            "api_timeout": self.api_timeout,
            "api_retries": self.api_retries,
            "server_startup_timeout": self.server_startup_timeout,
        }


@dataclass
class EnvironmentCheckResult:
    """环境预检结果"""

    npu_smi_ok: bool = False
    npu_device_count: int = 0
    vllm_installed: bool = False
    vllm_version: str = ""
    torch_npu_installed: bool = False
    torch_npu_version: str = ""
    cann_version: str = ""
    driver_version: str = ""
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "npu_smi": self.npu_smi_ok,
            "npu_device_count": self.npu_device_count,
            "vllm_installed": self.vllm_installed,
            "vllm_version": self.vllm_version,
            "torch_npu_installed": self.torch_npu_installed,
            "torch_npu_version": self.torch_npu_version,
            "cann_version": self.cann_version,
            "driver_version": self.driver_version,
            "errors": self.errors,
        }


@dataclass
class AccuracyResult:
    """精度测试结果"""

    dataset: str = ""
    metric_name: str = ""
    metric_value: float = 0.0
    reference_value: float | None = None
    status: ValidationStatus = ValidationStatus.PENDING
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "reference_value": self.reference_value,
            "status": self.status.value,
            "error": self.error,
        }


@dataclass
class PerformanceResult:
    """性能基准测试结果"""

    mode: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)
    status: ValidationStatus = ValidationStatus.PENDING
    error: str = ""
    raw_output: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "metrics": self.metrics,
            "status": self.status.value,
            "error": self.error,
        }


@dataclass
class ValidationReport:
    """验证报告"""

    success: bool = False
    model_name: str = ""
    hardware_type: str = ""
    start_time: str = ""
    end_time: str = ""
    duration_seconds: float = 0.0
    environment_check: EnvironmentCheckResult | None = None
    deploy_status: ValidationStatus = ValidationStatus.PENDING
    accuracy_results: list[AccuracyResult] = field(default_factory=list)
    performance_results: list[PerformanceResult] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    report_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "summary": self._generate_summary(),
            "model_name": self.model_name,
            "hardware_type": self.hardware_type,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "detailed_report": {
                "environment_check": (
                    self.environment_check.to_dict() if self.environment_check else None
                ),
                "deploy_status": self.deploy_status.value,
                "accuracy_evaluation": [r.to_dict() for r in self.accuracy_results],
                "performance_benchmarks": {
                    r.mode: r.to_dict() for r in self.performance_results
                },
            },
            "logs": self.logs,
            "errors": self.errors,
            "report_path": self.report_path,
        }

    def _generate_summary(self) -> str:
        if self.success:
            return f"验证完成，耗时 {self.duration_seconds:.1f} 秒"
        elif self.errors:
            return "验证失败: {}".format("; ".join(self.errors[:3]))
        else:
            return "验证未完成"


# ========== Qwen3.5-27B 预设配置 ==========

QWEN35_27B_PRESET = ValidationConfig(
    model_name="Qwen3.5-27B",
    is_quantized=True,
    vllm_server=VLLMServerConfig(
        host="0.0.0.0",
        port=8000,
        tensor_parallel_size=2,
        data_parallel_size=1,
        max_model_len=133000,
        gpu_memory_utilization=0.90,
        max_num_seqs=32,
        max_num_batched_tokens=8096,
        seed=1024,
        trust_remote_code=True,
        enable_prefix_caching=False,
        compilation_config={"cudagraph_mode": "FULL_DECODE_ONLY"},
        additional_config={"enable_cpu_binding": True},
        async_scheduling=True,
        quantization="ascend",
        served_model_name="qwen3.5",
    ),
    benchmark=BenchmarkConfig(
        input_len=200,
        output_len=200,
        num_prompts=200,
        request_rate=1,
    ),
    run_accuracy_test=True,
    run_performance_tests=["serve", "latency", "throughput"],
)

# GSM8K 参考指标
GSM8K_REFERENCE = {
    "Qwen3.5-27B-w8a8": 96.74,
}


# ========== Step 1: 环境预检 ==========


def run_environment_check() -> EnvironmentCheckResult:
    """Step 1: 环境预检

    检查项：
    - NPU 驱动是否正常 (npu-smi info)
    - vLLM-Ascend 是否已安装 (pip list | grep vllm)
    - 昇腾设备是否可用
    """
    result = EnvironmentCheckResult()

    # npu-smi info
    try:
        output = subprocess.run(
            ["npu-smi", "info"], capture_output=True, text=True, timeout=30
        )
        if output.returncode == 0:
            result.npu_smi_ok = True
            # 统计 NPU 设备数
            device_count = len(re.findall(r"NPU\s+\d+", output.stdout))
            result.npu_device_count = device_count

            # 提取驱动版本
            driver_match = re.search(r"Version\s*:\s*(\S+)", output.stdout)
            if driver_match:
                result.driver_version = driver_match.group(1)

            # 提取 CANN 版本
            cann_match = re.search(r"CANN\s*:\s*(\S+)", output.stdout)
            if cann_match:
                result.cann_version = cann_match.group(1)
        else:
            result.errors.append(f"npu-smi info 失败: {output.stderr[:200]}")
    except FileNotFoundError:
        result.errors.append("npu-smi 命令未找到，请确认 CANN Toolkit 已安装")
    except subprocess.TimeoutExpired:
        result.errors.append("npu-smi info 超时，NPU 驱动可能异常")
    except Exception as e:
        result.errors.append(f"环境检查异常: {str(e)}")

    # vLLM 安装检查
    try:
        output = subprocess.run(
            ["pip", "show", "vllm"], capture_output=True, text=True, timeout=10
        )
        if output.returncode == 0:
            result.vllm_installed = True
            for line in output.stdout.splitlines():
                if line.startswith("Version:"):
                    result.vllm_version = line.split(":", 1)[1].strip()
    except Exception:
        pass

    # torch_npu 安装检查
    try:
        output = subprocess.run(
            ["pip", "show", "torch_npu"], capture_output=True, text=True, timeout=10
        )
        if output.returncode == 0:
            result.torch_npu_installed = True
            for line in output.stdout.splitlines():
                if line.startswith("Version:"):
                    result.torch_npu_version = line.split(":", 1)[1].strip()
    except Exception:
        pass

    return result


# ========== Step 2: 模型服务部署 ==========


def generate_vllm_serve_command(config: ValidationConfig) -> str:
    """Step 2: 生成 vLLM 服务启动命令"""
    sc = config.vllm_server
    lines = []

    # 环境变量
    lines.append("export VLLM_USE_MODELSCOPE=true")
    lines.append("export PYTORCH_NPU_ALLOC_CONF=expandable_segments:True")
    lines.append("export HCCL_BUFFSIZE=512")
    lines.append("export OMP_PROC_BIND=false")
    lines.append("export OMP_NUM_THREADS=1")
    lines.append("export TASK_QUEUE_ENABLE=1")
    lines.append("")

    # vLLM 启动命令
    cmd_parts = [
        f"vllm serve {_shell_quote(config.model_path)}",
        f"--host {_shell_quote(sc.host)}",
        f"--port {_shell_quote(sc.port)}",
        f"--data-parallel-size {_shell_quote(sc.data_parallel_size)}",
        f"--tensor-parallel-size {_shell_quote(sc.tensor_parallel_size)}",
        f"--seed {_shell_quote(sc.seed)}",
        f"--max-num-seqs {_shell_quote(sc.max_num_seqs)}",
        f"--max-model-len {_shell_quote(sc.max_model_len)}",
        f"--max-num-batched-tokens {_shell_quote(sc.max_num_batched_tokens)}",
        f"--gpu-memory-utilization {_shell_quote(sc.gpu_memory_utilization)}",
    ]

    if sc.trust_remote_code:
        cmd_parts.append("--trust-remote-code")

    if not sc.enable_prefix_caching:
        cmd_parts.append("--no-enable-prefix-caching")

    if sc.quantization:
        cmd_parts.append(f"--quantization {_shell_quote(sc.quantization)}")

    if sc.served_model_name:
        cmd_parts.append(f"--served-model-name {_shell_quote(sc.served_model_name)}")

    if sc.compilation_config:
        comp_json = json.dumps(sc.compilation_config)
        cmd_parts.append(f"--compilation-config {_shell_quote(comp_json)}")

    if sc.additional_config:
        add_json = json.dumps(sc.additional_config)
        cmd_parts.append(f"--additional-config {_shell_quote(add_json)}")

    if sc.async_scheduling:
        cmd_parts.append("--async-scheduling")

    lines.append(" \\\n  ".join(cmd_parts))

    return "\n".join(lines)


def _wait_for_server(host: str, port: int, timeout: int = 300) -> bool:
    """等待 vLLM 服务器就绪"""
    import urllib.error
    import urllib.request

    url = f"http://{host}:{port}/v1/models"
    start = time.time()

    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(5)

    return False


def _kill_vllm_server() -> bool:
    """保守清理：不再全局 pkill，避免误杀非本验证任务启动的 vLLM 服务"""
    logger.warning("跳过全局 vLLM 进程清理：未持有本任务进程句柄")
    return False


# ========== Step 3: 精度验证 ==========


def run_accuracy_test(
    model_name: str,
    host: str = "0.0.0.0",
    port: int = 8000,
    timeout: int = 60,
    retries: int = 2,
) -> AccuracyResult:
    """Step 3.1: 精度验证

    通过 chat/completions API 发送测试请求，
    验证模型基本推理能力。
    """
    result = AccuracyResult(
        dataset="chat_completions",
        metric_name="response_valid",
        status=ValidationStatus.RUNNING,
    )

    import urllib.error
    import urllib.request

    url = f"http://{host}:{port}/v1/chat/completions"
    payload = json.dumps(
        {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": "Give me a short introduction to large language models.",
                }
            ],
            "temperature": 0.6,
            "top_p": 0.95,
            "top_k": 20,
            "max_completion_tokens": 4096,
        }
    ).encode("utf-8")

    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))

                if "choices" in body and len(body["choices"]) > 0:
                    content = body["choices"][0].get("message", {}).get("content", "")
                    if content and len(content) > 20:
                        result.metric_value = 1.0
                        result.status = ValidationStatus.PASSED
                        result.error = ""
                        return result
                    else:
                        result.error = "模型返回内容过短或为空"
                else:
                    result.error = "API 返回格式异常: 无 choices"

        except urllib.error.URLError as e:
            result.error = f"API 请求失败: {str(e)[:200]}"
        except Exception as e:
            result.error = f"精度测试异常: {str(e)[:200]}"

        if attempt < retries:
            time.sleep(2)

    result.status = ValidationStatus.FAILED
    return result


def run_gsm8k_evaluation(
    model_name: str,
    model_path: str,
    host: str = "0.0.0.0",
    port: int = 8000,
) -> AccuracyResult:
    """GSM8K 精度评估（使用 lm-eval-harness）"""
    result = AccuracyResult(
        dataset="gsm8k",
        metric_name="accuracy",
        status=ValidationStatus.RUNNING,
    )

    ref = GSM8K_REFERENCE.get(model_name)
    result.reference_value = ref

    vllm_url = f"http://{host}:{port}/v1"

    try:
        cmd = [
            "lm_eval",
            "--model",
            "vllm",
            "--model_args",
            f"pretrained={model_path},tensor_parallel_size=1,data_parallel_size=1,"
            f"max_model_len=8192,trust_remote_code=true,base_url={vllm_url}",
            "--tasks",
            "gsm8k",
            "--num_fewshot",
            "5",
            "--batch_size",
            "1",
        ]

        output = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if output.returncode == 0:
            # 解析 lm-eval 输出中的准确率
            acc_match = re.search(r"acc(?:uracy)?[,\s]+(\d+\.\d+)", output.stdout)
            if acc_match:
                result.metric_value = float(acc_match.group(1)) * 100
                result.status = ValidationStatus.PASSED
            else:
                result.error = "无法解析 lm-eval 输出中的准确率"
                result.status = ValidationStatus.FAILED
        else:
            result.error = f"lm-eval 执行失败: {output.stderr[:300]}"
            result.status = ValidationStatus.FAILED

    except FileNotFoundError:
        result.error = "lm_eval 未安装，请运行: pip install lm-eval"
        result.status = ValidationStatus.FAILED
    except subprocess.TimeoutExpired:
        result.error = "GSM8K 评估超时（600s）"
        result.status = ValidationStatus.FAILED
    except Exception as e:
        result.error = f"评估异常: {str(e)[:200]}"
        result.status = ValidationStatus.FAILED

    return result


# ========== Step 3.2: 性能基准测试 ==========


def run_benchmark_serve(
    model_path: str,
    benchmark: BenchmarkConfig,
    host: str = "0.0.0.0",
    port: int = 8000,
) -> PerformanceResult:
    """serve 模式: 在线吞吐测试 (QPS, TTFT, TPOT)"""
    result = PerformanceResult(mode="serve", status=ValidationStatus.RUNNING)

    cmd = [
        "vllm",
        "bench",
        "serve",
        "--model",
        model_path,
        "--dataset-name",
        benchmark.dataset_name,
        "--random-input",
        str(benchmark.input_len),
        "--num-prompts",
        str(benchmark.num_prompts),
        "--request-rate",
        str(benchmark.request_rate),
        "--save-result",
    ]

    try:
        output = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        result.raw_output = (
            output.stdout[-2000:] if len(output.stdout) > 2000 else output.stdout
        )

        if output.returncode == 0:
            # 解析关键指标
            qps_match = re.search(r"QPS[:\s]+(\d+\.?\d*)", output.stdout)
            ttft_match = re.search(r"TTFT[:\s]+(\d+\.?\d*)\s*ms", output.stdout)
            tpot_match = re.search(r"TPOT[:\s]+(\d+\.?\d*)\s*ms", output.stdout)

            result.metrics = {
                "qps": float(qps_match.group(1)) if qps_match else None,
                "ttft_ms": float(ttft_match.group(1)) if ttft_match else None,
                "tpot_ms": float(tpot_match.group(1)) if tpot_match else None,
            }
            result.status = ValidationStatus.PASSED
        else:
            result.error = f"bench serve 失败: {output.stderr[:300]}"
            result.status = ValidationStatus.FAILED

    except FileNotFoundError:
        result.error = "vllm bench 命令未找到"
        result.status = ValidationStatus.FAILED
    except subprocess.TimeoutExpired:
        result.error = "bench serve 超时（600s）"
        result.status = ValidationStatus.FAILED
    except Exception as e:
        result.error = f"bench serve 异常: {str(e)[:200]}"
        result.status = ValidationStatus.FAILED

    return result


def run_benchmark_latency(
    model_path: str,
    benchmark: BenchmarkConfig,
) -> PerformanceResult:
    """latency 模式: 单请求延迟测试 (P50/P90/P99)"""
    result = PerformanceResult(mode="latency", status=ValidationStatus.RUNNING)

    cmd = [
        "vllm",
        "bench",
        "latency",
        "--model",
        model_path,
        "--input-len",
        str(benchmark.input_len),
        "--output-len",
        str(benchmark.output_len),
        "--num-iterations",
        str(benchmark.num_iterations),
    ]

    try:
        output = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        result.raw_output = (
            output.stdout[-2000:] if len(output.stdout) > 2000 else output.stdout
        )

        if output.returncode == 0:
            p50 = re.search(r"P50[:\s]+(\d+\.?\d*)\s*ms", output.stdout)
            p90 = re.search(r"P90[:\s]+(\d+\.?\d*)\s*ms", output.stdout)
            p99 = re.search(r"P99[:\s]+(\d+\.?\d*)\s*ms", output.stdout)

            result.metrics = {
                "p50_ms": float(p50.group(1)) if p50 else None,
                "p90_ms": float(p90.group(1)) if p90 else None,
                "p99_ms": float(p99.group(1)) if p99 else None,
            }
            result.status = ValidationStatus.PASSED
        else:
            result.error = f"bench latency 失败: {output.stderr[:300]}"
            result.status = ValidationStatus.FAILED

    except FileNotFoundError:
        result.error = "vllm bench 命令未找到"
        result.status = ValidationStatus.FAILED
    except subprocess.TimeoutExpired:
        result.error = "bench latency 超时（300s）"
        result.status = ValidationStatus.FAILED
    except Exception as e:
        result.error = f"bench latency 异常: {str(e)[:200]}"
        result.status = ValidationStatus.FAILED

    return result


def run_benchmark_throughput(
    model_path: str,
    benchmark: BenchmarkConfig,
) -> PerformanceResult:
    """throughput 模式: 离线吞吐测试 (tokens/sec)"""
    result = PerformanceResult(mode="throughput", status=ValidationStatus.RUNNING)

    cmd = [
        "vllm",
        "bench",
        "throughput",
        "--model",
        model_path,
        "--input-len",
        str(benchmark.input_len),
        "--output-len",
        str(benchmark.output_len),
        "--num-batches",
        str(benchmark.num_batches),
    ]

    try:
        output = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        result.raw_output = (
            output.stdout[-2000:] if len(output.stdout) > 2000 else output.stdout
        )

        if output.returncode == 0:
            tps_match = re.search(r"(\d+\.?\d*)\s*tokens/s", output.stdout)
            if not tps_match:
                tps_match = re.search(
                    r"throughput[:\s]+(\d+\.?\d*)", output.stdout, re.IGNORECASE
                )

            result.metrics = {
                "tokens_per_sec": float(tps_match.group(1)) if tps_match else None,
            }
            result.status = ValidationStatus.PASSED
        else:
            result.error = f"bench throughput 失败: {output.stderr[:300]}"
            result.status = ValidationStatus.FAILED

    except FileNotFoundError:
        result.error = "vllm bench 命令未找到"
        result.status = ValidationStatus.FAILED
    except subprocess.TimeoutExpired:
        result.error = "bench throughput 超时（300s）"
        result.status = ValidationStatus.FAILED
    except Exception as e:
        result.error = f"bench throughput 异常: {str(e)[:200]}"
        result.status = ValidationStatus.FAILED

    return result


# ========== 完整验证流水线 ==========


class ValidationExecutor:
    """完整验证流水线执行器

    流程：
    1. 环境预检
    2. 模型服务部署
    3. 精度验证
    4. 性能基准测试
    5. 资源清理
    6. 报告生成
    """

    def __init__(self, config: ValidationConfig):
        self.config = config
        self.report = ValidationReport(
            model_name=config.model_name,
            hardware_type=config.hardware_type,
        )
        self._server_process: subprocess.Popen[bytes] | None = None

    def run(self) -> ValidationReport:
        """执行完整验证流水线"""
        start_time = datetime.now()
        self.report.start_time = start_time.isoformat()
        self._log(
            f"验证开始: model={self.config.model_name}, "
            f"hardware={self.config.hardware_type}"
        )

        try:
            # Step 1: 环境预检
            self._log("Step 1: 环境预检")
            env_result = self._step_env_check()
            if env_result.errors:
                self.report.errors.extend(env_result.errors)
                if not env_result.npu_smi_ok:
                    self._fail("环境预检失败，NPU 不可用")
                    return self._finalize(start_time)

            # Step 2: 模型服务部署
            self._log("Step 2: 模型服务部署")
            deploy_ok = self._step_deploy()
            if not deploy_ok:
                self._fail("模型服务部署失败")
                return self._finalize(start_time)

            # Step 3.1: 精度验证
            if self.config.run_accuracy_test:
                self._log("Step 3.1: 精度验证")
                self._step_accuracy()
            else:
                self._log("Step 3.1: 精度验证（跳过）")

            # Step 3.2: 性能基准测试
            if self.config.run_performance_tests:
                self._log("Step 3.2: 性能基准测试")
                self._step_performance()
            else:
                self._log("Step 3.2: 性能基准测试（跳过）")

            # 判断总体是否成功
            all_accuracy_ok = all(
                r.status == ValidationStatus.PASSED
                for r in self.report.accuracy_results
            )
            all_perf_ok = all(
                r.status == ValidationStatus.PASSED
                for r in self.report.performance_results
            )
            self.report.success = all_accuracy_ok and all_perf_ok

        except Exception as e:
            self._fail(f"验证流水线异常: {str(e)}")

        finally:
            # Step 4: 资源清理
            self._log("Step 4: 资源清理")
            self._step_cleanup()

            # Step 5: 报告生成
            self._log("Step 5: 报告生成")
            self._step_generate_report()

        return self._finalize(start_time)

    def _log(self, msg: str) -> None:
        """记录日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {msg}"
        self.report.logs.append(log_line)
        logger.info(log_line)

    def _fail(self, reason: str) -> None:
        """标记失败"""
        self.report.success = False
        self.report.errors.append(reason)
        self._log(f"失败: {reason}")

    def _finalize(self, start_time: datetime) -> ValidationReport:
        """完成验证"""
        end_time = datetime.now()
        self.report.end_time = end_time.isoformat()
        self.report.duration_seconds = (end_time - start_time).total_seconds()
        return self.report

    # --- Step 1: 环境预检 ---
    def _step_env_check(self) -> EnvironmentCheckResult:
        result = run_environment_check()
        self.report.environment_check = result
        self._log(
            f"环境检查完成: npu_smi={result.npu_smi_ok}, "
            f"vllm={result.vllm_installed}, "
            f"torch_npu={result.torch_npu_installed}"
        )
        return result

    # --- Step 2: 模型服务部署 ---
    def _step_deploy(self) -> bool:
        sc = self.config.vllm_server
        serve_cmd = generate_vllm_serve_command(self.config)
        self._log(f"启动命令:\n{serve_cmd}")

        try:
            # 启动 vLLM 服务
            env = os.environ.copy()
            env["VLLM_USE_MODELSCOPE"] = "true"
            env["PYTORCH_NPU_ALLOC_CONF"] = "expandable_segments:True"
            env["HCCL_BUFFSIZE"] = "512"
            env["OMP_PROC_BIND"] = "false"
            env["OMP_NUM_THREADS"] = "1"
            env["TASK_QUEUE_ENABLE"] = "1"

            cmd_parts = shlex.split(serve_cmd.split("\n")[-1].replace("\\\n  ", " "))
            # start_new_session=True 创建新进程组，中断时可通过 kill 整组避免孤儿进程
            self._server_process = subprocess.Popen(
                cmd_parts,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )

            # 等待服务就绪
            self._log(
                f"等待服务就绪 (timeout={self.config.server_startup_timeout}s)..."
            )
            ready = _wait_for_server(
                sc.host, sc.port, timeout=self.config.server_startup_timeout
            )

            if ready:
                self.report.deploy_status = ValidationStatus.PASSED
                self._log(f"服务就绪: http://{sc.host}:{sc.port}")
                return True
            else:
                self.report.deploy_status = ValidationStatus.FAILED
                # 读取 stderr 用于诊断
                stderr_output = ""
                if self._server_process and self._server_process.stderr:
                    try:
                        stderr_output = self._server_process.stderr.read(2000).decode(
                            "utf-8", errors="replace"
                        )
                    except Exception:
                        pass
                self._log(f"服务启动失败。stderr: {stderr_output[:500]}")
                return False

        except Exception as e:
            self.report.deploy_status = ValidationStatus.ERROR
            self._log(f"部署异常: {str(e)}")
            return False

    # --- Step 3.1: 精度验证 ---
    def _step_accuracy(self) -> None:
        sc = self.config.vllm_server
        model_id = sc.served_model_name or self.config.model_name

        # 基本 chat completions 验证
        acc_result = run_accuracy_test(
            model_name=model_id,
            host=sc.host,
            port=sc.port,
            timeout=self.config.api_timeout,
            retries=self.config.api_retries,
        )
        self.report.accuracy_results.append(acc_result)
        self._log(
            f"精度验证: status={acc_result.status.value}, "
            f"value={acc_result.metric_value}"
        )

        # GSM8K 评估（可选，需要 lm-eval-harness）
        if self.config.model_name in GSM8K_REFERENCE:
            self._log("执行 GSM8K 评估...")
            gsm8k_result = run_gsm8k_evaluation(
                model_name=self.config.model_name,
                model_path=self.config.model_path,
                host=sc.host,
                port=sc.port,
            )
            self.report.accuracy_results.append(gsm8k_result)
            self._log(
                "GSM8K: accuracy={:.2f}% (参考值: {})".format(
                    gsm8k_result.metric_value, gsm8k_result.reference_value or "N/A"
                )
            )

    # --- Step 3.2: 性能基准测试 ---
    def _step_performance(self) -> None:
        for mode in self.config.run_performance_tests:
            self._log(f"执行性能测试: {mode}")

            if mode == "serve":
                result = run_benchmark_serve(
                    self.config.model_path,
                    self.config.benchmark,
                    self.config.vllm_server.host,
                    self.config.vllm_server.port,
                )
            elif mode == "latency":
                result = run_benchmark_latency(
                    self.config.model_path,
                    self.config.benchmark,
                )
            elif mode == "throughput":
                result = run_benchmark_throughput(
                    self.config.model_path,
                    self.config.benchmark,
                )
            else:
                self._log(f"未知性能测试模式: {mode}")
                continue

            self.report.performance_results.append(result)
            self._log(f"性能测试 {mode} 完成: status={result.status.value}")

    # --- Step 4: 资源清理 ---
    def _step_cleanup(self) -> None:
        # 停止 vLLM 服务进程（按进程组终止，避免孤儿子进程）
        if self._server_process:
            if sys.platform == "win32":
                # Windows 无进程组语义（getpgid/killpg 为 POSIX-only）
                self._server_process.terminate()
                try:
                    self._server_process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    self._server_process.kill()
                self._log("vLLM 服务已停止")
            else:
                try:
                    import signal as _signal

                    # 优先向整个进程组发送 SIGTERM
                    try:
                        os.killpg(os.getpgid(self._server_process.pid), _signal.SIGTERM)
                    except (ProcessLookupError, PermissionError):
                        self._server_process.terminate()
                    self._server_process.wait(timeout=30)
                    self._log("vLLM 服务已停止")
                except Exception:
                    try:
                        import signal as _signal

                        try:
                            os.killpg(
                                os.getpgid(self._server_process.pid),
                                _signal.SIGKILL,
                            )
                        except (ProcessLookupError, PermissionError):
                            self._server_process.kill()
                        self._log("vLLM 服务已强制终止")
                    except Exception:
                        pass

        # 额外清理残留进程
        _kill_vllm_server()
        self._log("资源清理完成")

    # --- Step 5: 报告生成 ---
    def _step_generate_report(self) -> None:
        report_dir = Path(self.config.report_output_dir)
        report_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r"[^\w\-.]", "_", self.config.model_name)
        report_path = report_dir / f"validation_{safe_name}_{timestamp}.json"

        report_data = self.report.to_dict()

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        self.report.report_path = str(report_path)
        self._log(f"报告已生成: {report_path}")


# ========== 便捷函数 ==========


def run_validation(config: ValidationConfig) -> ValidationReport:
    """一键执行完整验证流水线"""
    executor = ValidationExecutor(config)
    return executor.run()


def get_preset_config(model_name: str) -> ValidationConfig | None:
    """获取预设模型配置"""
    presets = {
        "Qwen3.5-27B": QWEN35_27B_PRESET,
        "Qwen3.5-27B-w8a8": QWEN35_27B_PRESET,
    }
    return presets.get(model_name)


def list_supported_models() -> list[dict[str, Any]]:
    """列出支持的模型"""
    return [
        {
            "model_name": "Qwen3.5-27B-w8a8",
            "hardware": "Atlas 800 A2",
            "tp_size": 2,
            "max_model_len": 133000,
            "quantized": True,
            "gsm8k_reference": 96.74,
        },
    ]

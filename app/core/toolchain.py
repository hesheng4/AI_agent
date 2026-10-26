"""昇腾 NPU 推理工具链模块

覆盖 vLLM-Ascend 安装/运行、msmodelslim 量化、
敏感度分析、AISBench 评测等完整推理工具链。

遵循 quantify-agent skill 规范：
- 启动前先执行 npu-smi info 硬件检查
- 设置必要环境变量 (VLLM_WORKER_MULTIPROC_METHOD 等)
- 支持硬件诊断、安装引导、运行排障、量化流程、评测验证
"""

import json
import logging
import os
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("ascend_toolchain")


def _shell_quote(value: object) -> str:
    return shlex.quote(str(value))


def _py_literal(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


# ========== 路径安全校验 ==========

# 路径中禁止出现的字符：防止 shell 注入与路径遍历
_UNSAFE_PATH_CHARS = re.compile(r"[`;|$&!<>\n\r]")


def validate_path_safety(path: str, field_name: str = "path") -> str:
    """校验用户输入的路径是否安全

    - 禁止 shell 元字符（防注入）
    - 禁止空字节
    - 警告路径遍历（..）但不强制拒绝（合法场景可能用到）
    """
    if not path:
        raise ValueError(f"{field_name} 不能为空")
    if not isinstance(path, str):
        raise ValueError(f"{field_name} 必须是字符串")
    if "\x00" in path:
        raise ValueError(f"{field_name} 包含空字节")
    if _UNSAFE_PATH_CHARS.search(path):
        raise ValueError(f"{field_name} 包含禁止字符: {path!r}")
    if ".." in path.split(os.sep) or ".." in path.split("/"):
        logger.warning(f"{field_name} 包含路径遍历符 '..': {path!r}，请确认路径合法")
    return path


# ========== 枚举与数据结构 ==========


class NPUHealthStatus(Enum):
    """NPU 健康状态"""

    OK = "OK"
    WARNING = "WARNING"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"


class QuantizationFormat(Enum):
    """量化格式"""

    FP16 = "fp16"
    BF16 = "bf16"
    W8A8 = "w8a8"
    W4A16 = "w4a16"
    W8A16 = "w8a16"


class ModelArchitecture(Enum):
    """模型架构"""

    DENSE = "dense"
    MOE = "moe"


@dataclass
class NPUDeviceInfo:
    """单个 NPU 设备信息"""

    index: int
    name: str = ""
    health: NPUHealthStatus = NPUHealthStatus.UNKNOWN
    memory_total_mb: int = 0
    memory_used_mb: int = 0
    temperature: float = 0.0
    process_ids: list[str] = field(default_factory=list)
    power_usage: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "name": self.name,
            "health": self.health.value,
            "memory_total_mb": self.memory_total_mb,
            "memory_used_mb": self.memory_used_mb,
            "memory_free_mb": self.memory_total_mb - self.memory_used_mb,
            "temperature": self.temperature,
            "process_ids": self.process_ids,
            "power_usage": self.power_usage,
        }


@dataclass
class HardwareCheckResult:
    """硬件检查结果"""

    success: bool = False
    device_count: int = 0
    devices: list[NPUDeviceInfo] = field(default_factory=list)
    cann_version: str = ""
    driver_version: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "device_count": self.device_count,
            "devices": [d.to_dict() for d in self.devices],
            "cann_version": self.cann_version,
            "driver_version": self.driver_version,
            "errors": self.errors,
            "warnings": self.warnings,
        }


@dataclass
class VLLMInstallGuide:
    """vLLM-Ascend 安装指引"""

    pip_install: str = ""
    source_install: str = ""
    prerequisites: list[str] = field(default_factory=list)
    env_setup: list[str] = field(default_factory=list)
    verification: str = ""
    common_issues: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pip_install": self.pip_install,
            "source_install": self.source_install,
            "prerequisites": self.prerequisites,
            "env_setup": self.env_setup,
            "verification": self.verification,
            "common_issues": self.common_issues,
        }


@dataclass
class VLLMRunConfig:
    """vLLM-Ascend 运行配置"""

    model: str = ""
    tp_size: int = 1
    ep_size: int = 0
    dp_size: int = 1
    max_model_len: int = 8192
    quantization: str | None = None
    enable_chunked_prefill: bool = False
    enable_prefix_caching: bool = False
    gpu_memory_utilization: float = 0.9
    max_num_seqs: int = 256
    port: int = 8001
    extra_args: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "tp_size": self.tp_size,
            "ep_size": self.ep_size,
            "dp_size": self.dp_size,
            "max_model_len": self.max_model_len,
            "quantization": self.quantization,
            "enable_chunked_prefill": self.enable_chunked_prefill,
            "enable_prefix_caching": self.enable_prefix_caching,
            "gpu_memory_utilization": self.gpu_memory_utilization,
            "max_num_seqs": self.max_num_seqs,
            "port": self.port,
            "extra_args": self.extra_args,
        }


@dataclass
class QuantizationConfig:
    """msmodelslim 量化配置"""

    model_path: str = ""
    output_path: str = ""
    format: QuantizationFormat = QuantizationFormat.W8A8
    dataset: str = "random"
    num_samples: int = 128
    seq_length: int = 2048
    batch_size: int = 1
    anti_overflow: bool = True
    w16a16_ref: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_path": self.model_path,
            "output_path": self.output_path,
            "format": self.format.value,
            "dataset": self.dataset,
            "num_samples": self.num_samples,
            "seq_length": self.seq_length,
            "batch_size": self.batch_size,
            "anti_overflow": self.anti_overflow,
            "w16a16_ref": self.w16a16_ref,
        }


@dataclass
class SensitivityLayerResult:
    """敏感度分析单层结果"""

    layer_name: str
    baseline_loss: float = 0.0
    quantized_loss: float = 0.0
    loss_diff: float = 0.0
    loss_diff_pct: float = 0.0
    is_sensitive: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer_name": self.layer_name,
            "baseline_loss": self.baseline_loss,
            "quantized_loss": self.quantized_loss,
            "loss_diff": self.loss_diff,
            "loss_diff_pct": self.loss_diff_pct,
            "is_sensitive": self.is_sensitive,
        }


@dataclass
class AISBenchConfig:
    """AISBench 评测配置"""

    model_name: str = ""
    benchmark: str = "gsm8k"
    num_fewshot: int = 5
    batch_size: int = 1
    max_tokens: int = 1024
    temperature: float = 0.0
    vllm_url: str = "http://127.0.0.1:8001/v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "benchmark": self.benchmark,
            "num_fewshot": self.num_fewshot,
            "batch_size": self.batch_size,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "vllm_url": self.vllm_url,
        }


# ========== 硬件检查 ==========


def check_npu_hardware() -> HardwareCheckResult:
    """执行 NPU 硬件检查

    遵循 quantify-agent skill 规范：在每次量化或推理任务开始前，
    先运行 npu-smi info 确认所有 NPU 健康。
    """
    result = HardwareCheckResult()

    try:
        output = subprocess.run(
            ["npu-smi", "info"], capture_output=True, text=True, timeout=30
        )
        if output.returncode != 0:
            result.errors.append(f"npu-smi info 失败: {output.stderr}")
            return result

        result.success = True
        lines = output.stdout.splitlines()

        # 解析 NPU 设备信息
        current_device = None
        for line in lines:
            line_stripped = line.strip()

            # 匹配设备索引
            dev_match = re.match(r"NPU\s+(\d+)", line_stripped)
            if dev_match:
                idx = int(dev_match.group(1))
                current_device = NPUDeviceInfo(index=idx)
                result.devices.append(current_device)
                continue

            if current_device is None:
                continue

            # 健康状态
            if "Health" in line_stripped:
                if "OK" in line_stripped or "Normal" in line_stripped:
                    current_device.health = NPUHealthStatus.OK
                elif "Warning" in line_stripped or "Alarm" in line_stripped:
                    current_device.health = NPUHealthStatus.WARNING
                    result.warnings.append(
                        f"NPU {current_device.index} 健康状态异常: {line_stripped}"
                    )
                else:
                    current_device.health = NPUHealthStatus.ERROR
                    result.errors.append(
                        f"NPU {current_device.index} 健康状态错误: {line_stripped}"
                    )

            # 显存信息
            if "HBM" in line_stripped or "Memory" in line_stripped:
                mem_match = re.search(r"(\d+)\s*/\s*(\d+)\s*MiB", line_stripped)
                if mem_match:
                    current_device.memory_used_mb = int(mem_match.group(1))
                    current_device.memory_total_mb = int(mem_match.group(2))

            # 温度
            if "Temperature" in line_stripped or "Temp" in line_stripped:
                temp_match = re.search(r"(\d+\.?\d*)\s*°?C", line_stripped)
                if temp_match:
                    current_device.temperature = float(temp_match.group(1))

            # 进程 ID
            if "Process" in line_stripped and "ID" in line_stripped:
                pid_match = re.findall(r"\d+", line_stripped.split("Process")[-1])
                current_device.process_ids = pid_match

            # 功耗
            if "Power" in line_stripped:
                power_match = re.search(r"(\d+\.?\d*)\s*W", line_stripped)
                if power_match:
                    current_device.power_usage = float(power_match.group(1))

        result.device_count = len(result.devices)

        # 健康检查汇总
        for dev in result.devices:
            if dev.health != NPUHealthStatus.OK:
                result.success = False
                result.errors.append(
                    f"NPU {dev.index} 健康状态: {dev.health.value}，"
                    f"请检查设备或联系运维"
                )

            if dev.process_ids:
                result.warnings.append(
                    f"NPU {dev.index} 上有运行中的进程: {dev.process_ids}，"
                    f"确认非本任务进程后可考虑清理"
                )

    except FileNotFoundError:
        result.errors.append(
            "npu-smi 命令未找到。请确认 CANN toolkit 已安装并添加到 PATH: "
            "source /usr/local/Ascend/ascend-toolkit/set_env.sh"
        )
    except subprocess.TimeoutExpired:
        result.errors.append("npu-smi info 执行超时（30s），NPU 驱动可能异常")
    except Exception as e:
        result.errors.append(f"硬件检查异常: {str(e)}")

    return result


def get_common_env_setup(device_ids: str = "0,1,2,3") -> dict[str, str]:
    """获取推荐的公共环境变量

    遵循 quantify-agent skill 规范：
    - VLLM_WORKER_MULTIPROC_METHOD=spawn: vLLM 多进程支持
    - VLLM_USE_MODELSCOPE=true: 国内推荐用 ModelScope 下载
    - ASCEND_RT_VISIBLE_DEVICES: 控制 NPU 可见性
    """
    return {
        "VLLM_WORKER_MULTIPROC_METHOD": "spawn",
        "VLLM_USE_MODELSCOPE": "true",
        "ASCEND_RT_VISIBLE_DEVICES": device_ids,
    }


# ========== vLLM-Ascend 安装 ==========


def get_vllm_install_guide() -> VLLMInstallGuide:
    """获取 vLLM-Ascend 安装指引"""
    guide = VLLMInstallGuide()

    guide.prerequisites = [
        "Ascend CANN Toolkit 8.0+ 已安装",
        "Ascend NPU Driver 已安装",
        "Python 3.8 - 3.12",
        "PyTorch 2.1.0+ 已安装",
        "torch_npu 已安装并与 PyTorch 版本匹配",
    ]

    guide.pip_install = (
        "pip install vllm-ascend\n# 或者安装特定版本\n# pip install vllm-ascend==0.6.0"
    )

    guide.source_install = (
        "# 从源码安装（开发/调试用）\n"
        "git clone https://github.com/vllm-project/vllm-ascend.git\n"
        "cd vllm-ascend\n"
        "pip install -e .\n"
        "# 可选：安装开发依赖\n"
        "# pip install -e '.[dev]'"
    )

    guide.env_setup = [
        "# CANN 环境变量（必须）",
        "source /usr/local/Ascend/ascend-toolkit/set_env.sh",
        "",
        "# vLLM 多进程支持",
        "export VLLM_WORKER_MULTIPROC_METHOD=spawn",
        "",
        "# 使用 ModelScope 下载（推荐国内用户）",
        "export VLLM_USE_MODELSCOPE=true",
        "",
        "# 可见 NPU 设备",
        "export ASCEND_RT_VISIBLE_DEVICES=0,1,2,3",
        "",
        "# 性能优化",
        "export TASK_QUEUE_ENABLE=2",
        "export PYTORCH_NPU_ALLOC_CONF=expandable_segments",
        "export ASCEND_ENABLE_ACL_GRAPH=1",
    ]

    guide.verification = (
        "# 验证 vLLM-Ascend 安装\n"
        'python -c "import vllm_ascend; print(vllm_ascend.__version__)"\n'
        "\n"
        "# 验证 torch_npu\n"
        'python -c "import torch_npu; print(torch_npu.__version__)"\n'
        "\n"
        # 修复历史缺陷：原代码 "# 验证 NPU 可见性\n"("python -c ...") 把
        # 字符串当函数调用，运行到本函数必抛 TypeError: 'str' object is
        # not callable。本意为相邻字符串拼接（隐式续行）。
        "# 验证 NPU 可见性\n"
        'python -c "import torch; print(f\'NPU 可用: '
        "{torch.npu.is_available()}, 设备数: {torch.npu.device_count()}')\"\n"
    )

    guide.common_issues = [
        {
            "issue": "ImportError: No module named 'torch_npu'",
            "solution": "安装 torch_npu: pip install torch_npu，版本需与 PyTorch 匹配",
        },
        {
            "issue": "RuntimeError: No NPU devices are available",
            "solution": (
                "检查 ASCEND_RT_VISIBLE_DEVICES 设置，运行 npu-smi info 确认设备状态"
            ),
        },
        {
            "issue": "vLLM 启动后 worker 崩溃",
            "solution": (
                "确保 VLLM_WORKER_MULTIPROC_METHOD=spawn，检查 NPU 显存是否足够"
            ),
        },
        {
            "issue": "HCCL 初始化失败",
            "solution": (
                "检查 HCCL 连接: export HCCL_CONNECT_TIMEOUT=7200，确认所有 NPU 可互通"
            ),
        },
        {
            "issue": "OOM (Out of Memory)",
            "solution": (
                "减小 max_model_len，降低 gpu_memory_utilization，或增大 TP 并行度"
            ),
        },
        {
            "issue": "模型下载超时",
            "solution": (
                "设置 VLLM_USE_MODELSCOPE=true 使用国内镜像，或手动下载后指定本地路径"
            ),
        },
    ]

    return guide


# ========== vLLM-Ascend 运行 ==========


def generate_vllm_launch_command(config: VLLMRunConfig) -> str:
    """生成 vLLM-Ascend 启动命令

    包含必要的环境变量和优化参数。
    """
    parts = []

    # CANN 环境
    parts.append("source /usr/local/Ascend/ascend-toolkit/set_env.sh")

    # 公共环境变量
    parts.append("export VLLM_WORKER_MULTIPROC_METHOD=spawn")
    parts.append(
        "export ASCEND_RT_VISIBLE_DEVICES="
        f"{_get_visible_devices(config.tp_size, config.ep_size)}"
    )

    # 性能优化
    parts.append("export TASK_QUEUE_ENABLE=2")
    parts.append("export PYTORCH_NPU_ALLOC_CONF=expandable_segments")
    parts.append("export ASCEND_ENABLE_ACL_GRAPH=1")

    # vLLM 启动命令（动态参数统一 shell quote，防止生成命令被注入/破坏）
    cmd_parts = [
        "python -m vllm.entrypoints.openai.api_server",
        f"--model {_shell_quote(config.model)}",
        f"--tensor-parallel-size {_shell_quote(config.tp_size)}",
        f"--max-model-len {_shell_quote(config.max_model_len)}",
        f"--port {_shell_quote(config.port)}",
        f"--gpu-memory-utilization {_shell_quote(config.gpu_memory_utilization)}",
        f"--max-num-seqs {_shell_quote(config.max_num_seqs)}",
        "--device npu",
    ]

    if config.quantization:
        cmd_parts.append(f"--quantization {_shell_quote(config.quantization)}")

    if config.enable_chunked_prefill:
        cmd_parts.append("--enable-chunked-prefill")

    if config.enable_prefix_caching:
        cmd_parts.append("--enable-prefix-caching")

    if config.ep_size > 0:
        cmd_parts.append(f"--expert-parallel-size {_shell_quote(config.ep_size)}")

    # 额外参数（校验 key 格式防止注入）
    _SAFE_ARG_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*$")  # noqa: N806
    for k, v in config.extra_args.items():
        if not isinstance(k, str) or not _SAFE_ARG_RE.match(k):
            logger.warning("extra_args 中跳过非法 key: %r", k)
            continue
        if isinstance(v, bool) and v:
            cmd_parts.append(f"--{k}")
        elif isinstance(v, (str, int, float)):
            cmd_parts.append(f"--{k} {_shell_quote(v)}")
        else:
            logger.warning(
                "extra_args 中跳过不支持的 value 类型: key=%r, type=%s",
                k,
                type(v).__name__,
            )

    parts.append(" \\\n  ".join(cmd_parts))

    return "\n".join(parts)


def _get_visible_devices(tp_size: int, ep_size: int = 0) -> str:
    """根据并行度计算可见 NPU 设备"""
    total = max(tp_size, tp_size * max(ep_size, 1))
    return ",".join(str(i) for i in range(total))


def diagnose_vllm_error(error_output: str) -> list[dict[str, str]]:
    """诊断 vLLM-Ascend 运行错误

    匹配常见错误模式，返回诊断结果和修复建议。
    """
    diagnoses = []

    patterns = [
        (
            r"OOM|out of memory|OutOfMemoryError",
            "显存不足 (OOM)",
            "1. 减小 --max-model-len\n"
            "2. 降低 --gpu-memory-utilization（默认 0.9）\n"
            "3. 增大 --tensor-parallel-size 使用更多 NPU\n"
            "4. 使用量化模型（w8a8/w4a16）",
        ),
        (
            r"HCCL|hccl_init|rank_id",
            "HCCL 通信初始化失败",
            "1. 检查 NPU 间网络连通性\n"
            "2. 设置 export HCCL_CONNECT_TIMEOUT=7200\n"
            "3. 检查 HCCL_BUFFERSIZE 设置\n"
            "4. 确认所有 NPU 设备正常: npu-smi info",
        ),
        (
            r"torch_npu|ImportError.*torch_npu",
            "torch_npu 模块问题",
            "1. 确认 torch_npu 已安装: pip show torch_npu\n"
            "2. 版本需与 PyTorch 匹配\n"
            "3. 运行 source /usr/local/Ascend/ascend-toolkit/set_env.sh",
        ),
        (
            r"CANN|cann_version|ascend-toolkit",
            "CANN 环境问题",
            "1. 确认 CANN Toolkit 已安装\n"
            "2. source /usr/local/Ascend/ascend-toolkit/set_env.sh\n"
            "3. 检查 CANN 版本与 torch_npu 兼容性",
        ),
        (
            r"worker.*crash|worker.*died|RuntimeError.*NPU",
            "vLLM Worker 崩溃",
            "1. 确认 VLLM_WORKER_MULTIPROC_METHOD=spawn\n"
            "2. 检查 NPU 显存是否充足\n"
            "3. 检查 NPU 健康状态: npu-smi info\n"
            "4. 查看详细日志: export VLLM_LOGGING_LEVEL=DEBUG",
        ),
        (
            r"safetensors|model.*load|checkpoint",
            "模型加载失败",
            "1. 确认模型路径正确\n"
            "2. 设置 VLLM_USE_MODELSCOPE=true 重新下载\n"
            "3. 检查磁盘空间和文件完整性\n"
            "4. 如使用量化模型，确认量化格式正确",
        ),
        (
            r"timeout|TimeoutError|timed out",
            "请求超时",
            "1. 增大 ASCEND_VLLM_TIMEOUT 设置\n"
            "2. 检查 NPU 是否正常运行\n"
            "3. 首次推理较慢（编译缓存），后续会加速\n"
            "4. 考虑调用 /api/v1/ascend/warmup 预热",
        ),
    ]

    for pattern, issue, solution in patterns:
        if re.search(pattern, error_output, re.IGNORECASE):
            diagnoses.append(
                {
                    "issue": issue,
                    "solution": solution,
                    "matched_pattern": pattern,
                }
            )

    if not diagnoses:
        diagnoses.append(
            {
                "issue": "未知错误",
                "solution": (
                    "1. 查看完整日志输出\n"
                    "2. 运行 npu-smi info 检查硬件状态\n"
                    "3. 确认环境变量已正确设置\n"
                    "4. 尝试最小化复现: 单卡运行简单模型"
                ),
            }
        )

    return diagnoses


# ========== msmodelslim 量化 ==========


def generate_quantization_script(config: QuantizationConfig) -> str:
    """生成 msmodelslim 量化脚本"""
    # 校验用户输入路径，防止注入与遍历
    validate_path_safety(config.model_path, "config.model_path")
    validate_path_safety(config.output_path, "config.output_path")
    env_setup = [
        "source /usr/local/Ascend/ascend-toolkit/set_env.sh",
        "export ASCEND_RT_VISIBLE_DEVICES=0",
    ]

    quant_type_map = {
        QuantizationFormat.W8A8: "W8A8",
        QuantizationFormat.W4A16: "W4A16",
        QuantizationFormat.W8A16: "W8A16",
    }
    quant_type_map.get(config.format, "W8A8")

    # 构建量化 Python 代码
    python_code = [
        "import torch",
        "from msmodelslim.pytorch.llm_ptq.llm_ptq_tools import Calibrator, QuantConfig",
        "",
        f"model_path = {_py_literal(config.model_path)}",
        f"output_path = {_py_literal(config.output_path)}",
        "",
        "# 量化配置",
        "quant_config = QuantConfig(",
        "    w_bit=8,",
        "    disable_names=[],",
        '    dev_type="npu",',
        "    act_method=1,",
        "    pr=1.0,",
        f"    w16a16_ref={str(config.w16a16_ref).lower()},",
        ")",
        "",
        "# 创建校准器",
        "calibrator = Calibrator(",
        "    quant_config,",
        "    model_path,",
        "    torch.npu.current_device(),",
        f"    dataset={_py_literal(config.dataset)},",
        f"    num_samples={config.num_samples},",
        f"    seq_length={config.seq_length},",
        f"    batch_size={config.batch_size},",
        ")",
        "",
        "# 执行量化",
        "calibrator.run()",
        "calibrator.save(output_path)",
        "",
        'print(f"量化完成，输出路径: {output_path}")',
    ]

    script_lines = env_setup
    script_lines.append("")
    script_lines.append("python3 << 'EOF'")
    script_lines.extend(python_code)
    script_lines.append("EOF")

    return "\n".join(script_lines)


def generate_sensitivity_script(
    model_path: str,
    output_dir: str = "./sensitivity_results",
    quant_format: str = "w8a8",
) -> str:
    """生成敏感度分析脚本

    Args:
        model_path: 模型路径（会做安全校验）
        output_dir: 输出目录
        quant_format: 量化格式
    """
    validate_path_safety(model_path, "model_path")
    validate_path_safety(output_dir, "output_dir")

    lines = [
        "#!/usr/bin/env python3",
        '"""模型量化敏感度分析脚本',
        "",
        "逐层分析量化对每层 loss 的影响，找出敏感层。",
        "敏感层建议保持 FP16 精度，其余层可安全量化。",
        '"""',
        "",
        "import torch",
        "import json",
        "import os",
        "from msmodelslim.pytorch.llm_ptq.llm_ptq_tools import Calibrator, QuantConfig",
        "",
        f"MODEL_PATH = {_py_literal(model_path)}",
        f"OUTPUT_DIR = {_py_literal(output_dir)}",
        f"QUANT_FORMAT = {_py_literal(quant_format)}",
        "",
        "os.makedirs(OUTPUT_DIR, exist_ok=True)",
        "",
        "",
        "def run_sensitivity_analysis():",
        '    """运行敏感度分析"""',
        "    results = []",
        "",
        "    # 1. 获取基线 loss（FP16）",
        '    print("=== 获取 FP16 基线 ===")',
        "    # TODO: 在实际校准数据集上计算基线 loss",
        "    # baseline_loss = compute_model_loss(MODEL_PATH, dataset)",
        "",
        "    # 2. 逐层量化，计算 loss 变化",
        '    print("=== 逐层敏感度分析 ===")',
        "    # TODO: 对每层单独量化，计算量化后的 loss",
        "    # for layer_name in model_layers:",
        "    #     quantized_loss = compute_loss_with_layer_quantized(layer_name)",
        "    #     diff = abs(quantized_loss - baseline_loss) / baseline_loss * 100",
        "    #     is_sensitive = diff > SENSITIVITY_THRESHOLD",
        "    #     results.append(...)",
        "",
        "    # 3. 保存结果",
        '    output_path = os.path.join(OUTPUT_DIR, "sensitivity_results.json")',
        '    with open(output_path, "w") as f:',
        "        json.dump(results, f, indent=2, ensure_ascii=False)",
        "",
        "    # 4. 生成建议",
        '    sensitive_layers = [r for r in results if r.get("is_sensitive")]',
        '    print(f"\\n敏感层数量: {len(sensitive_layers)} / {len(results)}")',
        '    print(f"建议在量化时跳过以下层:")',
        "    for layer in sensitive_layers:",
        (
            '        print(f"  - {layer["layer_name"]} '
            '(loss 差异: {layer["loss_diff_pct"]:.2f}%)")'
        ),
        "",
        "    return results",
        "",
        "",
        'if __name__ == "__main__":',
        "    run_sensitivity_analysis()",
    ]

    return "\n".join(lines)


# ========== AISBench 评测 ==========


def generate_aisbench_script(config: AISBenchConfig) -> str:
    """生成 AISBench 评测脚本"""
    lines = [
        "#!/usr/bin/env python3",
        '"""AISBench 评测脚本',
        "",
        f"评测模型: {config.model_name}",
        f"评测基准: {config.benchmark}",
        "需要 vLLM 服务已启动。",
        '"""',
        "",
        "import subprocess",
        "import sys",
        "",
        "# 确保 lm-eval 已安装",
        "try:",
        "    import lm_eval",
        "except ImportError:",
        '    print("安装 lm-eval-harness...")',
        (
            '    subprocess.check_call([sys.executable, "-m", "pip", '
            '"install", "lm-eval"])'
        ),
        "",
        "# 运行评测",
        "cmd = [",
        '    "lm_eval",',
        '    "--model", "vllm",',
        f'    "--model_args", "pretrained={config.model_name},'
        f"tensor_parallel_size=1,"
        f"data_parallel_size=1,"
        f"max_model_len=8192,"
        f"trust_remote_code=true,"
        f'base_url={config.vllm_url}",',
        f'    "--tasks", "{config.benchmark}",',
        f'    "--num_fewshot", "{config.num_fewshot}",',
        f'    "--batch_size", "{config.batch_size}",',
        f'    "--max_tokens", "{config.max_tokens}",',
        "]",
        "",
        'print(f"运行评测: {\\" \\".join(cmd)}")',
        "result = subprocess.run(cmd, capture_output=True, text=True)",
        "",
        "if result.returncode == 0:",
        "    print(result.stdout)",
        "else:",
        '    print(f"评测失败: {result.stderr}")',
    ]

    return "\n".join(lines)


# ========== 环境验证 ==========


def verify_ascend_environment() -> dict[str, Any]:
    """验证完整的昇腾推理环境"""
    checks: dict[str, Any] = {
        "cann_toolkit": {"installed": False, "version": "", "path": ""},
        "npu_driver": {"installed": False, "version": ""},
        "torch_npu": {"installed": False, "version": ""},
        "vllm_ascend": {"installed": False, "version": ""},
        "msmodelslim": {"installed": False, "version": ""},
        "env_vars": {},
        "npu_devices": {"count": 0, "details": []},
        "warnings": [],
        "errors": [],
    }

    # CANN Toolkit
    cann_path = os.environ.get("ASCEND_HOME_PATH", "")
    if cann_path and os.path.exists(cann_path):
        checks["cann_toolkit"]["installed"] = True
        checks["cann_toolkit"]["path"] = cann_path

    # NPU Driver
    try:
        output = subprocess.run(
            ["npu-smi", "--version"], capture_output=True, text=True, timeout=10
        )
        if output.returncode == 0:
            checks["npu_driver"]["installed"] = True
            checks["npu_driver"]["version"] = output.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # Python packages
    for pkg_name, check_key in [
        ("torch_npu", "torch_npu"),
        ("vllm_ascend", "vllm_ascend"),
        ("msmodelslim", "msmodelslim"),
    ]:
        try:
            output = subprocess.run(
                ["pip", "show", pkg_name], capture_output=True, text=True, timeout=10
            )
            if output.returncode == 0:
                checks[check_key]["installed"] = True
                for line in output.stdout.splitlines():
                    if line.startswith("Version:"):
                        checks[check_key]["version"] = line.split(":", 1)[1].strip()
                    if line.startswith("Location:"):
                        checks[check_key]["location"] = line.split(":", 1)[1].strip()
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass

    # 关键环境变量
    env_var_keys = [
        "ASCEND_RT_VISIBLE_DEVICES",
        "VLLM_WORKER_MULTIPROC_METHOD",
        "VLLM_USE_MODELSCOPE",
        "TASK_QUEUE_ENABLE",
        "PYTORCH_NPU_ALLOC_CONF",
        "ASCEND_ENABLE_ACL_GRAPH",
        "LD_PRELOAD",
        "HCCL_CONNECT_TIMEOUT",
    ]
    for key in env_var_keys:
        checks["env_vars"][key] = os.environ.get(key, "(未设置)")

    # NPU 设备
    hw = check_npu_hardware()
    checks["npu_devices"]["count"] = hw.device_count
    checks["npu_devices"]["details"] = [d.to_dict() for d in hw.devices]
    checks["warnings"].extend(hw.warnings)
    checks["errors"].extend(hw.errors)

    return checks


def get_recommended_vllm_config(
    model_name: str,
    npu_count: int = 4,
    model_arch: ModelArchitecture = ModelArchitecture.DENSE,
    quant_format: QuantizationFormat | None = None,
) -> VLLMRunConfig:
    """根据模型和硬件生成推荐的 vLLM 运行配置"""
    config = VLLMRunConfig(model=model_name)

    # TP 并行度
    model_size_hints = {
        "7b": 1,
        "8b": 1,
        "13b": 2,
        "14b": 2,
        "32b": 4,
        "34b": 4,
        "70b": 4,
        "72b": 4,
        "110b": 8,
        "130b": 8,
        "671b": 8,
    }

    for size_hint, tp in model_size_hints.items():
        if size_hint in model_name.lower():
            config.tp_size = min(tp, npu_count)
            break
    else:
        config.tp_size = min(4, npu_count)

    # MoE EP
    if model_arch == ModelArchitecture.MOE and npu_count >= config.tp_size:
        config.ep_size = npu_count // config.tp_size

    # 量化
    if quant_format:
        config.quantization = quant_format.value

    # 长序列
    if any(k in model_name.lower() for k in ["32k", "128k", "long"]):
        config.max_model_len = 32768
        config.enable_chunked_prefill = True

    config.enable_prefix_caching = True
    config.gpu_memory_utilization = 0.9

    return config

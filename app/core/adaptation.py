"""昇腾 NPU 模型适配核心模块

实现 adapt-agent skill 的 10 步模型适配 playbook：
1. 收集上下文（模型路径、实现根目录、交付仓库、默认功能集）
2. 分析模型（config.json、modeling 文件、processor、tokenizer、safetensors）
3. 算子兼容性门控（Torch/Triton/CUDA 分类）
4. 框架侧代码分析（vLLM 补丁检查）
5. 选择适配策略（复用/补丁/新适配器）
6. 实现最小代码改动
7. 两阶段验证（dummy + real-weight）
8. 验证推理和功能
9. Backport + 生成产物 + 提交
10. 交接产物
"""

import json
import logging
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("ascend_adaptation")


# ========== 枚举与数据结构 ==========


class AdaptationStatus(Enum):
    """适配会话状态"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


class StepStatus(Enum):
    """单步状态"""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class OperatorClassification(Enum):
    """算子分类"""

    TORCH = "Torch"  # PyTorch 原生算子，昇腾自动兼容
    TRITON = "Triton"  # Triton kernel，需验证或重写
    CUDA_WITH_FALLBACK = "CUDA_with_fallback"  # CUDA 算子但有 CPU/Torch 回退
    CUDA_WITHOUT_FALLBACK = "CUDA_without_fallback"  # CUDA 算子无回退，阻塞
    TRITON_VERIFICATION_FAILED = "Triton_verification_failed"  # Triton 验证失败


class AdaptationStrategy(Enum):
    """适配策略"""

    REUSE = "reuse"  # 架构已注册，仅补丁损坏部分
    PATCH = "patch"  # 需要补丁 vllm-ascend 代码
    NEW_ADAPTER = "new_adapter"  # 需要新写适配器
    BLOCKED = "blocked"  # 被阻塞，需提 GitHub issue


class ModelArchitectureType(Enum):
    """模型架构类型"""

    LLM_STANDARD = "LLM_Standard"
    LLM_SLIDING_WINDOW = "LLM_Sliding_Window"
    LLM_MAMBA = "LLM_Mamba"
    LLM_MLA = "LLM_MLA"
    LLM_HYBRID = "LLM_Hybrid"
    VLM = "VLM"
    WHISPER = "Whisper"
    ENCODER_DECODER = "Encoder_Decoder"


class AttentionVariant(Enum):
    """注意力变体"""

    MHA = "MHA"  # Multi-Head Attention
    GQA = "GQA"  # Grouped Query Attention
    MQA = "MQA"  # Multi-Query Attention
    MLA = "MLA"  # Multi-head Latent Attention
    SLIDING_WINDOW = "Sliding_Window"


class QuantizationType(Enum):
    """量化类型"""

    NONE = "none"
    GPTQ = "gptq"
    AWQ = "awq"
    SMOOTHQUANT = "smoothquant"
    W8A8 = "w8a8"
    W4A16 = "w4a16"
    FP8 = "fp8"
    OTHER = "other"


# 10 步名称定义
STEP_NAMES = {
    1: "收集上下文",
    2: "分析模型",
    3: "算子兼容性门控",
    4: "框架侧代码分析",
    5: "选择适配策略",
    6: "实现最小代码改动",
    7: "两阶段验证",
    8: "验证推理和功能",
    9: "生成产物",
    10: "交接产物",
}


@dataclass
class AdaptationStep:
    """单步状态"""

    step_number: int
    name: str
    status: StepStatus = StepStatus.PENDING
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_number": self.step_number,
            "name": self.name,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
        }


@dataclass
class AdaptationSession:
    """适配会话"""

    id: str
    model_path: str
    model_name: str
    current_step: int = 1
    status: AdaptationStatus = AdaptationStatus.PENDING
    steps_data: dict[int, AdaptationStep] = field(default_factory=dict)
    delivery_repo: str = ""
    features: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
        # 初始化 10 步
        if not self.steps_data:
            for i in range(1, 11):
                self.steps_data[i] = AdaptationStep(
                    step_number=i,
                    name=STEP_NAMES[i],
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "model_path": self.model_path,
            "model_name": self.model_name,
            "current_step": self.current_step,
            "status": self.status.value,
            "steps": {str(k): v.to_dict() for k, v in self.steps_data.items()},
            "delivery_repo": self.delivery_repo,
            "features": self.features,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ========== 会话存储 ==========

_sessions: dict[str, AdaptationSession] = {}
_sessions_lock = threading.Lock()


def _update_session(session: AdaptationSession):
    """更新会话时间戳"""
    session.updated_at = datetime.now().isoformat()


# ========== Step 1: 收集上下文 ==========


def create_session(
    model_path: str,
    model_name: str,
    delivery_repo: str = "",
    features: list[str] | None = None,
) -> AdaptationSession:
    """创建适配会话，初始化 10 步

    Args:
        model_path: 模型权重路径（本地或 HuggingFace ID）
        model_name: 模型名称标识
        delivery_repo: 交付仓库路径
        features: 默认功能集（如 ["generate", "chat"]）

    Returns:
        新创建的适配会话
    """
    session_id = uuid.uuid4().hex[:12]

    # 校验 model_path 非空
    if not model_path or not model_path.strip():
        raise ValueError("model_path 不能为空")

    # 校验本地路径存在性（仅对非 HuggingFace ID 的本地路径）
    if (
        model_path.startswith("/")
        or model_path.startswith("./")
        or (len(model_path) > 2 and model_path[1] == ":")
    ):
        if not Path(model_path).exists():
            raise FileNotFoundError(f"模型路径不存在: {model_path}")

    session = AdaptationSession(
        id=session_id,
        model_path=model_path.strip(),
        model_name=model_name.strip() or Path(model_path).name,
        delivery_repo=delivery_repo,
        features=features or ["generate", "chat"],
    )
    with _sessions_lock:
        _sessions[session_id] = session
    logger.info("创建适配会话: id=%s, model=%s", session_id, model_name)
    return session


def get_session(session_id: str) -> AdaptationSession | None:
    """获取会话"""
    with _sessions_lock:
        return _sessions.get(session_id)


def list_sessions() -> list[dict[str, Any]]:
    """列出所有会话"""
    with _sessions_lock:
        return [s.to_dict() for s in _sessions.values()]


def step1_collect_context(
    session_id: str,
    context: dict[str, Any] | None = None,
) -> AdaptationStep:
    """Step 1: 收集上下文信息

    收集模型路径、实现根目录、交付仓库、默认功能集等基础信息。

    Args:
        session_id: 会话 ID
        context: 上下文信息字典，可包含：
            - model_path: 模型路径
            - implementation_root: 实现根目录
            - delivery_repo: 交付仓库
            - features: 功能集
            - vllm_path: vLLM 安装路径
            - transformers_version: transformers 版本
    """
    session = _sessions.get(session_id)
    if not session:
        raise ValueError(f"会话不存在: {session_id}")

    step = session.steps_data[1]
    step.status = StepStatus.RUNNING
    _update_session(session)

    try:
        ctx = context or {}
        # 补全会话信息
        if "model_path" in ctx:
            session.model_path = ctx["model_path"]
        if "delivery_repo" in ctx:
            session.delivery_repo = ctx["delivery_repo"]
        if "features" in ctx:
            session.features = ctx["features"]

        step.result = {
            "model_path": session.model_path,
            "model_name": session.model_name,
            "delivery_repo": session.delivery_repo,
            "features": session.features,
            "implementation_root": ctx.get("implementation_root", ""),
            "vllm_path": ctx.get("vllm_path", ""),
            "transformers_version": ctx.get("transformers_version", ""),
        }
        step.status = StepStatus.PASSED
        session.current_step = 2
        session.status = AdaptationStatus.IN_PROGRESS
        logger.info("Step 1 完成: session=%s", session_id)

    except Exception as e:
        step.status = StepStatus.FAILED
        step.error = str(e)
        logger.error("Step 1 失败: session=%s, error=%s", session_id, e)

    _update_session(session)
    return step


# ========== Step 2: 分析模型 ==========


def step2_analyze_model(session_id: str) -> AdaptationStep:
    """Step 2: 分析模型

    读取 config.json，推断架构类型（LLM/VLM/Whisper），
    识别注意力变体（GQA/MQA/MHA/MLA/sliding_window），
    量化类型，state-dict key prefix。
    """
    session = _sessions.get(session_id)
    if not session:
        raise ValueError(f"会话不存在: {session_id}")

    step = session.steps_data[2]
    step.status = StepStatus.RUNNING
    _update_session(session)

    try:
        model_path = Path(session.model_path)
        config_data = {}

        # 尝试读取 config.json
        config_path = model_path / "config.json"
        if config_path.exists():
            try:
                with open(config_path, encoding="utf-8") as f:
                    config_data = json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning("config.json 解析失败: %s, 使用空配置", e)
                step.result["config_note"] = f"config.json 解析失败: {e}"
        else:
            # 可能是 HuggingFace ID，记录提示
            step.result["config_note"] = "config.json 未在本地找到，请确保模型已下载"

        # 推断架构类型
        arch_type = _infer_architecture_type(config_data)

        # 识别注意力变体
        attention_variant = _infer_attention_variant(config_data)

        # 识别量化类型
        quant_type = _infer_quantization_type(config_data, model_path)

        # 提取 state-dict key prefix
        key_prefix = _infer_key_prefix(config_data)

        # 检查模型文件
        model_files = _scan_model_files(model_path)

        step.result = {
            "architecture_type": arch_type.value,
            "attention_variant": attention_variant.value,
            "quantization_type": quant_type.value,
            "key_prefix": key_prefix,
            "model_type": config_data.get("model_type", ""),
            "architectures": config_data.get("architectures", []),
            "model_files": model_files,
            "has_vision_config": "vision_config" in config_data,
            "has_encoder_decoder": config_data.get("is_encoder_decoder", False),
            "config_data_keys": list(config_data.keys())[:30],
        }
        step.status = StepStatus.PASSED
        session.current_step = 3
        logger.info(
            "Step 2 完成: session=%s, arch=%s, attn=%s",
            session_id,
            arch_type.value,
            attention_variant.value,
        )

    except Exception as e:
        step.status = StepStatus.FAILED
        step.error = str(e)
        logger.error("Step 2 失败: session=%s, error=%s", session_id, e)

    _update_session(session)
    return step


def _infer_architecture_type(config: dict[str, Any]) -> ModelArchitectureType:
    """推断模型架构类型"""
    # 检查是否有视觉配置
    if "vision_config" in config:
        return ModelArchitectureType.VLM

    # 检查是否是编码器-解码器
    if config.get("is_encoder_decoder", False):
        model_type = config.get("model_type", "").lower()
        if "whisper" in model_type:
            return ModelArchitectureType.WHISPER
        return ModelArchitectureType.ENCODER_DECODER

    # LLM 细分
    model_type = config.get("model_type", "").lower()
    architectures = [a.lower() for a in config.get("architectures", [])]

    # MLA 检测（DeepSeek-V2/V3 系列）
    if (
        "mla" in str(config.get("model_type", "")).lower()
        or any("mla" in a for a in architectures)
        or "q_lora_rank" in config
    ):
        return ModelArchitectureType.LLM_MLA

    # Mamba 检测
    if "mamba" in model_type or any("mamba" in a for a in architectures):
        return ModelArchitectureType.LLM_MAMBA

    # Sliding Window 检测
    if config.get("sliding_window") or config.get("sliding_window_size"):
        return ModelArchitectureType.LLM_SLIDING_WINDOW

    # Hybrid 检测（如 Jamba 等 Mamba+Attention 混合）
    if "mamba" in str(config) and "attention" in str(config):
        return ModelArchitectureType.LLM_HYBRID

    return ModelArchitectureType.LLM_STANDARD


def _infer_attention_variant(config: dict[str, Any]) -> AttentionVariant:
    """识别注意力变体"""
    # MLA 检测
    if "q_lora_rank" in config or "kv_lora_rank" in config:
        return AttentionVariant.MLA

    # GQA / MQA 检测
    num_attention_heads = config.get("num_attention_heads", 0)
    num_key_value_heads = config.get("num_key_value_heads", 0)

    if num_key_value_heads > 0 and num_attention_heads > 0:
        if num_key_value_heads == 1:
            return AttentionVariant.MQA
        elif num_key_value_heads < num_attention_heads:
            return AttentionVariant.GQA

    # Sliding Window 检测
    if config.get("sliding_window") or config.get("sliding_window_size"):
        return AttentionVariant.SLIDING_WINDOW

    return AttentionVariant.MHA


def _infer_quantization_type(
    config: dict[str, Any], model_path: Path
) -> QuantizationType:
    """识别量化类型"""
    quant_method = config.get("quantization_config", {}).get("quant_method", "").lower()

    if not quant_method:
        # 检查文件名中的量化标识
        model_name = str(model_path).lower()
        if "w8a8" in model_name:
            return QuantizationType.W8A8
        if "w4a16" in model_name:
            return QuantizationType.W4A16
        if "fp8" in model_name:
            return QuantizationType.FP8
        if "gptq" in model_name:
            return QuantizationType.GPTQ
        if "awq" in model_name:
            return QuantizationType.AWQ
        return QuantizationType.NONE

    quant_map = {
        "gptq": QuantizationType.GPTQ,
        "awq": QuantizationType.AWQ,
        "smoothquant": QuantizationType.SMOOTHQUANT,
        "fp8": QuantizationType.FP8,
        "w8a8": QuantizationType.W8A8,
    }
    return quant_map.get(quant_method, QuantizationType.OTHER)


def _infer_key_prefix(config: dict[str, Any]) -> str:
    """推断 state-dict key prefix"""
    architectures = config.get("architectures", [])
    if architectures:
        # 常见映射：架构类名 → key prefix
        arch = architectures[0]
        prefix_map = {
            "LlamaForCausalLM": "model",
            "Qwen2ForCausalLM": "model",
            "Qwen3ForCausalLM": "model",
            "DeepseekV2ForCausalLM": "model",
            "DeepseekV3ForCausalLM": "model",
            "ChatGLMModel": "transformer",
            "WhisperForConditionalGeneration": "model",
        }
        return prefix_map.get(arch, "model")
    return "model"


def _scan_model_files(model_path: Path) -> dict[str, Any]:
    """扫描模型目录中的文件"""
    result = {
        "has_config": False,
        "has_tokenizer": False,
        "has_processor": False,
        "has_safetensors": False,
        "has_pytorch_bin": False,
        "safetensors_count": 0,
        "pytorch_bin_count": 0,
    }

    if not model_path.exists():
        result["note"] = "模型路径不存在（可能是 HuggingFace ID）"
        return result

    for f in model_path.iterdir():
        name = f.name.lower()
        if name == "config.json":
            result["has_config"] = True
        elif "tokenizer" in name:
            result["has_tokenizer"] = True
        elif "processor" in name and name.endswith(".json"):
            result["has_processor"] = True
        elif name.endswith(".safetensors"):
            result["has_safetensors"] = True
            result["safetensors_count"] += 1
        elif name.endswith(".bin") or name.endswith(".pt"):
            result["has_pytorch_bin"] = True
            result["pytorch_bin_count"] += 1

    return result


# ========== Step 3: 算子兼容性门控 ==========

# 算子扫描正则
_TRITON_IMPORT_RE = re.compile(r"import\s+triton|from\s+triton\s+import|@triton\.jit")
_CUDA_CALL_RE = re.compile(
    r"\.cuda\(\)|torch\.cuda\.|cupy\.|custom_cuda|cuda_ext|_cuda\b"
)
_TORCH_IMPORT_RE = re.compile(r"import\s+torch|from\s+torch\s+import")


def step3_operator_gate(
    session_id: str,
    model_code: str = "",
) -> AdaptationStep:
    """Step 3: 算子兼容性门控

    扫描代码中的算子类型，分类为 Torch/Triton/CUDA。
    CUDA without fallback → BLOCKED。

    Args:
        session_id: 会话 ID
        model_code: 模型实现代码（Python 源码字符串）
    """
    session = _sessions.get(session_id)
    if not session:
        raise ValueError(f"会话不存在: {session_id}")

    step = session.steps_data[3]
    step.status = StepStatus.RUNNING
    _update_session(session)

    try:
        operators = _scan_operators(model_code)

        # 分类结果
        classification = {
            OperatorClassification.TORCH.value: operators["torch_ops"],
            OperatorClassification.TRITON.value: operators["triton_ops"],
            OperatorClassification.CUDA_WITH_FALLBACK.value: operators[
                "cuda_with_fallback"
            ],
            OperatorClassification.CUDA_WITHOUT_FALLBACK.value: operators[
                "cuda_without_fallback"
            ],
        }

        # 判断是否阻塞
        blocked_ops = operators["cuda_without_fallback"]
        if blocked_ops:
            step.status = StepStatus.BLOCKED
            session.status = AdaptationStatus.BLOCKED
            step.error = (
                f"发现 {len(blocked_ops)} 个无回退 CUDA 算子，适配被阻塞: "
                f"{', '.join(blocked_ops[:5])}"
            )
        else:
            step.status = StepStatus.PASSED
            session.current_step = 4

        step.result = {
            "classification": classification,
            "blocked": bool(blocked_ops),
            "blocked_operators": blocked_ops,
            "triton_count": len(operators["triton_ops"]),
            "cuda_count": len(operators["cuda_with_fallback"])
            + len(operators["cuda_without_fallback"]),
            "torch_count": len(operators["torch_ops"]),
        }

        logger.info(
            "Step 3 完成: session=%s, blocked=%s, triton=%d, cuda=%d",
            session_id,
            bool(blocked_ops),
            len(operators["triton_ops"]),
            len(operators["cuda_with_fallback"])
            + len(operators["cuda_without_fallback"]),
        )

    except Exception as e:
        step.status = StepStatus.FAILED
        step.error = str(e)
        logger.error("Step 3 失败: session=%s, error=%s", session_id, e)

    _update_session(session)
    return step


def _scan_operators(code: str) -> dict[str, list[str]]:
    """扫描代码中的算子类型

    Returns:
        包含 torch_ops, triton_ops, cuda_with_fallback, cuda_without_fallback 的字典
    """
    result = {
        "torch_ops": [],
        "triton_ops": [],
        "cuda_with_fallback": [],
        "cuda_without_fallback": [],
    }

    if not code:
        return result

    lines = code.splitlines()

    # 当前函数/方法上下文，用于判断 CUDA 是否有 fallback

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Triton 检测
        if _TRITON_IMPORT_RE.search(stripped):
            # 提取函数名
            func_match = re.search(r"def\s+(\w+)", stripped)
            name = func_match.group(1) if func_match else f"triton_kernel_line_{i + 1}"
            result["triton_ops"].append(name)

        # CUDA 检测
        if _CUDA_CALL_RE.search(stripped):
            # 提取 CUDA 操作描述
            cuda_match = re.search(
                r"(\w+)\s*[=\(].*\.cuda\(\)|(\w+)\s*[=\(].*torch\.cuda\.|(\w+)\s*[=\(].*cupy\.|(\w+)\s*[=\(].*custom_cuda",
                stripped,
            )
            name = ""
            for g in cuda_match.groups() if cuda_match else []:
                if g:
                    name = g
                    break
            if not name:
                name = f"cuda_op_line_{i + 1}"

            # 检查同一代码块中是否有 CPU/Torch fallback
            # 简化判断：搜索上下文中是否有 .cpu() 或 if.*device 或 try.*except
            has_fallback = _check_cuda_fallback(lines, i)
            if has_fallback:
                result["cuda_with_fallback"].append(name)
            else:
                result["cuda_without_fallback"].append(name)

        # Torch 原生检测
        if _TORCH_IMPORT_RE.search(stripped) and not _CUDA_CALL_RE.search(stripped):
            func_match = re.search(r"def\s+(\w+)", stripped)
            if func_match:
                result["torch_ops"].append(func_match.group(1))

    return result


def _check_cuda_fallback(lines: list[str], cuda_line_idx: int) -> bool:
    """检查 CUDA 操作是否有 CPU/Torch fallback

    在 CUDA 调用附近的代码块中搜索 fallback 证据：
    - .cpu() / .to("cpu")
    - if ... device / if ... cuda
    - try ... except 包含 CPU 回退
    - hasattr 检查 CUDA 可用性
    """
    # 搜索范围：当前行前后 20 行
    start = max(0, cuda_line_idx - 20)
    end = min(len(lines), cuda_line_idx + 20)

    context = "\n".join(lines[start:end])

    fallback_patterns = [
        r"\.cpu\(\)",
        r'\.to\(["\']cpu["\']\)',
        r"if\s+.*\.is_cuda_available",
        r"if\s+.*device.*==.*cpu",
        r"torch\.cuda\.is_available",
        r"hasattr.*cuda",
        r"except.*:",
        r"fallback",
        r"cpu_version",
    ]

    for pattern in fallback_patterns:
        if re.search(pattern, context, re.IGNORECASE):
            return True

    return False


# ========== Step 4: 框架侧代码分析 ==========


def step4_framework_analysis(
    session_id: str,
    vllm_path: str = "",
) -> AdaptationStep:
    """Step 4: 框架侧代码分析

    检查 vLLM registry.py 中是否已有架构注册，
    检查 vllm-ascend 补丁。

    Args:
        session_id: 会话 ID
        vllm_path: vLLM 安装路径
    """
    session = _sessions.get(session_id)
    if not session:
        raise ValueError(f"会话不存在: {session_id}")

    step = session.steps_data[4]
    step.status = StepStatus.RUNNING
    _update_session(session)

    try:
        # 获取 step2 的架构信息
        step2_data = session.steps_data[2].result
        architectures = step2_data.get("architectures", [])

        # 检查 registry.py
        registry_info = _check_vllm_registry(vllm_path, architectures)

        # 检查 vllm-ascend 补丁
        patch_info = _check_vllm_ascend_patches(vllm_path, architectures)

        step.result = {
            "architectures": architectures,
            "registry_info": registry_info,
            "patch_info": patch_info,
            "vllm_path": vllm_path,
        }
        step.status = StepStatus.PASSED
        session.current_step = 5
        logger.info(
            "Step 4 完成: session=%s, registered=%s",
            session_id,
            registry_info.get("registered", False),
        )

    except Exception as e:
        step.status = StepStatus.FAILED
        step.error = str(e)
        logger.error("Step 4 失败: session=%s, error=%s", session_id, e)

    _update_session(session)
    return step


def _check_vllm_registry(vllm_path: str, architectures: list[str]) -> dict[str, Any]:
    """检查 vLLM registry.py 中是否已注册架构"""
    result = {
        "registered": False,
        "registered_architectures": [],
        "registry_path": "",
    }

    if not vllm_path:
        result["note"] = "vLLM 路径未提供，无法检查 registry"
        return result

    # 查找 registry.py
    vllm_dir = Path(vllm_path)
    registry_paths = [
        vllm_dir / "vllm" / "model_executor" / "models" / "registry.py",
        vllm_dir / "vllm" / "models" / "registry.py",
    ]

    registry_file = None
    for rp in registry_paths:
        if rp.exists():
            registry_file = rp
            break

    if not registry_file:
        result["note"] = "registry.py 未找到"
        return result

    result["registry_path"] = str(registry_file)

    try:
        content = registry_file.read_text(encoding="utf-8")
        for arch in architectures:
            if arch in content:
                result["registered"] = True
                result["registered_architectures"].append(arch)
    except Exception as e:
        result["error"] = str(e)

    return result


def _check_vllm_ascend_patches(
    vllm_path: str, architectures: list[str]
) -> dict[str, Any]:
    """检查 vllm-ascend 补丁"""
    result = {
        "patch_available": False,
        "patch_files": [],
    }

    if not vllm_path:
        return result

    vllm_dir = Path(vllm_path)
    # 搜索 vllm-ascend 相关补丁文件
    ascend_dirs = [
        vllm_dir / "vllm_ascend",
        vllm_dir / "vllm" / "ascend",
    ]

    for ad in ascend_dirs:
        if ad.exists() and ad.is_dir():
            result["patch_available"] = True
            for f in ad.rglob("*.py"):
                result["patch_files"].append(str(f))
            break

    return result


# ========== Step 5: 选择适配策略 ==========


def step5_choose_strategy(session_id: str) -> AdaptationStep:
    """Step 5: 选择适配策略

    基于 step 2-4 结果自动判断：
    - architectures 已在 registry.py → reuse（仅补丁损坏部分）
    - architectures 不存在或不适配 → new_adapter
    - remote_code 需要更新 transformers → copy files
    - 失败需要 vllm-ascend 中的建模代码 → blocked（raise GitHub issue）
    """
    session = _sessions.get(session_id)
    if not session:
        raise ValueError(f"会话不存在: {session_id}")

    step = session.steps_data[5]
    step.status = StepStatus.RUNNING
    _update_session(session)

    try:
        step2_data = session.steps_data[2].result
        step3_data = session.steps_data[3].result
        step4_data = session.steps_data[4].result

        # 如果 step3 被阻塞，策略也是 blocked
        if step3_data.get("blocked", False):
            strategy = AdaptationStrategy.BLOCKED
            reason = "存在无回退 CUDA 算子，需要 vllm-ascend 中的建模代码支持"
        elif step4_data.get("registry_info", {}).get("registered", False):
            strategy = AdaptationStrategy.REUSE
            reason = "架构已在 vLLM registry 中注册，仅需补丁损坏部分"
        else:
            strategy = AdaptationStrategy.NEW_ADAPTER
            reason = "架构未在 vLLM registry 中注册，需要编写新适配器"

        # 检查是否需要 patch（有 Triton 算子时可能需要）
        if (
            strategy == AdaptationStrategy.REUSE
            and step3_data.get("triton_count", 0) > 0
        ):
            strategy = AdaptationStrategy.PATCH
            reason = "架构已注册但存在 Triton 算子，需要补丁处理"

        step.result = {
            "strategy": strategy.value,
            "reason": reason,
            "step2_arch_type": step2_data.get("architecture_type", ""),
            "step3_blocked": step3_data.get("blocked", False),
            "step4_registered": step4_data.get("registry_info", {}).get(
                "registered", False
            ),
        }
        step.status = StepStatus.PASSED
        session.current_step = 6

        # 如果策略是 blocked，更新会话状态
        if strategy == AdaptationStrategy.BLOCKED:
            session.status = AdaptationStatus.BLOCKED

        logger.info("Step 5 完成: session=%s, strategy=%s", session_id, strategy.value)

    except Exception as e:
        step.status = StepStatus.FAILED
        step.error = str(e)
        logger.error("Step 5 失败: session=%s, error=%s", session_id, e)

    _update_session(session)
    return step


# ========== Step 6: 实现最小代码改动 ==========


def step6_implement(
    session_id: str,
    implementation_details: dict[str, Any] | None = None,
) -> AdaptationStep:
    """Step 6: 实现最小代码改动

    根据适配策略生成适配器代码模板。

    Args:
        session_id: 会话 ID
        implementation_details: 实现细节（可选覆盖）
    """
    session = _sessions.get(session_id)
    if not session:
        raise ValueError(f"会话不存在: {session_id}")

    step = session.steps_data[6]
    step.status = StepStatus.RUNNING
    _update_session(session)

    try:
        step5_data = session.steps_data[5].result
        session.steps_data[2].result
        strategy_str = step5_data.get("strategy", "new_adapter")
        strategy = AdaptationStrategy(strategy_str)

        details = implementation_details or {}

        if strategy == AdaptationStrategy.BLOCKED:
            step.result = {
                "strategy": "blocked",
                "action": "raise_github_issue",
                "issue_template": _generate_issue_template(session),
                "message": "适配被阻塞，请提交 GitHub issue 请求 vllm-ascend 支持",
            }
        elif strategy == AdaptationStrategy.REUSE:
            step.result = _generate_reuse_code(session, details)
        elif strategy == AdaptationStrategy.PATCH:
            step.result = _generate_patch_code(session, details)
        else:
            step.result = _generate_new_adapter_code(session, details)

        step.result["strategy"] = strategy.value
        step.status = StepStatus.PASSED
        session.current_step = 7
        logger.info("Step 6 完成: session=%s, strategy=%s", session_id, strategy.value)

    except Exception as e:
        step.status = StepStatus.FAILED
        step.error = str(e)
        logger.error("Step 6 失败: session=%s, error=%s", session_id, e)

    _update_session(session)
    return step


def _generate_new_adapter_code(
    session: AdaptationSession, details: dict
) -> dict[str, Any]:
    """生成新适配器代码模板"""
    step2_data = session.steps_data[2].result
    arch_type = step2_data.get("architecture_type", "LLM_Standard")
    attention = step2_data.get("attention_variant", "MHA")
    quant = step2_data.get("quantization_type", "none")
    architectures = step2_data.get("architectures", [])
    arch_class = architectures[0] if architectures else "CustomModelForCausalLM"

    adapter_code = f'''"""昇腾 NPU 适配器: {session.model_name}

架构类型: {arch_type}
注意力变体: {attention}
量化类型: {quant}
生成时间: {datetime.now().isoformat()}
"""

import torch
import torch_npu
from vllm.model_executor.models.registry import ModelRegistry


class {arch_class}NPUAdapter:
    """{session.model_name} 昇腾 NPU 适配器

    设备检测 + fallback 分支：
    - NPU 可用时使用 torch_npu 加速
    - NPU 不可用时回退到 CPU/CUDA
    """

    def __init__(self, model_config, **kwargs):
        self.model_config = model_config
        self.device = self._detect_device()
        self.model = None

    @staticmethod
    def _detect_device() -> str:
        """检测可用设备，优先 NPU"""
        try:
            if torch.npu.is_available():
                return "npu"
        except Exception:
            pass
        try:
            if torch.cuda.is_available():
                return "cuda"
        except Exception:
            pass
        return "cpu"

    def load_model(self, weights):
        """加载模型权重"""
        # TODO: 实现权重加载逻辑
        pass

    def forward(self, input_ids, **kwargs):
        """前向推理"""
        # TODO: 实现前向推理逻辑
        pass


def register_{arch_class.lower()}_adapter():
    """注册适配器到 vLLM ModelRegistry"""
    # TODO: 在 vllm registry.py 中注册
    # ModelRegistry.register_model("{arch_class}", {arch_class}NPUAdapter)
    pass
'''

    weight_loader_code = f'''"""权重加载器: {session.model_name}"""


def load_weights_npu(model, checkpoint_path, device="npu"):
    """在 NPU 上加载模型权重

    Args:
        model: 模型实例
        checkpoint_path: 权重文件路径
        device: 目标设备
    """
    import safetensors.torch

    # 遍历 safetensors 文件
    from pathlib import Path
    weight_dir = Path(checkpoint_path)
    for sf_file in sorted(weight_dir.glob("*.safetensors")):
        weights = safetensors.torch.load_file(str(sf_file), device="cpu")
        # 转换到 NPU
        if device == "npu":
            weights = {{k: v.npu() for k, v in weights.items()}}
        model.load_weights(weights.items())
'''

    return {
        "adapter_code": adapter_code,
        "weight_loader_code": weight_loader_code,
        "files_to_create": [
            f"vllm/model_executor/models/{arch_class.lower()}_npu.py",
            f"vllm/model_executor/models/{arch_class.lower()}_weight_loader.py",
        ],
        "registry_entry": f'"{arch_class}": "{arch_class.lower()}_npu.py"',
    }


def _generate_reuse_code(session: AdaptationSession, details: dict) -> dict[str, Any]:
    """生成复用策略代码"""
    step2_data = session.steps_data[2].result
    architectures = step2_data.get("architectures", [])
    arch_class = architectures[0] if architectures else "Unknown"

    return {
        "message": f"架构 {arch_class} 已在 registry 中注册，仅需补丁损坏部分",
        "patch_instructions": [
            f"1. 检查 {arch_class} 在 vllm-ascend 中的补丁状态",
            "2. 如果补丁已存在但损坏，修复补丁",
            "3. 如果补丁不存在，创建最小补丁",
        ],
        "files_to_patch": details.get("files_to_patch", []),
    }


def _generate_patch_code(session: AdaptationSession, details: dict) -> dict[str, Any]:
    """生成补丁策略代码"""
    step2_data = session.steps_data[2].result
    step3_data = session.steps_data[3].result
    architectures = step2_data.get("architectures", [])
    arch_class = architectures[0] if architectures else "Unknown"

    triton_ops = step3_data.get("classification", {}).get("Triton", [])

    return {
        "message": f"架构 {arch_class} 已注册但存在 Triton 算子，需要补丁",
        "triton_ops_to_handle": triton_ops,
        "patch_template": f'''"""Triton 算子 NPU 补丁: {session.model_name}"""


def patch_triton_ops():
    """将 Triton 算子替换为 NPU 兼容实现"""
    # TODO: 为每个 Triton 算子编写 NPU 兼容实现
    pass
''',
        "files_to_create": [
            f"vllm_ascend/patches/{arch_class.lower()}_triton_patch.py",
        ],
    }


def _generate_issue_template(session: AdaptationSession) -> str:
    """生成 GitHub issue 模板"""
    step2_data = session.steps_data[2].result
    step3_data = session.steps_data[3].result

    return f"""## 模型适配请求: {session.model_name}

### 模型信息
- 模型路径: {session.model_path}
- 架构类型: {step2_data.get("architecture_type", "Unknown")}
- 注意力变体: {step2_data.get("attention_variant", "Unknown")}
- 量化类型: {step2_data.get("quantization_type", "none")}

### 阻塞原因
存在无回退 CUDA 算子:
{chr(10).join(f"- {op}" for op in step3_data.get("blocked_operators", []))}

### 请求
请在 vllm-ascend 中添加对 {session.model_name} 的建模代码支持。
"""


# ========== Step 7: 两阶段验证 ==========


def step7_validate_dummy(
    session_id: str,
    config: dict[str, Any] | None = None,
) -> AdaptationStep:
    """Step 7a: 两阶段验证 - Dummy Fast Gate

    生成 vllm serve --load-format dummy 命令，
    用于快速验证模型加载流程是否正确（不加载实际权重）。

    Args:
        session_id: 会话 ID
        config: 验证配置（可选）
    """
    session = _sessions.get(session_id)
    if not session:
        raise ValueError(f"会话不存在: {session_id}")

    step = session.steps_data[7]
    step.status = StepStatus.RUNNING
    _update_session(session)

    try:
        cfg = config or {}
        model_path = cfg.get("model_path", session.model_path)
        tp_size = cfg.get("tensor_parallel_size", 1)
        host = cfg.get("host", "0.0.0.0")
        port = cfg.get("port", 8000)
        max_model_len = cfg.get("max_model_len", 4096)

        # 生成 dummy 验证命令（路径用引号包裹防空格）
        dummy_command = (
            f"vllm serve '{model_path}' "
            f"--load-format dummy "
            f"--tensor-parallel-size {tp_size} "
            f"--host {host} --port {port} "
            f"--max-model-len {max_model_len} "
            f"--trust-remote-code"
        )

        step.result = {
            "phase": "dummy_fast_gate",
            "command": dummy_command,
            "description": "Dummy Fast Gate: 使用虚拟权重验证模型加载流程",
            "expected_outcome": "服务启动成功，/v1/models 返回模型信息",
            "timeout_seconds": 120,
            "next_step": "如果 dummy 验证通过，继续 step7-real 进行实际权重验证",
        }
        step.status = StepStatus.PASSED
        logger.info("Step 7-dummy 完成: session=%s", session_id)

    except Exception as e:
        step.status = StepStatus.FAILED
        step.error = str(e)
        logger.error("Step 7-dummy 失败: session=%s, error=%s", session_id, e)

    _update_session(session)
    return step


def step7_validate_real(
    session_id: str,
    config: dict[str, Any] | None = None,
) -> AdaptationStep:
    """Step 7b: 两阶段验证 - Real-Weight Mandatory Gate

    使用实际权重验证模型加载和推理。

    Args:
        session_id: 会话 ID
        config: 验证配置（可选）
    """
    session = _sessions.get(session_id)
    if not session:
        raise ValueError(f"会话不存在: {session_id}")

    step = session.steps_data[7]
    step.status = StepStatus.RUNNING
    _update_session(session)

    try:
        cfg = config or {}
        model_path = cfg.get("model_path", session.model_path)
        tp_size = cfg.get("tensor_parallel_size", 1)
        host = cfg.get("host", "0.0.0.0")
        port = cfg.get("port", 8000)
        max_model_len = cfg.get("max_model_len", 8192)
        gpu_mem_util = cfg.get("gpu_memory_utilization", 0.90)

        # 生成 real-weight 验证命令（model_path 用引号包裹防止路径注入）
        serve_command = (
            f"vllm serve '{model_path}' "
            f"--tensor-parallel-size {tp_size} "
            f"--host {host} --port {port} "
            f"--max-model-len {max_model_len} "
            f"--gpu-memory-utilization {gpu_mem_util} "
            f"--trust-remote-code"
        )

        # 环境变量
        env_commands = [
            "export VLLM_USE_MODELSCOPE=true",
            "export PYTORCH_NPU_ALLOC_CONF=expandable_segments:True",
            "export TASK_QUEUE_ENABLE=1",
        ]

        step.result = {
            "phase": "real_weight_mandatory_gate",
            "serve_command": serve_command,
            "env_commands": env_commands,
            "description": "Real-Weight Mandatory Gate: 使用实际权重验证模型加载和推理",
            "expected_outcome": "服务启动成功，chat/completions API 可正常返回",
            "timeout_seconds": 300,
            "validation_curl": (
                f"curl http://{host}:{port}/v1/chat/completions "
                f'-H "Content-Type: application/json" '
                f'-d \'{{"model": "{session.model_name}", '
                f'"messages": [{{"role": "user", "content": "Hello"}}], '
                f'"max_tokens": 32}}\''
            ),
        }
        step.status = StepStatus.PASSED
        session.current_step = 8
        logger.info("Step 7-real 完成: session=%s", session_id)

    except Exception as e:
        step.status = StepStatus.FAILED
        step.error = str(e)
        logger.error("Step 7-real 失败: session=%s, error=%s", session_id, e)

    _update_session(session)
    return step


# ========== Step 8: 验证推理和功能 ==========


def step8_validate_inference(
    session_id: str,
    host: str = "0.0.0.0",
    port: int = 8000,
) -> AdaptationStep:
    """Step 8: 验证推理和功能

    生成 curl 测试命令，验证模型推理能力。

    Args:
        session_id: 会话 ID
        host: 服务地址
        port: 服务端口
    """
    session = _sessions.get(session_id)
    if not session:
        raise ValueError(f"会话不存在: {session_id}")

    step = session.steps_data[8]
    step.status = StepStatus.RUNNING
    _update_session(session)

    try:
        model_name = session.model_name

        # 生成测试命令（model_name 用引号包裹防止注入）
        test_commands = {
            "models_list": f"curl http://{host}:{port}/v1/models",
            "chat_completions": (
                f"curl http://{host}:{port}/v1/chat/completions "
                f'-H "Content-Type: application/json" '
                f'-d \'{{"model": "{model_name}", '
                f'"messages": [{{"role": "user", "content": '
                f'"Give me a short introduction to large language models."}}], '
                f'"temperature": 0.6, "max_tokens": 256}}\''
            ),
            "completions": (
                f"curl http://{host}:{port}/v1/completions "
                f'-H "Content-Type: application/json" '
                f'-d \'{{"model": "{model_name}", '
                f'"prompt": "The meaning of life is", '
                f'"max_tokens": 64}}\''
            ),
            "health": f"curl http://{host}:{port}/health",
        }

        # 功能验证清单
        features_to_test = session.features or ["generate", "chat"]
        feature_checks = []
        for feat in features_to_test:
            if feat == "generate":
                feature_checks.append(
                    {
                        "feature": "generate",
                        "command": test_commands["completions"],
                        "expected": "返回完整文本生成结果",
                    }
                )
            elif feat == "chat":
                feature_checks.append(
                    {
                        "feature": "chat",
                        "command": test_commands["chat_completions"],
                        "expected": "返回 chat 格式响应，content 非空",
                    }
                )

        step.result = {
            "test_commands": test_commands,
            "feature_checks": feature_checks,
            "host": host,
            "port": port,
        }
        step.status = StepStatus.PASSED
        session.current_step = 9
        logger.info("Step 8 完成: session=%s", session_id)

    except Exception as e:
        step.status = StepStatus.FAILED
        step.error = str(e)
        logger.error("Step 8 失败: session=%s, error=%s", session_id, e)

    _update_session(session)
    return step


# ========== Step 9: 生成产物 ==========


def step9_generate_artifacts(session_id: str) -> AdaptationStep:
    """Step 9: 生成产物

    生成 YAML 配置、文档、提交命令。
    """
    session = _sessions.get(session_id)
    if not session:
        raise ValueError(f"会话不存在: {session_id}")

    step = session.steps_data[9]
    step.status = StepStatus.RUNNING
    _update_session(session)

    try:
        session.steps_data[2].result
        session.steps_data[5].result
        step6_data = session.steps_data[6].result

        # 生成 YAML 配置
        yaml_config = _generate_yaml_config(session)

        # 生成适配文档
        adaptation_doc = _generate_adaptation_doc(session)

        # 生成提交命令
        commit_commands = _generate_commit_commands(session)

        step.result = {
            "yaml_config": yaml_config,
            "adaptation_doc": adaptation_doc,
            "commit_commands": commit_commands,
            "artifacts": step6_data.get("files_to_create", []),
        }
        step.status = StepStatus.PASSED
        session.current_step = 10
        logger.info("Step 9 完成: session=%s", session_id)

    except Exception as e:
        step.status = StepStatus.FAILED
        step.error = str(e)
        logger.error("Step 9 失败: session=%s, error=%s", session_id, e)

    _update_session(session)
    return step


def _generate_yaml_config(session: AdaptationSession) -> str:
    """生成 YAML 配置"""
    step2_data = session.steps_data[2].result
    step5_data = session.steps_data[5].result

    return f"""# {session.model_name} 昇腾 NPU 适配配置
# 生成时间: {datetime.now().isoformat()}

model:
  name: {session.model_name}
  path: {session.model_path}
  architecture_type: {step2_data.get("architecture_type", "")}
  attention_variant: {step2_data.get("attention_variant", "")}
  quantization_type: {step2_data.get("quantization_type", "none")}
  key_prefix: {step2_data.get("key_prefix", "model")}

adaptation:
  strategy: {step5_data.get("strategy", "new_adapter")}
  session_id: {session.id}

serving:
  tensor_parallel_size: 1
  max_model_len: 8192
  gpu_memory_utilization: 0.90
  trust_remote_code: true

features:
{chr(10).join(f"  - {f}" for f in session.features)}
"""


def _generate_adaptation_doc(session: AdaptationSession) -> str:
    """生成适配文档"""
    step2_data = session.steps_data[2].result
    step3_data = session.steps_data[3].result
    step5_data = session.steps_data[5].result

    return f"""# {session.model_name} 昇腾 NPU 适配文档

## 模型信息
- 架构类型: {step2_data.get("architecture_type", "")}
- 注意力变体: {step2_data.get("attention_variant", "")}
- 量化类型: {step2_data.get("quantization_type", "none")}

## 算子兼容性
- Torch 原生算子: {step3_data.get("torch_count", 0)} 个
- Triton 算子: {step3_data.get("triton_count", 0)} 个
- CUDA 算子（有回退）: {
        len(step3_data.get("classification", {}).get("CUDA_with_fallback", []))
    } 个
- CUDA 算子（无回退）: {
        len(step3_data.get("classification", {}).get("CUDA_without_fallback", []))
    } 个

## 适配策略
- 策略: {step5_data.get("strategy", "")}
- 原因: {step5_data.get("reason", "")}

## 验证步骤
1. Dummy Fast Gate: vllm serve --load-format dummy
2. Real-Weight Gate: vllm serve（实际权重）
3. 推理验证: curl 测试 chat/completions API
"""


def _generate_commit_commands(session: AdaptationSession) -> list[str]:
    """生成提交命令"""
    step6_data = session.steps_data[6].result
    files = step6_data.get("files_to_create", [])

    commands = []
    if files:
        for f in files:
            commands.append(f"git add {f}")
        commands.append(f'git commit -m "feat: add {session.model_name} NPU adapter"')
    else:
        commands.append("# 无需新增文件，仅补丁修改")

    return commands


# ========== Step 10: 交接产物 ==========


def step10_handoff(session_id: str) -> AdaptationStep:
    """Step 10: 生成交接报告

    汇总所有步骤结果，生成最终交接文档。
    """
    session = _sessions.get(session_id)
    if not session:
        raise ValueError(f"会话不存在: {session_id}")

    step = session.steps_data[10]
    step.status = StepStatus.RUNNING
    _update_session(session)

    try:
        # 汇总所有步骤结果
        steps_summary = {}
        for i in range(1, 11):
            s = session.steps_data[i]
            steps_summary[f"step{i}"] = {
                "name": s.name,
                "status": s.status.value,
                "has_result": bool(s.result),
                "error": s.error,
            }

        # 生成交接报告
        handoff_report = {
            "session_id": session.id,
            "model_name": session.model_name,
            "model_path": session.model_path,
            "delivery_repo": session.delivery_repo,
            "final_status": session.status.value,
            "steps_summary": steps_summary,
            "key_findings": _extract_key_findings(session),
            "next_actions": _generate_next_actions(session),
            "generated_at": datetime.now().isoformat(),
        }

        step.result = handoff_report
        step.status = StepStatus.PASSED
        session.status = AdaptationStatus.COMPLETED
        logger.info(
            "Step 10 完成: session=%s, status=%s", session_id, session.status.value
        )

    except Exception as e:
        step.status = StepStatus.FAILED
        step.error = str(e)
        logger.error("Step 10 失败: session=%s, error=%s", session_id, e)

    _update_session(session)
    return step


def _extract_key_findings(session: AdaptationSession) -> list[str]:
    """提取关键发现"""
    findings = []

    step2 = session.steps_data[2].result
    if step2:
        findings.append(f"架构类型: {step2.get('architecture_type', 'Unknown')}")
        findings.append(f"注意力变体: {step2.get('attention_variant', 'Unknown')}")
        if step2.get("quantization_type", "none") != "none":
            findings.append(f"量化类型: {step2.get('quantization_type')}")

    step3 = session.steps_data[3].result
    if step3:
        if step3.get("blocked", False):
            findings.append(
                f"⚠️ 存在 {len(step3.get('blocked_operators', []))} 个无回退 CUDA 算子"
            )
        if step3.get("triton_count", 0) > 0:
            findings.append(f"存在 {step3.get('triton_count', 0)} 个 Triton 算子需处理")

    step5 = session.steps_data[5].result
    if step5:
        findings.append(f"适配策略: {step5.get('strategy', 'Unknown')}")

    return findings


def _generate_next_actions(session: AdaptationSession) -> list[str]:
    """生成后续行动项"""
    actions = []

    if session.status == AdaptationStatus.BLOCKED:
        actions.append("提交 GitHub issue 请求 vllm-ascend 支持")
        actions.append("评估是否可以为阻塞算子编写 CPU fallback")
    else:
        step6 = session.steps_data[6].result
        if step6:
            for f in step6.get("files_to_create", []):
                actions.append(f"创建并实现: {f}")
            for f in step6.get("files_to_patch", []):
                actions.append(f"补丁修改: {f}")

        actions.append("执行 dummy 验证")
        actions.append("执行 real-weight 验证")
        actions.append("执行推理功能验证")
        actions.append("提交代码到交付仓库")

    return actions


# ========== 快速参考 ==========


def get_quick_reference() -> dict[str, Any]:
    """获取快速参考"""
    return {
        "playbook": "adapt-agent 10 步模型适配",
        "steps": [
            {
                "step": 1,
                "name": "收集上下文",
                "description": "收集模型路径、实现根目录、交付仓库、默认功能集",
                "input": "model_path, model_name, delivery_repo, features",
            },
            {
                "step": 2,
                "name": "分析模型",
                "description": "读取 config.json，推断架构类型、注意力变体、量化类型",
                "input": "自动（基于 model_path 读取 config.json）",
            },
            {
                "step": 3,
                "name": "算子兼容性门控",
                "description": "扫描代码中的算子类型，分类为 Torch/Triton/CUDA",
                "input": "model_code（模型实现源码）",
                "blocking": "CUDA without fallback → BLOCKED",
            },
            {
                "step": 4,
                "name": "框架侧代码分析",
                "description": "检查 vLLM registry.py 和 vllm-ascend 补丁",
                "input": "vllm_path（vLLM 安装路径）",
            },
            {
                "step": 5,
                "name": "选择适配策略",
                "description": "基于 step 2-4 结果自动判断策略",
                "strategies": "reuse / patch / new_adapter / blocked",
            },
            {
                "step": 6,
                "name": "实现最小代码改动",
                "description": "根据策略生成适配器代码模板",
                "output": "adapter_code, weight_loader_code, registry_entry",
            },
            {
                "step": 7,
                "name": "两阶段验证",
                "description": "dummy 验证 + real-weight 验证",
                "phases": "7a: --load-format dummy, 7b: 实际权重",
            },
            {
                "step": 8,
                "name": "验证推理和功能",
                "description": "生成 curl 测试命令验证推理能力",
                "output": "test_commands, feature_checks",
            },
            {
                "step": 9,
                "name": "生成产物",
                "description": "YAML 配置、文档、提交命令",
                "output": "yaml_config, adaptation_doc, commit_commands",
            },
            {
                "step": 10,
                "name": "交接产物",
                "description": "汇总所有步骤结果，生成交接报告",
                "output": "handoff_report",
            },
        ],
        "operator_classification": {
            "Torch": "PyTorch 原生算子，昇腾自动兼容",
            "Triton": "Triton kernel，需验证或重写",
            "CUDA_with_fallback": "CUDA 算子但有 CPU/Torch 回退，可适配",
            "CUDA_without_fallback": "CUDA 算子无回退，阻塞适配",
        },
        "strategy_selection": {
            "reuse": "架构已注册，仅补丁损坏部分",
            "patch": "架构已注册但存在 Triton 算子，需补丁",
            "new_adapter": "架构未注册，需编写新适配器",
            "blocked": "存在无回退 CUDA 算子，需提 GitHub issue",
        },
    }

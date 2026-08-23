"""昇腾 NPU Profiling 采集与性能分析模块

支持 L0（最小膨胀）、L1（算子级）、L2（完整调用栈+内存）三个采集级别。
遵循 ascend-ai4s-profiling skill 规范：
- 默认采集 L0 级别
- 不修改训练/推理脚本中的 CUDA 代码
- 使用 torch_npu.profiler 采集
- 采集前设置性能优化环境变量
"""

import json
import logging
import os
import re
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("ascend_profiling")


def _py_literal(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


# 路径中禁止出现的字符：防止 shell 注入
_UNSAFE_PATH_CHARS = re.compile(r"[`;|$&!<>\n\r]")


def _validate_path_safety(path: str, field_name: str = "path") -> str:
    """校验路径安全性（防 shell 注入与空字节）"""
    if not path:
        return path  # 空路径由调用方决定是否允许
    if not isinstance(path, str):
        raise ValueError(f"{field_name} 必须是字符串")
    if "\x00" in path:
        raise ValueError(f"{field_name} 包含空字节")
    if _UNSAFE_PATH_CHARS.search(path):
        raise ValueError(f"{field_name} 包含禁止字符: {path!r}")
    return path


class ProfilingLevel(Enum):
    """Profiling 采集级别"""

    L0 = "L0"  # 仅 NPU 活动，最小膨胀
    L1 = "L1"  # CPU + NPU + 算子详情
    L2 = "L2"  # L1 + 调用栈 + 内存


class ProfilingScenario(Enum):
    """采集场景"""

    TRAINING = "training"
    INFERENCE = "inference"


@dataclass
class ProfilingConfig:
    """Profiling 采集配置"""

    level: ProfilingLevel = ProfilingLevel.L0
    scenario: ProfilingScenario = ProfilingScenario.INFERENCE
    output_dir: str = "./profiling_output"

    # schedule 参数（训练场景）
    skip_first: int = 20  # 跳过初始迭代
    wait: int = 1  # 等待步数
    warmup: int = 1  # 预热步数
    active: int = 1  # 实际记录步数
    repeat: int = 1  # 重复轮数

    # 推理场景参数
    num_inference_steps: int = 5  # 推理采集步数

    # L1/L2 参数
    record_shapes: bool = True
    with_stack: bool = False  # L2 时自动开启
    profile_memory: bool = False  # L2 时自动开启

    # 环境变量
    cpu_affinity: int = 1
    task_queue_enable: int = 2

    def __post_init__(self):
        if self.level == ProfilingLevel.L2:
            self.with_stack = True
            self.profile_memory = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level.value,
            "scenario": self.scenario.value,
            "output_dir": self.output_dir,
            "skip_first": self.skip_first,
            "wait": self.wait,
            "warmup": self.warmup,
            "active": self.active,
            "repeat": self.repeat,
            "record_shapes": self.record_shapes,
            "with_stack": self.with_stack,
            "profile_memory": self.profile_memory,
        }


@dataclass
class ProfilingResult:
    """Profiling 采集结果"""

    config: ProfilingConfig
    output_dir: str = ""
    status: str = "pending"  # pending / running / completed / failed
    error: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    duration_seconds: float = 0.0
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": self.config.to_dict(),
            "output_dir": self.output_dir,
            "status": self.status,
            "error": self.error,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "summary": self.summary,
        }


def setup_profiling_env(config: ProfilingConfig) -> dict[str, str]:
    """设置 Profiling 前的环境变量

    遵循 skill 规范：
    - CPU_AFFINITY_CONF: 绑核，减少调度抖动
    - TASK_QUEUE_ENABLE: Host-Device 异步流水
    """
    env_vars = {
        "CPU_AFFINITY_CONF": str(config.cpu_affinity),
        "TASK_QUEUE_ENABLE": str(config.task_queue_enable),
    }

    for key, value in env_vars.items():
        os.environ[key] = value
        logger.info(f"环境变量: {key}={value}")

    return env_vars


def build_profiler_kwargs(config: ProfilingConfig) -> dict[str, Any]:
    """构建 torch_npu.profiler.profile() 参数

    根据采集级别自动组装参数：
    - L0: 仅 NPU 活动
    - L1: CPU + NPU + record_shapes + ProfilerLevel.Level1
    - L2: L1 + with_stack + profile_memory
    """
    try:
        import torch_npu.profiler
    except ImportError:
        raise RuntimeError("torch_npu 未安装，无法使用 Profiling 功能")

    kwargs: dict[str, Any] = {}

    # activities — 根据级别决定
    if config.level == ProfilingLevel.L0:
        kwargs["activities"] = [torch_npu.profiler.ProfilerActivity.NPU]
    else:
        # L1/L2 采集 CPU + NPU
        kwargs["activities"] = [
            torch_npu.profiler.ProfilerActivity.CPU,
            torch_npu.profiler.ProfilerActivity.NPU,
        ]

    # schedule — 训练和推理通用
    kwargs["schedule"] = torch_npu.profiler.schedule(
        wait=config.wait,
        warmup=config.warmup,
        active=config.active,
        repeat=config.repeat,
        skip_first=config.skip_first,
    )

    # on_trace_ready
    output_path = os.path.join(
        config.output_dir,
        f"npu-profiling-{config.level.value}-{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    )
    kwargs["on_trace_ready"] = torch_npu.profiler.tensorboard_trace_handler(output_path)

    # L1/L2 专有参数
    if config.level in (ProfilingLevel.L1, ProfilingLevel.L2):
        kwargs["record_shapes"] = config.record_shapes
        kwargs["with_stack"] = config.with_stack
        kwargs["profile_memory"] = config.profile_memory
        kwargs["experimental_config"] = torch_npu.profiler._ExperimentalConfig(
            profiler_level=torch_npu.profiler.ProfilerLevel.Level1
        )

    return kwargs, output_path


def generate_profiling_script(
    config: ProfilingConfig,
    user_script_path: str = "",
    output_script_path: str = "",
) -> str:
    """生成完整的 Profiling 采集脚本

    根据场景和级别生成可直接运行的 Python 脚本。
    不修改用户代码中的 CUDA 调用（skill 规范）。

    Args:
        config: Profiling 配置
        user_script_path: 用户训练/推理脚本路径（可选，用于注释提示）
        output_script_path: 输出脚本路径（可选，默认 auto）

    Returns:
        生成的脚本内容
    """
    # 校验用户输入路径
    _validate_path_safety(user_script_path, "user_script_path")
    _validate_path_safety(output_script_path, "output_script_path")
    _validate_path_safety(config.output_dir, "config.output_dir")

    level = config.level.value
    scenario = config.scenario.value

    # 环境变量设置
    env_block = f"""
# ========== 环境变量（采集前必设） ==========
import os
os.environ['CPU_AFFINITY_CONF'] = '{config.cpu_affinity}'   # CPU 绑核
os.environ['TASK_QUEUE_ENABLE'] = '{config.task_queue_enable}'  # Host-Device 异步流水
"""

    # import 块
    import_block = """
# ========== 导入 ==========
import torch
import torch_npu
"""

    # 级别标签
    level_desc = {
        "L0": "最小膨胀（仅 NPU 活动）",
        "L1": "算子级（CPU + NPU + 算子详情）",
        "L2": "完整调用栈 + 内存",
    }

    header = f'''"""
昇腾 NPU Profiling 采集脚本
- 级别: {level} — {level_desc.get(level, "")}
- 场景: {scenario}
- 生成时间: {datetime.now().isoformat()}

⚠️ 注意：不要修改训练/推理脚本中的 CUDA 代码。
   torch_npu 的自动迁移（transfer_to_npu）会在运行时将 CUDA 调用转为 NPU 调用。
   Profiling 代码使用 torch_npu.profiler 是必要的，但业务代码保持原样即可。
"""
'''

    if scenario == "training":
        body = _generate_training_body(config)
    else:
        body = _generate_inference_body(config)

    script = header + env_block + import_block + body

    # 写入文件
    if output_script_path:
        os.makedirs(os.path.dirname(output_script_path) or ".", exist_ok=True)
        with open(output_script_path, "w", encoding="utf-8") as f:
            f.write(script)
        logger.info(f"Profiling 脚本已保存: {output_script_path}")

    return script


def _generate_training_body(config: ProfilingConfig) -> str:
    """生成训练场景的 Profiling 代码体"""
    level = config.level.value

    if level == "L0":
        activities = "[torch_npu.profiler.ProfilerActivity.NPU]"
        extra_params = ""
    elif level == "L1":
        activities = (
            "[\n        torch_npu.profiler.ProfilerActivity.CPU,\n"
            "        torch_npu.profiler.ProfilerActivity.NPU,\n    ]"
        )
        extra_params = """    record_shapes=True,
    with_stack=False,
    profile_memory=False,
    experimental_config=torch_npu.profiler._ExperimentalConfig(
        profiler_level=torch_npu.profiler.ProfilerLevel.Level1
    ),"""
    else:  # L2
        activities = (
            "[\n        torch_npu.profiler.ProfilerActivity.CPU,\n"
            "        torch_npu.profiler.ProfilerActivity.NPU,\n    ]"
        )
        extra_params = """    record_shapes=True,
    with_stack=True,
    profile_memory=True,
    experimental_config=torch_npu.profiler._ExperimentalConfig(
        profiler_level=torch_npu.profiler.ProfilerLevel.Level1
    ),"""

    return f"""
# ========== 训练场景 Profiling ==========
# 请将下方的 train_dataloader 和 train_one_step 替换为你的实际训练循环

output_dir = {_py_literal(f"{config.output_dir}/npu-profiling-{level}")}

with torch_npu.profiler.profile(
    activities={activities},
    schedule=torch_npu.profiler.schedule(
        wait={config.wait},
        warmup={config.warmup},
        active={config.active},
        repeat={config.repeat},
        skip_first={config.skip_first},
    ),
{extra_params}
    on_trace_ready=torch_npu.profiler.tensorboard_trace_handler(output_dir),
) as prof:
    # === 替换为你的训练循环 ===
    for step, batch in enumerate(train_dataloader):
        train_one_step(batch)
        prof.step()
    # === 替换结束 ===

print(f"Profiling 数据已保存到: {{output_dir}}")
print(f"使用 TensorBoard 查看: tensorboard --logdir={{output_dir}}")
"""


def _generate_inference_body(config: ProfilingConfig) -> str:
    """生成推理场景的 Profiling 代码体"""
    level = config.level.value

    if level == "L0":
        activities = "[torch_npu.profiler.ProfilerActivity.NPU]"
        extra_params = ""
    elif level == "L1":
        activities = (
            "[\n        torch_npu.profiler.ProfilerActivity.CPU,\n"
            "        torch_npu.profiler.ProfilerActivity.NPU,\n    ]"
        )
        extra_params = """    record_shapes=True,
    with_stack=False,
    profile_memory=False,
    experimental_config=torch_npu.profiler._ExperimentalConfig(
        profiler_level=torch_npu.profiler.ProfilerLevel.Level1
    ),"""
    else:  # L2
        activities = (
            "[\n        torch_npu.profiler.ProfilerActivity.CPU,\n"
            "        torch_npu.profiler.ProfilerActivity.NPU,\n    ]"
        )
        extra_params = """    record_shapes=True,
    with_stack=True,
    profile_memory=True,
    experimental_config=torch_npu.profiler._ExperimentalConfig(
        profiler_level=torch_npu.profiler.ProfilerLevel.Level1
    ),"""

    return f"""
# ========== 推理场景 Profiling ==========
# 请将下方的 model 和 input_data 替换为你的实际推理代码

output_dir = {_py_literal(f"{config.output_dir}/npu-profiling-{level}")}

with torch_npu.profiler.profile(
    activities={activities},
{extra_params}
    on_trace_ready=torch_npu.profiler.tensorboard_trace_handler(output_dir),
) as prof:
    # === 替换为你的推理代码 ===
    for i in range({config.num_inference_steps}):
        output = model(input_data)
        prof.step()
    # === 替换结束 ===

print(f"Profiling 数据已保存到: {{output_dir}}")
print(f"使用 TensorBoard 查看: tensorboard --logdir={{output_dir}}")
"""


def generate_gpu_comparison_script(
    output_dir: str = "./gpu-profiling-output",
    skip_first: int = 20,
    wait: int = 1,
    warmup: int = 1,
    active: int = 1,
    repeat: int = 1,
) -> str:
    """生成 GPU 对比采集脚本

    GPU 采集使用原生 torch.profiler，与 NPU 的区别：
    1. 使用 torch.profiler.profile 而非 torch_npu.profiler.profile
    2. 使用 torch.profiler.ProfilerActivity.CUDA 而非 NPU
    3. 不使用 experimental_config 参数
    """
    script = f'''"""
GPU 对比 Profiling 采集脚本
用于 GPU vs NPU 性能对比，使用相同 schedule 配置。

⚠️ GPU 采集使用原生 torch.profiler，不使用 experimental_config。
"""

import torch

output_dir = {_py_literal(output_dir)}

with torch.profiler.profile(
    activities=[torch.profiler.ProfilerActivity.CUDA],
    schedule=torch.profiler.schedule(
        wait={wait},
        warmup={warmup},
        active={active},
        repeat={repeat},
        skip_first={skip_first},
    ),
    on_trace_ready=torch.profiler.tensorboard_trace_handler(output_dir),
) as prof:
    # === 替换为你的训练循环 ===
    for step, batch in enumerate(train_dataloader):
        train_one_step(batch)
        prof.step()
    # === 替换结束 ===

print(f"GPU Profiling 数据已保存到: {{output_dir}}")
print(f"使用 TensorBoard 查看: tensorboard --logdir={{output_dir}}")
'''
    return script


def generate_lightning_callback(
    output_dir: str = "./npu-profiling",
    level: str = "L0",
    skip_first: int = 20,
) -> str:
    """生成 PyTorch Lightning Profiling Callback"""
    return f'''
import torch
import torch_npu
import pytorch_lightning as pl


class NPUProfilingCallback(pl.Callback):
    """昇腾 NPU Profiling 回调，支持 L0/L1/L2 级别切换。"""

    def __init__(self, output_dir={_py_literal(output_dir)}, level={_py_literal(level)},
                 skip_first={skip_first}, wait=1, warmup=1, active=1, repeat=1):
        super().__init__()
        self.output_dir = output_dir
        self.level = level
        self.skip_first = skip_first
        self.wait = wait
        self.warmup = warmup
        self.active = active
        self.repeat = repeat
        self.prof = None

    def _build_profile_kwargs(self):
        kwargs = {{
            "activities": [torch_npu.profiler.ProfilerActivity.NPU],
            "schedule": torch_npu.profiler.schedule(
                wait=self.wait, warmup=self.warmup,
                active=self.active, repeat=self.repeat,
                skip_first=self.skip_first,
            ),
            "on_trace_ready": torch_npu.profiler.tensorboard_trace_handler(
                self.output_dir
            ),
        }}
        if self.level in ("L1", "L2"):
            kwargs["activities"].insert(
                0, torch_npu.profiler.ProfilerActivity.CPU
            )
            kwargs["record_shapes"] = True
            kwargs["experimental_config"] = (
                torch_npu.profiler._ExperimentalConfig(
                    profiler_level=torch_npu.profiler.ProfilerLevel.Level1
                )
            )
        if self.level == "L2":
            kwargs["with_stack"] = True
            kwargs["profile_memory"] = True
        return kwargs

    def on_train_start(self, trainer, pl_module):
        self.prof = torch_npu.profiler.profile(**self._build_profile_kwargs())
        self.prof.start()

    def on_train_batch_end(self, trainer, pl_module, outputs, batch, batch_idx):
        if self.prof is not None:
            torch.npu.synchronize()
            self.prof.step()

    def on_train_end(self, trainer, pl_module):
        if self.prof is not None:
            self.prof.stop()
            self.prof = None
'''


def generate_hf_trainer_callback(
    output_dir: str = "./npu-profiling",
    skip_first: int = 20,
) -> str:
    """生成 HuggingFace Transformers Trainer Profiling Callback"""
    return f"""
import torch
import torch_npu
from transformers import TrainerCallback


class NPUProfilingTrainerCallback(TrainerCallback):

    def __init__(self, output_dir={_py_literal(output_dir)}, skip_first={skip_first}):
        self.output_dir = output_dir
        self.skip_first = skip_first
        self.prof = None

    def on_train_begin(self, args, state, control, **kwargs):
        self.prof = torch_npu.profiler.profile(
            activities=[torch_npu.profiler.ProfilerActivity.NPU],
            schedule=torch_npu.profiler.schedule(
                wait=1, warmup=1, active=1, repeat=1,
                skip_first=self.skip_first,
            ),
            on_trace_ready=torch_npu.profiler.tensorboard_trace_handler(
                self.output_dir
            ),
        )
        self.prof.start()

    def on_step_end(self, args, state, control, **kwargs):
        if self.prof is not None:
            torch.npu.synchronize()
            self.prof.step()

    def on_train_end(self, args, state, control, **kwargs):
        if self.prof is not None:
            self.prof.stop()
            self.prof = None
"""


def generate_deepspeed_script(
    output_dir: str = "./npu-profiling-deepspeed",
    skip_first: int = 20,
    wait: int = 1,
    warmup: int = 1,
    active: int = 1,
    repeat: int = 1,
) -> str:
    """生成 DeepSpeed 多卡 Profiling 采集脚本

    遵循 skill 4.3 节规范：
    - prof.step() 在 model_engine.step() 之后调用
    - 多卡场景仅在 rank 0 上采集以减少数据量
    """
    _validate_path_safety(output_dir, "output_dir")
    return f'''"""
DeepSpeed 多卡 Profiling 采集脚本
- 仅在 rank 0 上采集以减少数据量
- prof.step() 必须在 model_engine.step() 之后调用

⚠️ 不要修改训练/推理脚本中的 CUDA 代码，torch_npu 自动迁移会在运行时转换。
"""

import os
import torch
import torch_npu

local_rank = int(os.environ.get("LOCAL_RANK", 0))

output_dir = {_py_literal(output_dir)}

if local_rank == 0:
    prof = torch_npu.profiler.profile(
        activities=[torch_npu.profiler.ProfilerActivity.NPU],
        schedule=torch_npu.profiler.schedule(
            wait={wait},
            warmup={warmup},
            active={active},
            repeat={repeat},
            skip_first={skip_first},
        ),
        on_trace_ready=torch_npu.profiler.tensorboard_trace_handler(output_dir),
    )
    prof.start()

for step, batch in enumerate(train_dataloader):
    loss = model_engine(batch)
    model_engine.backward(loss)
    model_engine.step()
    if local_rank == 0:
        prof.step()

if local_rank == 0:
    prof.stop()
    print(f"DeepSpeed Profiling 数据已保存到: {{output_dir}}")
    print(f"使用 TensorBoard 查看: tensorboard --logdir={{output_dir}}")
'''


# ========== 实际执行 Profiling 采集 ==========

# 全局任务状态（线程安全）
_profiling_lock = threading.Lock()
_current_process: subprocess.Popen | None = None


def _build_run_command(
    level: str,
    target: str,
    output_dir: str,
    num_steps: int,
) -> list[str]:
    """构建 Profiling 采集命令

    使用项目内 scripts/run_profiling.py（若存在），否则回退到内联 Python。
    """
    # 校验 level 合法性
    valid_levels = {"L0", "L1", "L2"}
    if level not in valid_levels:
        raise ValueError(f"无效的采集级别: {level}，合法值: {valid_levels}")

    _validate_path_safety(output_dir, "output_dir")
    _validate_path_safety(target, "target")

    # 优先使用项目脚本
    project_script = Path("scripts/run_profiling.py")
    if project_script.exists():
        return [
            "python",
            str(project_script),
            "--level",
            level,
            "--target",
            target,
            "--output-dir",
            output_dir,
            "--num-steps",
            str(num_steps),
        ]

    # 回退：内联 Python 采集 — 使用 sys.argv 传参，避免 f-string 注入
    inline_script = r"""
import os, sys, json

# 路径通过命令行参数传入，避免代码注入
output_dir = sys.argv[1]
level = sys.argv[2]
num_steps = int(sys.argv[3])

os.environ['CPU_AFFINITY_CONF'] = '1'
os.environ['TASK_QUEUE_ENABLE'] = '2'
os.makedirs(output_dir, exist_ok=True)

try:
    import torch, torch_npu
    from datetime import datetime
    out = os.path.join(
        output_dir,
        f'npu-profiling-{level}-'
        + datetime.now().strftime('%Y%m%d_%H%M%S'),
    )
    activities = [torch_npu.profiler.ProfilerActivity.NPU]
    if level in ('L1', 'L2'):
        activities.insert(0, torch_npu.profiler.ProfilerActivity.CPU)
    kwargs = {}
    if level in ('L1', 'L2'):
        kwargs['record_shapes'] = True
        kwargs['experimental_config'] = torch_npu.profiler._ExperimentalConfig(
            profiler_level=torch_npu.profiler.ProfilerLevel.Level1
        )
    if level == 'L2':
        kwargs['with_stack'] = True
        kwargs['profile_memory'] = True
    with torch_npu.profiler.profile(
        activities=activities,
        schedule=torch_npu.profiler.schedule(
            wait=1, warmup=1, active=1, repeat=1, skip_first=20
        ),
        on_trace_ready=torch_npu.profiler.tensorboard_trace_handler(out),
        **kwargs
    ) as prof:
        for i in range(num_steps):
            prof.step()
    print(json.dumps({'status': 'completed', 'output_dir': out}))
except Exception as e:
    print(json.dumps({'status': 'failed', 'error': str(e)}))
    sys.exit(1)
"""
    return ["python", "-c", inline_script, output_dir, level, str(num_steps)]


def execute_profiling(
    level: str,
    target: str,
    output_dir: str,
    num_steps: int,
    timeout: int = 600,
) -> dict[str, Any]:
    """实际执行 Profiling 采集

    在后台线程中启动子进程，立即返回任务句柄。
    状态通过 query_profiling_status() 轮询。

    Returns:
        包含 pid 和初始状态的字典
    """
    global _current_process

    with _profiling_lock:
        if _current_process is not None and _current_process.poll() is None:
            raise RuntimeError("已有 Profiling 任务正在运行")

        # 设置环境变量
        os.environ["CPU_AFFINITY_CONF"] = "1"
        os.environ["TASK_QUEUE_ENABLE"] = "2"

        # 确保输出目录存在
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        cmd = _build_run_command(level, target, output_dir, num_steps)
        logger.info(
            f"启动 Profiling 采集: {' '.join(cmd[:2])} ... "
            f"(level={level}, target={target})"
        )

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            _current_process = proc
        except FileNotFoundError as e:
            raise RuntimeError(f"无法启动 Python 进程: {e}")

    return {
        "pid": proc.pid,
        "level": level,
        "target": target,
        "output_dir": output_dir,
        "num_steps": num_steps,
        "status": "running",
        "start_time": datetime.now().isoformat(),
        "timeout": timeout,
    }


def query_profiling_status() -> dict[str, Any]:
    """查询当前 Profiling 任务状态"""
    global _current_process

    with _profiling_lock:
        if _current_process is None:
            return {"status": "idle", "message": "无运行中的任务"}

        proc = _current_process
        returncode = proc.poll()

        if returncode is None:
            return {
                "status": "running",
                "pid": proc.pid,
                "message": "采集进行中",
            }

        # 任务结束，读取输出
        stdout, stderr = proc.communicate(timeout=5)
        _current_process = None

        if returncode == 0:
            # 尝试从 stdout 解析状态
            result = {"status": "completed", "returncode": 0}
            for line in (stdout or "").splitlines():
                line = line.strip()
                if line.startswith("{") and "status" in line:
                    try:
                        parsed = json.loads(line)
                        result.update(parsed)
                    except json.JSONDecodeError:
                        pass
            result["stdout"] = (stdout or "")[-2000:]
            return result
        else:
            return {
                "status": "failed",
                "returncode": returncode,
                "stdout": (stdout or "")[-2000:],
                "stderr": (stderr or "")[-2000:],
                "message": f"采集失败，退出码 {returncode}",
            }


def stop_profiling() -> dict[str, Any]:
    """终止当前 Profiling 任务"""
    global _current_process

    with _profiling_lock:
        if _current_process is None:
            return {"status": "idle", "message": "无运行中的任务"}

        proc = _current_process
        try:
            import signal

            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            _current_process = None
            return {"status": "terminated", "message": "任务已终止"}
        except ProcessLookupError:
            _current_process = None
            return {"status": "idle", "message": "进程已退出"}


def scan_profiling_results(
    output_dir: str = "./profiling_output",
) -> list[dict[str, Any]]:
    """扫描文件系统中的 Profiling 采集结果

    遵循 skill 规范：读取真实文件系统而非内存列表。
    """
    _validate_path_safety(output_dir, "output_dir")
    root = Path(output_dir)
    if not root.exists():
        return []

    results = []
    for entry in sorted(
        root.iterdir(),
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
        reverse=True,
    ):
        if not entry.is_dir():
            continue
        if not entry.name.startswith("npu-profiling-") and not entry.name.startswith(
            "gpu-profiling-"
        ):
            continue

        stat = entry.stat()
        # 统计目录内文件
        file_count = 0
        total_size = 0
        trace_files = []
        for f in entry.rglob("*"):
            if f.is_file():
                file_count += 1
                total_size += f.stat().st_size
                if f.suffix in (".json", ".trace", ".pb"):
                    trace_files.append(str(f))

        results.append(
            {
                "name": entry.name,
                "path": str(entry),
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "file_count": file_count,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "trace_files": trace_files[:10],  # 限制返回数量
            }
        )

    return results

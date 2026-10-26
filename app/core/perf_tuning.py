"""昇腾 NPU 通用性能调优模块

遵循 ascend-ai4s-perf-tuning skill 规范：
- 渐进式调优：流水优化 → 绑核优化 → tcmalloc 替换，逐项开启
- 负优化回退：某项叠加后性能不升反降，应去掉该项
- 编译优化为进阶手段：需用户确认后才执行
- 配合 Profiling 使用：调优前后各采集一次 L0 Profiling

调优层次：
    1. 流水优化（TASK_QUEUE_ENABLE）
    2. CPU 绑核优化（CPU_AFFINITY_CONF）
    3. 高性能内存库替换（tcmalloc / LD_PRELOAD）
    4. 内存分配策略（PYTORCH_NPU_ALLOC_CONF）
    5. [进阶] Python 编译优化（毕昇编译器 + LTO + PGO）
    6. [进阶] PyTorch 编译优化（毕昇编译器 + LTO + PGO）
    7. [进阶] torch_npu 编译优化（毕昇编译器 + LTO + PGO）
"""

import logging
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger("ascend_perf_tuning")


# ========== 枚举与数据结构 ==========


class TuningLevel(Enum):
    """调优级别"""

    PIPELINE = "pipeline"
    CPU_AFFINITY = "cpu_affinity"
    TCMALLOC = "tcmalloc"
    ALLOC_CONF = "alloc_conf"
    COMPILE_PYTHON = "compile_python"
    COMPILE_TORCH = "compile_torch"
    COMPILE_TORCH_NPU = "compile_torch_npu"


class AffinityMode(Enum):
    """CPU 绑核模式"""

    DISABLED = 0
    COARSE = 1
    FINE = 2


class TaskQueueMode(Enum):
    """流水优化模式"""

    DISABLED = 0
    ENABLED = 1
    ENHANCED = 2


class AllocStrategy(Enum):
    """内存分配策略"""

    OFF = "off"
    EXPANDABLE_SEGMENTS = "expandable_segments"


@dataclass
class TuningConfig:
    """调优配置

    遵循渐进式调优原则，每个优化项可独立开关。
    """

    # 流水优化
    task_queue_enable: TaskQueueMode = TaskQueueMode.ENHANCED
    # CPU 绑核
    cpu_affinity_mode: AffinityMode = AffinityMode.DISABLED
    cpu_affinity_custom: str = ""
    # tcmalloc
    tcmalloc_enabled: bool = False
    tcmalloc_path: str = ""
    # 内存分配策略
    alloc_strategy: AllocStrategy = AllocStrategy.EXPANDABLE_SEGMENTS
    # ACL Graph 加速
    enable_acl_graph: bool = True
    # OMP_PROC_BIND（编译优化后使用）
    omp_proc_bind: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_queue_enable": self.task_queue_enable.value,
            "cpu_affinity_mode": self.cpu_affinity_mode.value,
            "cpu_affinity_custom": self.cpu_affinity_custom,
            "tcmalloc_enabled": self.tcmalloc_enabled,
            "tcmalloc_path": self.tcmalloc_path,
            "alloc_strategy": self.alloc_strategy.value,
            "enable_acl_graph": self.enable_acl_graph,
            "omp_proc_bind": self.omp_proc_bind,
        }


@dataclass
class TuningResult:
    """单项调优结果"""

    tuning_level: str
    config_applied: dict[str, Any]
    status: str = "pending"
    baseline_metric: float | None = None
    optimized_metric: float | None = None
    improvement_pct: float | None = None
    error: str | None = None
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tuning_level": self.tuning_level,
            "config_applied": self.config_applied,
            "status": self.status,
            "baseline_metric": self.baseline_metric,
            "optimized_metric": self.optimized_metric,
            "improvement_pct": self.improvement_pct,
            "error": self.error,
            "timestamp": self.timestamp,
        }


@dataclass
class TuningReport:
    """完整调优报告"""

    config: TuningConfig
    results: list[TuningResult] = field(default_factory=list)
    baseline_time: str | None = None
    final_time: str | None = None
    total_improvement_pct: float | None = None
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": self.config.to_dict(),
            "results": [r.to_dict() for r in self.results],
            "baseline_time": self.baseline_time,
            "final_time": self.final_time,
            "total_improvement_pct": self.total_improvement_pct,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
        }


# ========== 环境变量应用 ==========


def apply_tuning_env(config: TuningConfig) -> dict[str, str]:
    """应用调优环境变量

    按照渐进式调优原则，仅应用已启用的优化项。
    返回实际设置的环境变量字典。
    """
    applied = {}

    # 1. 流水优化
    tq_value = str(config.task_queue_enable.value)
    os.environ["TASK_QUEUE_ENABLE"] = tq_value
    applied["TASK_QUEUE_ENABLE"] = tq_value
    logger.info(f"流水优化: TASK_QUEUE_ENABLE={tq_value}")

    # 2. CPU 绑核
    if config.cpu_affinity_mode != AffinityMode.DISABLED:
        if config.cpu_affinity_custom:
            affinity_value = (
                f"{config.cpu_affinity_mode.value},{config.cpu_affinity_custom}"
            )
        else:
            affinity_value = str(config.cpu_affinity_mode.value)
        os.environ["CPU_AFFINITY_CONF"] = affinity_value
        applied["CPU_AFFINITY_CONF"] = affinity_value
        logger.info(f"CPU 绑核: CPU_AFFINITY_CONF={affinity_value}")

    # 3. tcmalloc
    if config.tcmalloc_enabled and config.tcmalloc_path:
        existing_preload = os.environ.get("LD_PRELOAD", "")
        if config.tcmalloc_path not in existing_preload:
            new_preload = f"{existing_preload}:{config.tcmalloc_path}".lstrip(":")
            os.environ["LD_PRELOAD"] = new_preload
            applied["LD_PRELOAD"] = new_preload
            logger.info(f"tcmalloc: LD_PRELOAD 包含 {config.tcmalloc_path}")

    # 4. 内存分配策略
    if config.alloc_strategy != AllocStrategy.OFF:
        alloc_value = config.alloc_strategy.value
        os.environ["PYTORCH_NPU_ALLOC_CONF"] = alloc_value
        applied["PYTORCH_NPU_ALLOC_CONF"] = alloc_value
        logger.info(f"内存分配: PYTORCH_NPU_ALLOC_CONF={alloc_value}")

    # 5. ACL Graph
    if config.enable_acl_graph:
        os.environ["ASCEND_ENABLE_ACL_GRAPH"] = "1"
        applied["ASCEND_ENABLE_ACL_GRAPH"] = "1"

    # 6. OMP_PROC_BIND
    if not config.omp_proc_bind:
        os.environ["OMP_PROC_BIND"] = "false"
        applied["OMP_PROC_BIND"] = "false"

    return applied


# ========== tcmalloc 检测 ==========


def detect_tcmalloc() -> dict[str, Any]:
    """检测 tcmalloc 是否已安装

    搜索常见路径，返回检测到的 libtcmalloc.so 路径。
    """
    result = {
        "installed": False,
        "path": "",
        "method": "",
    }

    common_paths = [
        "/usr/lib64/libtcmalloc.so",
        "/usr/lib/libtcmalloc.so",
        "/usr/lib/x86_64-linux-gnu/libtcmalloc.so",
        "/usr/local/lib/lib/libtcmalloc.so",
        "/usr/local/lib/libtcmalloc.so",
    ]

    for path in common_paths:
        if os.path.exists(path):
            result["installed"] = True
            result["path"] = path
            result["method"] = "系统路径搜索"
            return result

    # rpm 查询
    try:
        output = subprocess.run(
            ["rpm", "-ql", "gperftools-libs"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if output.returncode == 0:
            for line in output.stdout.splitlines():
                if "libtcmalloc.so" in line and not line.endswith(".debug"):
                    result["installed"] = True
                    result["path"] = line.strip()
                    result["method"] = "rpm 查询"
                    return result
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # ldconfig
    try:
        output = subprocess.run(
            ["ldconfig", "-p"], capture_output=True, text=True, timeout=10
        )
        if output.returncode == 0:
            for line in output.stdout.splitlines():
                if "libtcmalloc.so" in line:
                    parts = line.strip().split("=>")
                    if len(parts) == 2:
                        path = parts[1].strip()
                        if os.path.exists(path):
                            result["installed"] = True
                            result["path"] = path
                            result["method"] = "ldconfig 查询"
                            return result
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return result


def install_tcmalloc_instructions() -> str:
    """返回 tcmalloc 安装指引"""
    lines = [
        "# 方法一：系统包管理器安装（推荐）",
        "#",
        "# openEuler",
        "yum install gperftools",
        "#",
        "# CentOS",
        "yum install gperftools gperftools-devel",
        "#",
        "# Ubuntu",
        "sudo apt update",
        "sudo apt install libgoogle-perftools4 libgoogle-perftools-dev",
        "",
        "# 方法二：源码编译安装（需先安装 libunwind）",
        "wget https://github.com/gperftools/gperftools/releases/download/gperftools-2.16/gperftools-2.16.tar.gz",
        "tar -xf gperftools-2.16.tar.gz && cd gperftools-2.16",
        "./configure --prefix=/usr/local/lib --with-tcmalloc-pagesize=64",
        "make",
        "make install",
        "",
        "# 使能方法",
        'export LD_PRELOAD="$LD_PRELOAD:/usr/local/lib/lib/libtcmalloc.so"',
    ]
    return "\n".join(lines)


# ========== NUMA 拓扑检测 ==========


def detect_numa_topology() -> dict[str, Any]:
    """检测 NUMA 拓扑，用于确定 CPU 绑核的最佳配置。"""
    result: dict[str, Any] = {
        "available": False,
        "nodes": [],
        "cpu_count": 0,
        "npu_to_numa": {},
        "numa_info": [],
    }

    try:
        output = subprocess.run(["lscpu"], capture_output=True, text=True, timeout=10)
        if output.returncode == 0:
            result["available"] = True
            for line in output.stdout.splitlines():
                if "NUMA" in line.upper() or "CPU(s):" in line:
                    result["numa_info"].append(line.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    try:
        result["cpu_count"] = os.cpu_count() or 0
    except Exception:
        pass

    return result


# ========== 渐进式调优执行器 ==========


class ProgressiveTuningExecutor:
    """渐进式调优执行器

    遵循 skill 规范：
    - 按"流水优化 → 绑核优化 → tcmalloc 替换"的顺序逐项开启
    - 每次只变更一个配置，观察性能变化后再叠加下一项
    - 如果某项优化叠加后性能不升反降，应将其去掉
    """

    def __init__(self, config: TuningConfig):
        self.config = config
        self.report = TuningReport(config=config)
        self.applied_env: dict[str, str] = {}

    def run_all_basic(self) -> TuningReport:
        """执行基础调优（1-3 级：流水 → 绑核 → tcmalloc）"""
        self.report.baseline_time = datetime.now().isoformat()

        self._apply_pipeline()
        self._apply_cpu_affinity()
        self._apply_tcmalloc()
        self._apply_alloc_conf()

        self.report.final_time = datetime.now().isoformat()
        self._generate_recommendations()

        return self.report

    def _apply_pipeline(self) -> TuningResult:
        """应用流水优化"""
        result = TuningResult(
            tuning_level=TuningLevel.PIPELINE.value,
            config_applied={"TASK_QUEUE_ENABLE": self.config.task_queue_enable.value},
            timestamp=datetime.now().isoformat(),
        )

        try:
            env = apply_tuning_env(self.config)
            self.applied_env.update(env)
            result.status = "applied"
            result.config_applied = {
                "TASK_QUEUE_ENABLE": self.config.task_queue_enable.value,
            }

            if self.config.task_queue_enable == TaskQueueMode.ENHANCED:
                self.report.warnings.append(
                    "TASK_QUEUE_ENABLE=2 增强模式可能导致 NPU 内存峰值上升，"
                    "如遇 OOM 请减小 batch_size 或回退到 TASK_QUEUE_ENABLE=1"
                )

            if os.environ.get("ASCEND_LAUNCH_BLOCKING") == "1":
                self.report.warnings.append(
                    "ASCEND_LAUNCH_BLOCKING=1 时 task_queue 算子队列关闭，"
                    "TASK_QUEUE_ENABLE 设置不生效"
                )

        except Exception as e:
            result.status = "failed"
            result.error = str(e)

        self.report.results.append(result)
        return result

    def _apply_cpu_affinity(self) -> TuningResult:
        """应用 CPU 绑核优化"""
        result = TuningResult(
            tuning_level=TuningLevel.CPU_AFFINITY.value,
            config_applied={"CPU_AFFINITY_CONF": self.config.cpu_affinity_mode.value},
            timestamp=datetime.now().isoformat(),
        )

        if self.config.cpu_affinity_mode == AffinityMode.DISABLED:
            result.status = "skipped"
            result.config_applied = {"CPU_AFFINITY_CONF": "disabled (未启用)"}
            self.report.results.append(result)
            return result

        try:
            env = apply_tuning_env(self.config)
            self.applied_env.update(env)

            if self.config.cpu_affinity_custom:
                affinity_str = (
                    f"{self.config.cpu_affinity_mode.value},"
                    f"{self.config.cpu_affinity_custom}"
                )
            else:
                affinity_str = str(self.config.cpu_affinity_mode.value)

            result.status = "applied"
            result.config_applied = {"CPU_AFFINITY_CONF": affinity_str}

            mode_desc = {
                AffinityMode.COARSE: "粗粒度（绑定到 NPU 对应 NUMA 的全部 CPU 核心）",
                AffinityMode.FINE: "细粒度（锚定主要任务到固定 CPU 核心）",
            }
            result.config_applied["mode_description"] = mode_desc.get(
                self.config.cpu_affinity_mode, ""
            )

            self.report.warnings.append(
                "CPU 绑核对 vLLM 等自带多进程/多线程调度的推理框架可能产生负优化，"
                "建议先单独测试绑核效果，确认有正向收益后再保留"
            )

        except Exception as e:
            result.status = "failed"
            result.error = str(e)

        self.report.results.append(result)
        return result

    def _apply_tcmalloc(self) -> TuningResult:
        """应用 tcmalloc 内存库替换"""
        result = TuningResult(
            tuning_level=TuningLevel.TCMALLOC.value,
            config_applied={"tcmalloc_enabled": self.config.tcmalloc_enabled},
            timestamp=datetime.now().isoformat(),
        )

        if not self.config.tcmalloc_enabled:
            result.status = "skipped"
            result.config_applied = {"tcmalloc_enabled": False}
            self.report.results.append(result)
            return result

        if not self.config.tcmalloc_path:
            detection = detect_tcmalloc()
            if detection["installed"]:
                self.config.tcmalloc_path = detection["path"]
                result.config_applied["auto_detected_path"] = detection["path"]
                result.config_applied["detection_method"] = detection["method"]
            else:
                result.status = "failed"
                result.error = "tcmalloc 未安装，无法启用"
                result.config_applied["install_instructions"] = (
                    install_tcmalloc_instructions()
                )
                self.report.results.append(result)
                return result

        try:
            env = apply_tuning_env(self.config)
            self.applied_env.update(env)
            result.status = "applied"
            result.config_applied["LD_PRELOAD"] = self.config.tcmalloc_path

        except Exception as e:
            result.status = "failed"
            result.error = str(e)

        self.report.results.append(result)
        return result

    def _apply_alloc_conf(self) -> TuningResult:
        """应用内存分配策略"""
        result = TuningResult(
            tuning_level=TuningLevel.ALLOC_CONF.value,
            config_applied={"PYTORCH_NPU_ALLOC_CONF": self.config.alloc_strategy.value},
            timestamp=datetime.now().isoformat(),
        )

        try:
            env = apply_tuning_env(self.config)
            self.applied_env.update(env)
            result.status = "applied"

        except Exception as e:
            result.status = "failed"
            result.error = str(e)

        self.report.results.append(result)
        return result

    def _generate_recommendations(self) -> None:
        """根据调优结果生成建议"""
        failed = [r for r in self.report.results if r.status == "failed"]
        if failed:
            self.report.recommendations.append(
                f"有 {len(failed)} 项调优未成功应用，请检查错误信息后重试"
            )

        tcmalloc_result = next(
            (r for r in self.report.results if r.tuning_level == "tcmalloc"), None
        )
        if tcmalloc_result and tcmalloc_result.status == "failed":
            self.report.recommendations.append(
                "tcmalloc 未安装。对频繁内存分配的训练场景有显著提升，"
                "建议安装后重新启用"
            )

        affinity_result = next(
            (r for r in self.report.results if r.tuning_level == "cpu_affinity"), None
        )
        if affinity_result and affinity_result.status == "skipped":
            self.report.recommendations.append(
                "CPU 绑核未启用。如果 Profiling 显示 CPU 瓶颈，可尝试粗粒度绑核 "
                "(CPU_AFFINITY_CONF=1)。注意：vLLM 等推理框架需先单独测试效果"
            )

        self.report.recommendations.append(
            "通用调优已完成。如需进一步优化，可考虑：\n"
            "  1. Python 编译优化（毕昇编译器 + LTO + PGO）— 提升解释器效率\n"
            "  2. PyTorch 编译优化（毕昇编译器 + LTO + PGO）— 降低框架层开销\n"
            "  3. torch_npu 编译优化（毕昇编译器 + LTO + PGO）— 进一步优化算子调度\n"
            "注意：编译优化需从源码重编，耗时较长，请确认后再执行"
        )

        self.report.recommendations.append(
            "渐进式调优建议：如果某项优化叠加后性能不升反降，应将其去掉，"
            "用剩余项的组合重新测试，找到最优子集"
        )


# ========== 编译优化脚本生成 ==========

_PYTHON_COMPILE_TEMPLATE = """#!/bin/bash
# ========================================
# Python 编译优化脚本（LTO + PGO）
# 使用毕昇编译器编译 Python 解释器
# ========================================

set -e

PYTHON_VERSION="{python_version}"
INSTALL_DIR="{install_dir}"

echo "=== Python 编译优化 ==="
echo "版本: $PYTHON_VERSION"
echo "安装目录: $INSTALL_DIR"

# 前置：配置毕昇编译器
export CC=clang
export CXX=clang++

# 下载 Python 源码（如已下载可跳过）
if [ ! -d "Python-$PYTHON_VERSION" ]; then
    echo "下载 Python $PYTHON_VERSION ..."
    wget https://www.python.org/ftp/python/$PYTHON_VERSION/Python-$PYTHON_VERSION.tgz
    tar -xvf Python-$PYTHON_VERSION.tgz
fi

cd Python-$PYTHON_VERSION
mkdir -p "$INSTALL_DIR"

# --with-lto: 启用 LTO 链接时优化
# --enable-optimizations: 启用 PGO 优化
echo "配置 Python ..."
./configure --prefix="$INSTALL_DIR" --with-lto --enable-optimizations

echo "编译 Python（可能需要较长时间）..."
make -j$(nproc)

echo "安装 Python ..."
make install

# 创建软链接
cd "$INSTALL_DIR/bin"
ln -sf python3 python
ln -sf pip3 pip

echo ""
echo "=== Python 编译优化完成 ==="
echo "Python 安装路径: $INSTALL_DIR/bin/python"
echo "验证: $INSTALL_DIR/bin/python --version"
"""


def generate_python_compile_script(
    python_version: str = "3.8.17",
    install_dir: str = "/opt/python-ascend",
) -> str:
    """生成 Python 编译优化脚本

    使用毕昇编译器（clang/clang++）+ LTO + PGO 从源码编译 Python。
    """
    return _PYTHON_COMPILE_TEMPLATE.format(
        python_version=python_version,
        install_dir=install_dir,
    )


_PYTORCH_COMPILE_LTO_TEMPLATE = """#!/bin/bash
# ========================================
# PyTorch 编译优化脚本（仅 LTO）
# 使用毕昇编译器编译 PyTorch
# ========================================

set -e

PYTORCH_VERSION="{pytorch_version}"

echo "=== PyTorch 编译优化（LTO）==="

# 前置：配置毕昇编译器
export CC=clang
export CXX=clang++
export USE_XNNPACK=0

export CMAKE_C_FLAGS="-flto=thin -fuse-ld=lld"
export CMAKE_CXX_FLAGS="-flto=thin -fuse-ld=lld"

if [ ! -d "pytorch-$PYTORCH_VERSION" ]; then
    echo "获取 PyTorch 源码 ..."
    git clone -b v$PYTORCH_VERSION \
https://github.com/pytorch/pytorch.git pytorch-$PYTORCH_VERSION
    cd pytorch-$PYTORCH_VERSION
    git submodule sync
    git submodule update --init --recursive
    pip install -r requirements.txt
else
    cd pytorch-$PYTORCH_VERSION
fi

git clean -dfx
python3 setup.py bdist_wheel
pip3 install dist/*.whl --force-reinstall --no-deps

echo ""
echo "=== PyTorch LTO 编译优化完成 ==="
echo "验证: python3 -c 'import torch; print(torch.__version__)'"
"""

_PYTORCH_COMPILE_PGO_TEMPLATE = """#!/bin/bash
# ========================================
# PyTorch 编译优化脚本（LTO + PGO，两次编译）
# 使用毕昇编译器编译 PyTorch
# ========================================

set -e

PYTORCH_VERSION="{pytorch_version}"
PROFILE_DIR="{profile_dir}"

echo "=== PyTorch 编译优化（LTO + PGO）==="

# 前置：配置毕昇编译器
export CC=clang
export CXX=clang++
export USE_XNNPACK=0
export OMP_PROC_BIND=false

# ---------- 第一次编译：插桩 ----------
echo ""
echo "=== 第一次编译（插桩）==="

export CMAKE_C_FLAGS="-flto=thin -fuse-ld=lld -fprofile-generate=$PROFILE_DIR"
export CMAKE_CXX_FLAGS="-flto=thin -fuse-ld=lld -fprofile-generate=$PROFILE_DIR"

if [ ! -d "pytorch-$PYTORCH_VERSION" ]; then
    echo "获取 PyTorch 源码 ..."
    git clone -b v$PYTORCH_VERSION \
https://github.com/pytorch/pytorch.git pytorch-$PYTORCH_VERSION
    cd pytorch-$PYTORCH_VERSION
    git submodule sync
    git submodule update --init --recursive
    pip install -r requirements.txt
else
    cd pytorch-$PYTORCH_VERSION
fi

git clean -dfx
python3 setup.py bdist_wheel
pip3 install dist/*.whl --force-reinstall --no-deps

echo ""
echo "=== 插桩包已安装，请运行模型采集 Profile 数据 ==="
echo "运行模型时设置: export LLVM_PROFILE_FILE=/tmp/profile/default_%m.profraw"
echo "采集完成后，继续执行以下步骤："
echo ""
echo "  # Profile 数据转换"
echo "  llvm-profdata merge $PROFILE_DIR -o default.profdata"
echo ""
echo "  # 第二次编译（使用 Profile 数据）："
echo "  export CMAKE_C_FLAGS='-flto=thin -fuse-ld=lld \
-fprofile-use=$PROFILE_DIR/default.profdata'"
echo "  export CMAKE_CXX_FLAGS='-flto=thin -fuse-ld=lld \
-fprofile-use=$PROFILE_DIR/default.profdata'"
echo "  cd pytorch-$PYTORCH_VERSION && git clean -dfx"
echo "  python3 setup.py bdist_wheel"
echo "  pip3 install dist/*.whl --force-reinstall --no-deps"
echo ""
echo "注意：插桩包性能会偏低，属正常现象。"
"""


def generate_pytorch_compile_script(
    pytorch_version: str = "2.1.0",
    profile_dir: str = "/tmp/pytorch_profile",
    pgo: bool = False,
) -> str:
    """生成 PyTorch 编译优化脚本

    使用毕昇编译器 + LTO + PGO 从源码编译 PyTorch。
    PGO 需要两次编译：插桩编译 → 采集 Profile → 使用 Profile 编译。
    """
    if pgo:
        return _PYTORCH_COMPILE_PGO_TEMPLATE.format(
            pytorch_version=pytorch_version,
            profile_dir=profile_dir,
        )
    return _PYTORCH_COMPILE_LTO_TEMPLATE.format(
        pytorch_version=pytorch_version,
    )


_TORCH_NPU_COMPILE_LTO_TEMPLATE = """#!/bin/bash
# ========================================
# torch_npu 编译优化脚本（仅 LTO）
# 前置：必须先完成 PyTorch 编译优化并安装
# ========================================

set -e

TORCH_NPU_VERSION="{torch_npu_version}"

echo "=== torch_npu 编译优化（LTO）==="

# 前置：配置毕昇编译器
export CC=clang
export CXX=clang++

if [ ! -d "torch_npu" ]; then
    echo "获取 torch_npu 源码 ..."
    git clone -b v$TORCH_NPU_VERSION https://gitee.com/ascend/pytorch.git torch_npu
else
    cd torch_npu
fi

git clean -dfx
bash ci/build.sh --python=3.8 --enable_lto
pip install dist/torch_npu-*.whl --force-reinstall --no-deps

echo ""
echo "=== torch_npu LTO 编译优化完成 ==="
echo "验证: python3 -c 'import torch_npu; print(torch_npu.__version__)'"
"""

_TORCH_NPU_COMPILE_PGO_TEMPLATE = """#!/bin/bash
# ========================================
# torch_npu 编译优化脚本（LTO + PGO，两次编译）
# 前置：必须先完成 PyTorch 编译优化并安装
# ========================================

set -e

TORCH_NPU_VERSION="{torch_npu_version}"
PROFILE_DIR="{profile_dir}"

echo "=== torch_npu 编译优化（LTO + PGO）==="

# 前置：配置毕昇编译器
export CC=clang
export CXX=clang++

# ---------- 第一次编译：插桩 ----------
echo ""
echo "=== 第一次编译（插桩）==="

if [ ! -d "torch_npu" ]; then
    echo "获取 torch_npu 源码 ..."
    git clone -b v$TORCH_NPU_VERSION https://gitee.com/ascend/pytorch.git torch_npu
else
    cd torch_npu
fi

git clean -dfx
bash ci/build.sh --python=3.8 --enable_lto --enable_pgo=1
pip3 install dist/*.whl --force-reinstall --no-deps

echo ""
echo "=== 插桩包已安装，请运行模型采集 Profile 数据 ==="
echo "运行模型时设置: export LLVM_PROFILE_FILE=/tmp/profile/default_%m.profraw"
echo ""
echo "采集完成后继续执行："
echo "  # Profile 数据转换"
echo "  llvm-profdata merge $PROFILE_DIR -o default.profdata"
echo "  # 拷贝到 torch_npu 目录"
echo "  cp default.profdata torch_npu/"
echo "  # 第二次编译"
echo "  cd torch_npu && git clean -dfx"
echo "  bash ci/build.sh --python=3.8 --enable_lto --enable_pgo=2"
echo ""
echo "注意：PyTorch 和 torch_npu 的 Profile 数据可以使用相同路径，"
echo "合并后的 profdata 编译器会自动识别。"
"""


def generate_torch_npu_compile_script(
    torch_npu_version: str = "2.1.0",
    profile_dir: str = "/tmp/torch_npu_profile",
    pgo: bool = False,
) -> str:
    """生成 torch_npu 编译优化脚本

    注意：必须先完成 PyTorch 编译优化并安装，torch_npu 编译依赖毕昇编译的 PyTorch。
    """
    if pgo:
        return _TORCH_NPU_COMPILE_PGO_TEMPLATE.format(
            torch_npu_version=torch_npu_version,
            profile_dir=profile_dir,
        )
    return _TORCH_NPU_COMPILE_LTO_TEMPLATE.format(
        torch_npu_version=torch_npu_version,
    )


# ========== 启动命令生成 ==========


def generate_launch_command(
    config: TuningConfig,
    script_path: str = "train.py",
    extra_env: dict[str, str] | None = None,
) -> str:
    """生成带调优环境变量的启动命令

    按照渐进式调优原则，仅包含已启用的优化项。
    """
    parts = []

    parts.append("source /usr/local/Ascend/ascend-toolkit/set_env.sh")

    tq = config.task_queue_enable.value
    if tq > 0:
        parts.append(f"export TASK_QUEUE_ENABLE={tq}")

    if config.cpu_affinity_mode != AffinityMode.DISABLED:
        if config.cpu_affinity_custom:
            parts.append(
                f"export CPU_AFFINITY_CONF={config.cpu_affinity_mode.value},"
                f"{config.cpu_affinity_custom}"
            )
        else:
            parts.append(f"export CPU_AFFINITY_CONF={config.cpu_affinity_mode.value}")

    if config.tcmalloc_enabled and config.tcmalloc_path:
        parts.append(f'export LD_PRELOAD="$LD_PRELOAD:{config.tcmalloc_path}"')

    if config.alloc_strategy != AllocStrategy.OFF:
        parts.append(f"export PYTORCH_NPU_ALLOC_CONF={config.alloc_strategy.value}")

    if config.enable_acl_graph:
        parts.append("export ASCEND_ENABLE_ACL_GRAPH=1")

    if not config.omp_proc_bind:
        parts.append("export OMP_PROC_BIND=false")

    if extra_env:
        for k, v in extra_env.items():
            parts.append(f"export {k}={v}")

    parts.append(f"python {script_path}")

    return "\n".join(parts)


# ========== 推荐配置生成 ==========


def get_recommended_configs() -> dict[str, TuningConfig]:
    """获取不同场景的推荐调优配置"""
    return {
        "training_default": TuningConfig(
            task_queue_enable=TaskQueueMode.ENHANCED,
            cpu_affinity_mode=AffinityMode.COARSE,
            tcmalloc_enabled=True,
            alloc_strategy=AllocStrategy.EXPANDABLE_SEGMENTS,
            enable_acl_graph=True,
        ),
        "training_conservative": TuningConfig(
            task_queue_enable=TaskQueueMode.ENABLED,
            cpu_affinity_mode=AffinityMode.DISABLED,
            tcmalloc_enabled=False,
            alloc_strategy=AllocStrategy.EXPANDABLE_SEGMENTS,
            enable_acl_graph=True,
        ),
        "inference_vllm": TuningConfig(
            task_queue_enable=TaskQueueMode.ENHANCED,
            cpu_affinity_mode=AffinityMode.DISABLED,
            tcmalloc_enabled=True,
            alloc_strategy=AllocStrategy.EXPANDABLE_SEGMENTS,
            enable_acl_graph=True,
        ),
        "inference_embedding": TuningConfig(
            task_queue_enable=TaskQueueMode.ENHANCED,
            cpu_affinity_mode=AffinityMode.COARSE,
            tcmalloc_enabled=False,
            alloc_strategy=AllocStrategy.EXPANDABLE_SEGMENTS,
            enable_acl_graph=True,
        ),
    }


# ========== 脚本分析（optimizer-agent-plus Phase 2） ==========

# 高影响优化项识别规则
_HIGH_IMPACT_FLAGS = {
    "--async-scheduling": {
        "category": "Async Scheduling",
        "impact": "High",
        "applicable": "所有场景，减少调度开销",
        "reference": "减少 Host 侧任务下发延迟",
    },
    "--compilation-config": {
        "category": "Graph Compilation",
        "impact": "High",
        "applicable": "Decode 密集型负载",
        "reference": "FULL_DECODE_ONLY 模式加速 decode",
        "value_check": "建议包含 cudagraph_mode=FULL_DECODE_ONLY",
    },
    "--enable-chunked-prefill": {
        "category": "Chunked Prefill",
        "impact": "High",
        "applicable": "长输入序列",
        "reference": "分块 prefill 减少显存峰值",
    },
    "--quantization": {
        "category": "Quantization",
        "impact": "High",
        "applicable": "量化模型",
        "reference": "ascend 量化降低显存与计算量",
    },
}

# 环境变量优化项
_ENV_FLAG_PATTERNS = {
    "VLLM_ASCEND_ENABLE_FLASHCOMM1": {
        "category": "FlashComm1",
        "impact": "High",
        "applicable": "EP 并行配置",
        "reference": "减少 AllReduce 通信量",
    },
    "VLLM_ASCEND_ENABLE_MULTISTREAM_MOE": {
        "category": "Multi-Stream MoE",
        "impact": "High",
        "applicable": "MoE 模型",
        "reference": "多流并行加速 MoE 计算",
    },
    "VLLM_ASCEND_ENABLE_MULTISTREAM_MLA": {
        "category": "MLA Multi-Stream",
        "impact": "High",
        "applicable": "DeepSeek MLA 注意力",
        "reference": "多流并行加速 MLA",
    },
    "TASK_QUEUE_ENABLE": {
        "category": "Pipeline",
        "impact": "Medium",
        "applicable": "host-bound 场景",
        "reference": "Host-Device 异步流水",
    },
    "CPU_AFFINITY_CONF": {
        "category": "CPU Affinity",
        "impact": "Medium",
        "applicable": "CPU 调度开销高",
        "reference": "减少线程漂移与 NUMA 跨节点访问",
    },
}


def _detect_model_architecture(script: str) -> dict[str, str]:
    """从脚本中推断模型架构特征"""
    script_lower = script.lower()
    arch = {"type": "unknown", "parallel": "unknown", "notes": ""}

    # 模型类型
    if any(k in script_lower for k in ["deepseek", "qwen3-30b-a3b", "qwen3-a3b"]):
        arch["type"] = "MoE"
    elif any(k in script_lower for k in ["qwen3-32b", "qwen3-14b", "glm-5", "glm5"]):
        arch["type"] = "Dense"
    elif "moe" in script_lower:
        arch["type"] = "MoE"

    # 并行策略
    if "--expert-parallel-size" in script or "--ep-size" in script or "-ep " in script:
        arch["parallel"] = "EP"
    elif "--data-parallel-size" in script and "--tensor-parallel-size" in script:
        arch["parallel"] = "TP+DP"
    elif "--tensor-parallel-size" in script:
        arch["parallel"] = "TP"
    elif "--data-parallel-size" in script:
        arch["parallel"] = "DP"

    # 长序列
    if "--max-model-len" in script:
        import re as _re

        m = _re.search(r"--max-model-len\s+(\d+)", script)
        if m and int(m.group(1)) >= 32768:
            arch["notes"] = f"长序列 (max_model_len={m.group(1)})"

    return arch


def analyze_launch_script(script: str) -> dict[str, Any]:
    """分析 vLLM 启动脚本，匹配优化案例库

    遵循 optimizer-agent-plus Phase 2 规范：
    1. 检测已应用的优化 → 标记为 implemented
    2. 检测适用但缺失的优化 → 加入建议
    3. 标记潜在问题配置
    """
    if not script or not script.strip():
        return {"error": "脚本内容为空"}

    arch = _detect_model_architecture(script)
    detected_params: list[dict[str, Any]] = []
    missing_recommendations: list[dict[str, Any]] = []
    warnings: list[str] = []

    # 检测命令行参数
    for flag, info in _HIGH_IMPACT_FLAGS.items():
        if flag in script:
            detected_params.append(
                {
                    "flag": flag,
                    "category": info["category"],
                    "impact": info["impact"],
                    "status": "implemented",
                    "reference": info["reference"],
                }
            )
        else:
            # 判断是否适用
            applicable = False
            reason = ""
            if flag == "--async-scheduling":
                applicable = True
                reason = "所有场景推荐"
            elif flag == "--compilation-config":
                applicable = True
                reason = "推荐 FULL_DECODE_ONLY 模式"
            elif flag == "--enable-chunked-prefill":
                if "长序列" in arch.get("notes", ""):
                    applicable = True
                    reason = "长序列场景受益"
            elif flag == "--quantization":
                if (
                    "w8a8" in script.lower()
                    or "w4a16" in script.lower()
                    or "ascend" in script.lower()
                ):
                    applicable = False  # 已有量化
                else:
                    applicable = False
                    reason = "仅量化模型需要"

            if applicable:
                missing_recommendations.append(
                    {
                        "flag": flag,
                        "category": info["category"],
                        "impact": info["impact"],
                        "status": "missing",
                        "reason": reason,
                        "reference": info["reference"],
                        "expected_gain": info.get("value_check", ""),
                    }
                )

    # 检测环境变量
    for env_var, info in _ENV_FLAG_PATTERNS.items():
        if env_var in script:
            detected_params.append(
                {
                    "flag": env_var,
                    "category": info["category"],
                    "impact": info["impact"],
                    "status": "implemented",
                    "reference": info["reference"],
                }
            )
        else:
            applicable = False
            reason = ""
            if env_var == "VLLM_ASCEND_ENABLE_FLASHCOMM1" and arch["parallel"] == "EP":
                applicable = True
                reason = "EP 并行配置受益"
            elif (
                env_var == "VLLM_ASCEND_ENABLE_MULTISTREAM_MOE"
                and arch["type"] == "MoE"
            ):
                applicable = True
                reason = "MoE 模型受益"
            elif (
                env_var == "VLLM_ASCEND_ENABLE_MULTISTREAM_MLA"
                and "deepseek" in script.lower()
            ):
                applicable = True
                reason = "DeepSeek MLA 注意力受益"
            elif env_var == "TASK_QUEUE_ENABLE":
                applicable = True
                reason = "host-bound 场景推荐"

            if applicable:
                missing_recommendations.append(
                    {
                        "flag": env_var,
                        "category": info["category"],
                        "impact": info["impact"],
                        "status": "missing",
                        "reason": reason,
                        "reference": info["reference"],
                    }
                )

    # 潜在问题检测
    if "ASCEND_LAUNCH_BLOCKING=1" in script:
        warnings.append(
            "ASCEND_LAUNCH_BLOCKING=1 会关闭 task queue，TASK_QUEUE_ENABLE 设置不生效"
        )
    if "--gpu-memory-utilization" in script:
        import re as _re

        m = _re.search(r"--gpu-memory-utilization\s+([\d.]+)", script)
        if m and float(m.group(1)) > 0.95:
            warnings.append(
                f"gpu-memory-utilization={m.group(1)} 过高，可能导致 OOM，建议 ≤ 0.90"
            )

    # 生成执行摘要
    high_impact_missing = [r for r in missing_recommendations if r["impact"] == "High"]
    summary = (
        f"检测到 {len(detected_params)} 项已应用优化，"
        f"{len(missing_recommendations)} 项可补充优化"
        + (f"，其中 {len(high_impact_missing)} 项高影响" if high_impact_missing else "")
    )

    return {
        "summary": summary,
        "architecture": arch,
        "detected_optimizations": detected_params,
        "missing_recommendations": missing_recommendations,
        "warnings": warnings,
        "top_3_by_impact": sorted(
            missing_recommendations,
            key=lambda x: {"High": 0, "Medium": 1, "Low": 2}.get(x["impact"], 3),
        )[:3],
    }


# ========== 瓶颈判断（ascend-optimization skill） ==========


def diagnose_bottleneck(profiling_summary: dict[str, Any]) -> dict[str, Any]:
    """基于 Profiling 结果判断瓶颈类型

    遵循 ascend-optimization skill 规范：
    - compute-bound: 算子耗时高、NPU 忙、热点集中在 attention/norm/FFN
    - host-bound: Free Time 明显、Dequeue 阻塞、CPU 调度开销、NPU 等待 host
    - memory-bound: 内存峰值高、malloc/free 频繁、碎片或锁竞争
    - communication-bound: 通信算子占比高
    """
    if not profiling_summary:
        return {
            "bottleneck_type": "unknown",
            "confidence": "low",
            "reason": "无 Profiling 数据",
            "recommendations": ["先采集 L0 Profiling 数据"],
        }

    # 提取关键指标（容忍字段缺失）
    npu_util = profiling_summary.get("npu_utilization_pct", 0)
    cube_ratio = profiling_summary.get("cube_operator_ratio", 0)
    comm_ratio = profiling_summary.get("communication_ratio", 0)
    free_time_ratio = profiling_summary.get("free_time_ratio", 0)
    cpu_ratio = profiling_summary.get("cpu_operator_ratio", 0)
    memory_peak = profiling_summary.get("memory_peak_pct", 0)
    dequeue_blocking = profiling_summary.get("dequeue_blocking_ratio", 0)
    malloc_free_ratio = profiling_summary.get("malloc_free_ratio", 0)

    scores = {
        "compute-bound": 0,
        "host-bound": 0,
        "memory-bound": 0,
        "communication-bound": 0,
    }
    reasons: list[str] = []

    # 计算瓶颈评分
    if cube_ratio > 50 or npu_util > 80:
        scores["compute-bound"] += 2
        reasons.append(f"Cube 算子占比 {cube_ratio}%，NPU 利用率 {npu_util}%")
    if free_time_ratio > 20 or dequeue_blocking > 15 or cpu_ratio > 40:
        scores["host-bound"] += 2
        reasons.append(
            f"Free Time {free_time_ratio}%，Dequeue 阻塞 {dequeue_blocking}%，"
            f"CPU 算子 {cpu_ratio}%"
        )
    if memory_peak > 85 or malloc_free_ratio > 30:
        scores["memory-bound"] += 2
        reasons.append(
            f"内存峰值 {memory_peak}%，malloc/free 占比 {malloc_free_ratio}%"
        )
    if comm_ratio > 30:
        scores["communication-bound"] += 2
        reasons.append(f"通信算子占比 {comm_ratio}%")

    # 选出最高分瓶颈
    top_bottleneck = max(scores, key=scores.get)
    top_score = scores[top_bottleneck]

    if top_score == 0:
        return {
            "bottleneck_type": "balanced",
            "confidence": "low",
            "scores": scores,
            "reason": "未检测到明显瓶颈",
            "recommendations": ["性能均衡，可尝试综合优化"],
        }

    confidence = "high" if top_score >= 2 else "medium"

    # 根据瓶颈类型给出优化方向
    optimization_map = {
        "compute-bound": [
            (
                "代码层：评估 torch_npu 亲和算子替换"
                "（npu_rms_norm/npu_fusion_attention/npu_swiglu）"
            ),
            "运行时：启用 ACL Graph（ASCEND_ENABLE_ACL_GRAPH=1）",
            "进阶：PyTorch/torch_npu 编译优化（LTO + PGO）",
        ],
        "host-bound": [
            "运行时：TASK_QUEUE_ENABLE=2（增强流水）",
            "运行时：CPU_AFFINITY_CONF=2（细粒度绑核，注意 vLLM 可能负优化）",
            "OS 层：LD_PRELOAD tcmalloc 减少内存分配锁竞争",
            "代码层：减少循环中 .item()/.cpu() 同步调用",
        ],
        "memory-bound": [
            "运行时：PYTORCH_NPU_ALLOC_CONF=expandable_segments",
            "OS 层：LD_PRELOAD tcmalloc 减少碎片",
            "代码层：检查 KV cache 配置、梯度检查点",
            "配置：降低 gpu-memory-utilization 或 max-num-seqs",
        ],
        "communication-bound": [
            "运行时：VLLM_ASCEND_ENABLE_FLASHCOMM1=1（EP 场景）",
            "配置：优化 TP/EP/DP 并行策略",
            "环境：调整 HCCL_BUFFERSIZE",
            "代码层：评估通信算子融合",
        ],
    }

    return {
        "bottleneck_type": top_bottleneck,
        "confidence": confidence,
        "scores": scores,
        "reason": "；".join(reasons),
        "recommendations": optimization_map.get(top_bottleneck, []),
    }


# ========== 代码层优化建议（ascend-optimization skill） ==========

# torch_npu 亲和算子替换建议库
_AFFINITY_OPERATOR_SUGGESTIONS: list[dict[str, Any]] = [
    {
        "path": "Norm 路径",
        "pattern": "RMSNorm / residual-add + LayerNorm",
        "suggestions": [
            {
                "api": "torch_npu.npu_rms_norm",
                "applicable": "手写 RMSNorm",
                "note": "dtype 需为 float16/bfloat16",
            },
            {
                "api": "torch_npu.npu_add_layer_norm",
                "applicable": "residual-add + LayerNorm 融合",
                "note": "减少一次 kernel 启动",
            },
        ],
    },
    {
        "path": "RoPE 路径",
        "pattern": "手写旋转位置编码",
        "suggestions": [
            {
                "api": "torch_npu.npu_rotary_mul",
                "applicable": "cos/sin 旋转位置编码",
                "note": "需保证输入 layout 一致",
            },
        ],
    },
    {
        "path": "Attention 路径",
        "pattern": "QK^T -> mask -> softmax -> V",
        "suggestions": [
            {
                "api": "torch_npu.npu_fusion_attention",
                "applicable": "标准注意力",
                "note": "支持多种 mask 语义，参考 mask 入参",
            },
            {
                "api": "torch_npu.npu_prompt_flash_attention",
                "applicable": "Prompt Flash Attention",
                "note": "长序列场景更优",
            },
        ],
    },
    {
        "path": "FFN / 门控路径",
        "pattern": "SwiGLU / GeGLU / 两层 MLP",
        "suggestions": [
            {
                "api": "torch_npu.npu_swiglu",
                "applicable": "SwiGLU 激活",
                "note": "需匹配 gate/up/down 权重布局",
            },
            {"api": "torch_npu.npu_gelu_mul", "applicable": "GeGLU 激活", "note": ""},
            {
                "api": "torch_npu.npu_ffn",
                "applicable": "完整 FFN 融合",
                "note": "进阶融合算子",
            },
        ],
    },
    {
        "path": "Layout 路径",
        "pattern": "permute / transpose 后非连续张量",
        "suggestions": [
            {
                "api": "补 .contiguous()",
                "applicable": "permute/transpose 后",
                "note": "避免非连续张量触发额外拷贝或 fallback",
            },
        ],
    },
    {
        "path": "Host-device sync",
        "pattern": "循环中频繁 .item() / .cpu() / 同步计时",
        "suggestions": [
            {
                "api": "移除或减少同步",
                "applicable": "训练/推理循环",
                "note": "确需计时时再显式同步",
            },
        ],
    },
]


def suggest_code_optimizations(model_code: str = "") -> dict[str, Any]:
    """生成代码层优化建议（torch_npu 亲和算子替换）

    遵循 ascend-optimization skill 规范：
    - 优先改热点路径，不要全模型盲目替换
    - 只有满足 dtype/shape/layout 约束时才替换
    - 保留 fallback 分支
    """
    detected_patterns: list[dict[str, Any]] = []

    if model_code:
        code_lower = model_code.lower()
        for item in _AFFINITY_OPERATOR_SUGGESTIONS:
            # 简单关键词匹配
            keywords = {
                "Norm 路径": ["rmsnorm", "layernorm", "layer_norm"],
                "RoPE 路径": ["rotary", "rope", "rotate_half"],
                "Attention 路径": ["softmax", "scaled_dot_product", "attention"],
                "FFN / 门控路径": ["swiglu", "geglu", "gelu", "silu", "ffn"],
                "Layout 路径": ["permute", "transpose"],
                "Host-device sync": [".item()", ".cpu()", "torch.npu.synchronize"],
            }
            path_keywords = keywords.get(item["path"], [])
            if any(kw in code_lower for kw in path_keywords):
                detected_patterns.append(
                    {
                        "path": item["path"],
                        "pattern": item["pattern"],
                        "suggestions": item["suggestions"],
                        "status": "detected",
                    }
                )

    # 未提供代码时返回完整建议库
    if not detected_patterns:
        return {
            "summary": "未提供模型代码或未检测到可优化路径，返回完整建议库",
            "principles": [
                "优先改热点路径，不要全模型盲目替换",
                "只有满足 dtype/shape/layout 约束时才替换为 torch_npu 亲和 API",
                "保留 fallback 分支，非 NPU 环境回退到原生 PyTorch",
                "替换后用同输入同精度验证数值一致性",
            ],
            "all_suggestions": _AFFINITY_OPERATOR_SUGGESTIONS,
            "fallback_template": _DEVICE_DETECTION_TEMPLATE,
        }

    return {
        "summary": f"检测到 {len(detected_patterns)} 个可优化路径",
        "detected_patterns": detected_patterns,
        "principles": [
            "优先改热点路径，不要全模型盲目替换",
            "只有满足 dtype/shape/layout 约束时才替换为 torch_npu 亲和 API",
            "保留 fallback 分支，非 NPU 环境回退到原生 PyTorch",
        ],
        "verification_checklist": [
            "数值精度是否在可接受范围内（余弦相似度 > 0.999）",
            "输出 shape、dtype、mask 语义是否一致",
            "总耗时是否下降，而不是只看单算子",
            "同输入、同精度、同设备、同 batch、同预热策略对比",
        ],
    }


_DEVICE_DETECTION_TEMPLATE = """import torch

try:
    import torch_npu
    _HAS_TORCH_NPU = True
except ImportError:
    torch_npu = None
    _HAS_TORCH_NPU = False


def _is_npu_tensor(x: torch.Tensor) -> bool:
    return (
        _HAS_TORCH_NPU
        and hasattr(torch, "npu")
        and torch.npu.is_available()
        and str(x.device).startswith("npu")
    )


# 示例：RMSNorm 替换
def rms_norm(x, weight, eps=1e-6):
    if _is_npu_tensor(x):
        return torch_npu.npu_rms_norm(x, weight, epsilon=eps)
    # fallback: 原生实现
    variance = x.pow(2).mean(-1, keepdim=True)
    x = x * torch.rsqrt(variance + eps)
    return x * weight
"""

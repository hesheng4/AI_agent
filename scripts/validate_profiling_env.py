"""昇腾 NPU Profiling 环境验证脚本

在执行 Profiling 采集前，先运行此脚本确认环境就绪。

用法:
    python scripts/validate_profiling_env.py --device npu:0 --output-dir ./profiling_output

检查项:
    - CANN 环境变量
    - torch_npu 可用性
    - NPU 设备状态
    - 磁盘空间
    - 性能优化环境变量
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def check_cann_env() -> dict[str, Any]:
    """检查 CANN 环境变量"""
    result = {"check": "cann_env", "passed": False, "details": {}}

    # 检查 ASCEND_HOME_PATH
    ascend_home = os.environ.get("ASCEND_HOME_PATH", "")
    result["details"]["ASCEND_HOME_PATH"] = ascend_home or "未设置"

    # 检查 ASCEND_AICPU_PATH
    aicpu_path = os.environ.get("ASCEND_AICPU_PATH", "")
    result["details"]["ASCEND_AICPU_PATH"] = aicpu_path or "未设置"

    # 检查 LD_LIBRARY_PATH 中是否包含 ascend
    ld_path = os.environ.get("LD_LIBRARY_PATH", "")
    has_ascend_lib = "ascend" in ld_path.lower()
    result["details"]["LD_LIBRARY_PATH_contains_ascend"] = has_ascend_lib

    if ascend_home:
        # 检查 version.cfg
        version_cfg = Path(ascend_home) / "latest" / "version.cfg"
        if version_cfg.exists():
            try:
                version = version_cfg.read_text().strip()
                result["details"]["cann_version"] = version
            except Exception:
                result["details"]["cann_version"] = "读取失败"
        else:
            result["details"]["cann_version"] = "version.cfg 不存在"

    result["passed"] = bool(ascend_home)
    return result


def check_torch_npu() -> dict[str, Any]:
    """检查 torch_npu 可用性"""
    result = {"check": "torch_npu", "passed": False, "details": {}}

    try:
        import torch

        result["details"]["torch_version"] = torch.__version__

        try:
            import torch_npu

            result["details"]["torch_npu_version"] = getattr(
                torch_npu, "__version__", "unknown"
            )
            result["details"]["npu_available"] = torch.npu.is_available()
            result["details"]["npu_device_count"] = torch.npu.device_count()

            if torch.npu.is_available():
                try:
                    result["details"]["cann_version"] = torch.npu.version.cann
                except Exception:
                    result["details"]["cann_version"] = "unknown"

                # 测试实际 NPU 计算
                try:
                    a = torch.randn(3, 4).npu()
                    b = torch.randn(4, 2).npu()
                    c = torch.matmul(a, b)
                    result["details"]["npu_compute_test"] = f"OK (shape={c.shape})"
                    result["passed"] = True
                except Exception as e:
                    result["details"]["npu_compute_test"] = f"失败: {e}"

        except ImportError as e:
            result["details"]["error"] = f"torch_npu 导入失败: {e}"

    except ImportError as e:
        result["details"]["error"] = f"torch 导入失败: {e}"

    return result


def check_npu_smi() -> dict[str, Any]:
    """检查 npu-smi 信息"""
    result = {"check": "npu_smi", "passed": False, "details": {}}

    try:
        output = subprocess.run(
            ["npu-smi", "info"], capture_output=True, text=True, timeout=10
        )
        if output.returncode == 0:
            info = output.stdout[:500]  # 截取前 500 字符
            result["details"]["npu_smi_output"] = info
            result["passed"] = True
        else:
            result["details"]["error"] = f"npu-smi 返回码: {output.returncode}"
    except FileNotFoundError:
        result["details"]["error"] = "npu-smi 命令未找到"
    except subprocess.TimeoutExpired:
        result["details"]["error"] = "npu-smi 超时"
    except Exception as e:
        result["details"]["error"] = str(e)

    return result


def check_disk_space(output_dir: str, min_gb: float = 10.0) -> dict[str, Any]:
    """检查磁盘空间"""
    result = {"check": "disk_space", "passed": False, "details": {}}

    try:
        if sys.platform == "win32":
            import ctypes

            free_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                ctypes.c_wchar_p(output_dir[:3]), None, None, ctypes.pointer(free_bytes)
            )
            free_gb = free_bytes.value / (1024**3)
        else:
            stat = os.statvfs(output_dir if os.path.exists(output_dir) else ".")
            free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)

        result["details"]["free_gb"] = round(free_gb, 2)
        result["details"]["min_required_gb"] = min_gb
        result["passed"] = free_gb >= min_gb

    except Exception as e:
        result["details"]["error"] = str(e)

    return result


def check_perf_env_vars() -> dict[str, Any]:
    """检查性能优化环境变量"""
    result = {"check": "perf_env_vars", "passed": False, "details": {}}

    cpu_affinity = os.environ.get("CPU_AFFINITY_CONF", "未设置")
    task_queue = os.environ.get("TASK_QUEUE_ENABLE", "未设置")

    result["details"]["CPU_AFFINITY_CONF"] = cpu_affinity
    result["details"]["TASK_QUEUE_ENABLE"] = task_queue

    # 建议设置
    result["details"]["recommendation"] = (
        "建议在采集前设置: " "export CPU_AFFINITY_CONF=1; " "export TASK_QUEUE_ENABLE=2"
    )

    result["passed"] = cpu_affinity != "未设置" and task_queue != "未设置"
    return result


def check_profiler_module() -> dict[str, Any]:
    """检查 torch_npu.profiler 模块"""
    result = {"check": "profiler_module", "passed": False, "details": {}}

    try:
        import torch_npu.profiler

        # 检查关键类和函数
        has_profile = hasattr(torch_npu.profiler, "profile")
        has_schedule = hasattr(torch_npu.profiler, "schedule")
        has_activity = hasattr(torch_npu.profiler, "ProfilerActivity")
        has_trace_handler = hasattr(torch_npu.profiler, "tensorboard_trace_handler")
        has_experimental = hasattr(torch_npu.profiler, "_ExperimentalConfig")
        has_level = hasattr(torch_npu.profiler, "ProfilerLevel")

        result["details"]["profile"] = has_profile
        result["details"]["schedule"] = has_schedule
        result["details"]["ProfilerActivity"] = has_activity
        result["details"]["tensorboard_trace_handler"] = has_trace_handler
        result["details"]["_ExperimentalConfig"] = has_experimental
        result["details"]["ProfilerLevel"] = has_level

        result["passed"] = all(
            [
                has_profile,
                has_schedule,
                has_activity,
                has_trace_handler,
                has_experimental,
                has_level,
            ]
        )

    except ImportError as e:
        result["details"]["error"] = f"torch_npu.profiler 导入失败: {e}"

    return result


def run_all_checks(
    device: str = "npu:0", output_dir: str = "./profiling_output"
) -> list[dict[str, Any]]:
    """运行所有检查"""
    checks = [
        check_cann_env(),
        check_torch_npu(),
        check_npu_smi(),
        check_disk_space(output_dir),
        check_perf_env_vars(),
        check_profiler_module(),
    ]
    return checks


def print_report(checks: list[dict[str, Any]]):
    """打印检查报告"""
    print("\n" + "=" * 60)
    print("  昇腾 NPU Profiling 环境验证报告")
    print("=" * 60)

    all_passed = True

    for check in checks:
        status = "✅ PASS" if check["passed"] else "❌ FAIL"
        print(f"\n  {status}  {check['check']}")

        for key, value in check.get("details", {}).items():
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + "..."
            print(f"         {key}: {value}")

        if not check["passed"]:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("  ✅ 所有检查通过，可以进行 Profiling 采集")
    else:
        print("  ❌ 部分检查未通过，请修复后再进行 Profiling 采集")
        print("\n  常见修复方法:")
        print("    1. source /usr/local/Ascend/ascend-toolkit/set_env.sh")
        print("    2. export CPU_AFFINITY_CONF=1")
        print("    3. export TASK_QUEUE_ENABLE=2")
        print("    4. pip install torch_npu (匹配 PyTorch 版本)")
        print("    5. 确保磁盘空间 >= 10GB")
    print("=" * 60 + "\n")

    return all_passed


def main():
    parser = argparse.ArgumentParser(description="昇腾 NPU Profiling 环境验证")
    parser.add_argument("--device", default="npu:0", help="NPU 设备")
    parser.add_argument(
        "--output-dir", default="./profiling_output", help="Profiling 输出目录"
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    args = parser.parse_args()

    checks = run_all_checks(device=args.device, output_dir=args.output_dir)

    if args.json:
        import json

        print(json.dumps(checks, ensure_ascii=False, indent=2))
    else:
        print_report(checks)

    # 返回码
    all_passed = all(c["passed"] for c in checks)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()

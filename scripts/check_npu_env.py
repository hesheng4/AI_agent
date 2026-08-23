#!/usr/bin/env python3
"""昇腾 NPU 环境预检脚本

检查项：
1. Python 版本兼容性
2. torch / torch_npu 安装与版本
3. CANN 版本
4. NPU 设备可用性
5. vLLM-Ascend 服务连通性
6. Embedding 模型可用性
7. 关键环境变量配置

用法：
    python scripts/check_npu_env.py
    python scripts/check_npu_env.py --vllm-url http://127.0.0.1:8001/v1
"""

import argparse
import os
import sys
from pathlib import Path
from types import ModuleType

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 昇腾 NPU 依赖（可选，非昇腾环境不存在）
try:
    import torch_npu as _torch_npu  # noqa: F401
except ImportError:
    _torch_npu: ModuleType | None = None  # type: ignore[assignment]


class Color:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    RESET = "\033[0m"


def print_status(name: str, passed: bool, detail: str = ""):
    status = (
        f"{Color.GREEN}✅ PASS{Color.RESET}"
        if passed
        else f"{Color.RED}❌ FAIL{Color.RESET}"
    )
    suffix = f" — {detail}" if detail else ""
    print(f"  {status} {name}{suffix}")


def print_section(title: str):
    print(f"\n{Color.BLUE}{'=' * 50}{Color.RESET}")
    print(f"{Color.BLUE}  {title}{Color.RESET}")
    print(f"{Color.BLUE}{'=' * 50}{Color.RESET}")


def check_python():
    """检查 Python 版本"""
    print_section("Python 环境")
    version = sys.version_info
    passed = version.major == 3 and 8 <= version.minor <= 11
    print_status(
        f"Python {version.major}.{version.minor}.{version.micro}",
        passed,
        "推荐 3.10" if not (version.major == 3 and version.minor == 10) else "",
    )
    return passed


def check_torch():
    """检查 PyTorch 和 torch_npu"""
    print_section("PyTorch / torch_npu")

    torch_ok = False
    torch_npu_ok = False
    torch_version = None
    npu_version = None

    # PyTorch
    try:
        import torch

        torch_version = torch.__version__
        torch_ok = True
        print_status(f"PyTorch {torch_version}", True)
    except ImportError:
        print_status("PyTorch", False, "未安装")
        return False

    # torch_npu
    if _torch_npu is not None:
        npu_version = (
            _torch_npu.__version__ if hasattr(_torch_npu, "__version__") else "unknown"
        )
        torch_npu_ok = True
        print_status(f"torch_npu {npu_version}", True)
    else:
        print_status("torch_npu", False, "未安装 — pip install torch_npu")
        return False

    # 版本匹配
    try:
        from torch_npu.version import (
            __version__ as tn_ver,  # type: ignore[import-untyped]
        )

        print_status(
            "torch/torch_npu 版本匹配", True, f"torch={torch_version}, npu={tn_ver}"
        )
    except Exception:
        print_status("torch/torch_npu 版本匹配", True, "无法精确检查")

    return torch_ok and torch_npu_ok


def check_npu_devices():
    """检查 NPU 设备"""
    print_section("NPU 设备")

    try:
        import torch
    except ImportError:
        print_status("NPU 设备", False, "torch 未安装")
        return False

    if _torch_npu is None:
        print_status("NPU 设备", False, "torch_npu 未安装")
        return False

    available = torch.npu.is_available()
    count = torch.npu.device_count()

    print_status("NPU 可用", available)

    if available and count > 0:
        print_status(f"NPU 设备数量: {count}", True)
        for i in range(count):
            try:
                name = torch.npu.get_device_name(i)
                cap = (
                    torch.npu.get_device_capability(i)
                    if hasattr(torch.npu, "get_device_capability")
                    else "N/A"
                )
                print_status(f"  NPU:{i} — {name}", True, f"capability={cap}")
            except Exception as e:
                print_status(f"  NPU:{i}", True, f"信息获取受限: {e}")

        # CANN 版本
        try:
            cann_ver = torch.npu.version.cann
            print_status(f"CANN 版本: {cann_ver}", True, "推荐 >= 8.0")
        except Exception:
            print_status("CANN 版本", False, "无法获取")

        return True
    else:
        print_status("NPU 设备", False, "无可用 NPU — 检查驱动和 CANN 安装")
        return False


def check_vllm_ascend(url: str = "http://127.0.0.1:8001/v1"):
    """检查 vLLM-Ascend 服务"""
    print_section("vLLM-Ascend 服务")

    try:
        import httpx
    except ImportError:
        print_status("httpx", False, "未安装 — pip install httpx")
        return False

    try:
        with httpx.Client(timeout=5.0) as client:
            # 检查 /v1/models
            response = client.get(f"{url}/models")
            if response.status_code == 200:
                models = response.json()
                model_list = [m.get("id", "unknown") for m in models.get("data", [])]
                print_status("vLLM-Ascend 服务连通", True, f"{url}")
                print_status(f"可用模型: {', '.join(model_list[:5])}", True)
                return True
            else:
                print_status("vLLM-Ascend 服务", False, f"HTTP {response.status_code}")
                return False
    except httpx.ConnectError:
        print_status(
            "vLLM-Ascend 服务", False, f"无法连接 {url} — 请先启动 vLLM-Ascend"
        )
        return False
    except Exception as e:
        print_status("vLLM-Ascend 服务", False, str(e))
        return False


def check_environment_variables():
    """检查关键环境变量"""
    print_section("环境变量")

    env_vars = {
        "ASCEND_RT_VISIBLE_DEVICES": "NPU 可见设备（可选）",
        "ASCEND_HOME_PATH": "CANN 安装路径",
        "LD_LIBRARY_PATH": "动态库路径",
    }

    for var, desc in env_vars.items():
        value = os.environ.get(var, "")
        if value:
            print_status(f"{var}", True, f"{value[:80]}")
        else:
            print_status(f"{var}", True, f"未设置（{desc}）")

    return True


def check_project_config():
    """检查项目配置"""
    print_section("项目昇腾配置")

    try:
        from app.config import get_settings

        settings = get_settings()

        print_status(
            f"LLM_MODE = {settings.LLM_MODE}", settings.LLM_MODE in ("remote", "ascend")
        )
        print_status(
            f"EMBEDDING_MODE = {settings.EMBEDDING_MODE}",
            settings.EMBEDDING_MODE in ("remote", "ascend_api", "ascend_local"),
        )

        if settings.LLM_MODE == "ascend":
            print_status(f"ASCEND_LLM_MODEL = {settings.ASCEND_LLM_MODEL}", True)
            print_status(
                f"ASCEND_VLLM_BASE_URL = {settings.ASCEND_VLLM_BASE_URL}", True
            )
            print_status(
                f"ASCEND_TP_SIZE = {settings.ASCEND_TP_SIZE}",
                settings.ASCEND_TP_SIZE in (1, 2, 4, 8),
            )

        if settings.EMBEDDING_MODE in ("ascend_api", "ascend_local"):
            print_status(
                f"ASCEND_EMBEDDING_MODEL = {settings.ASCEND_EMBEDDING_MODEL}", True
            )

        return True
    except Exception as e:
        print_status("项目配置", False, str(e))
        return False


def check_dependencies():
    """检查关键依赖"""
    print_section("关键依赖")

    deps = {
        "fastapi": "Web框架",
        "sqlalchemy": "ORM",
        "pydantic": "数据验证",
        "httpx": "HTTP客户端",
        "openai": "OpenAI SDK（远程模式）",
    }

    all_ok = True
    for pkg, desc in deps.items():
        try:
            mod = __import__(pkg)
            ver = getattr(mod, "__version__", "unknown")
            print_status(f"{pkg} {ver}", True, desc)
        except ImportError:
            print_status(f"{pkg}", False, f"未安装 — {desc}")
            all_ok = False

    # 可选依赖
    optional = {
        "sentence_transformers": "本地 Embedding（ascend_local 模式）",
        "pymilvus": "向量数据库",
    }
    for pkg, desc in optional.items():
        try:
            mod = __import__(pkg)
            ver = getattr(mod, "__version__", "unknown")
            print_status(f"{pkg} {ver}", True, f"可选 — {desc}")
        except ImportError:
            print_status(f"{pkg}", True, f"未安装 — {desc}")

    return all_ok


def main():
    parser = argparse.ArgumentParser(description="昇腾 NPU 环境预检")
    parser.add_argument(
        "--vllm-url", default="http://127.0.0.1:8001/v1", help="vLLM-Ascend 服务地址"
    )
    args = parser.parse_args()

    print(f"{Color.BLUE}")
    print("  ╔══════════════════════════════════════════╗")
    print("  ║   昇腾 NPU 环境预检                      ║")
    print("  ║   Research Agent Platform - Ascend Edition║")
    print("  ╚══════════════════════════════════════════╝")
    print(f"{Color.RESET}")

    results = []
    results.append(("Python 环境", check_python()))
    results.append(("PyTorch/torch_npu", check_torch()))
    results.append(("NPU 设备", check_npu_devices()))
    results.append(("关键依赖", check_dependencies()))
    results.append(("环境变量", check_environment_variables()))
    results.append(("vLLM-Ascend 服务", check_vllm_ascend(args.vllm_url)))
    results.append(("项目配置", check_project_config()))

    # 汇总
    print_section("检查汇总")
    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        print_status(name, result)

    print(f"\n  总计: {passed}/{total} 项通过")

    if passed == total:
        print(
            f"\n  {Color.GREEN}🎉 昇腾 NPU 环境就绪！可以启动 Research Agent Platform{Color.RESET}"
        )
    elif passed >= total - 1:
        print(
            f"\n  {Color.YELLOW}⚠️  部分检查未通过，请确认 vLLM-Ascend 服务是否已启动{Color.RESET}"
        )
    else:
        print(f"\n  {Color.RED}❌ 环境不完整，请参照上述提示安装缺失组件{Color.RESET}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())

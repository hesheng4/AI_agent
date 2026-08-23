#!/usr/bin/env python3
"""昇腾 NPU 性能调优 CLI 工具

遵循 ascend-ai4s-perf-tuning skill 规范：
- 渐进式调优：流水优化 → 绑核优化 → tcmalloc 替换
- 负优化回退：某项叠加后性能不升反降，应去掉该项
- 编译优化为进阶手段：需用户确认后才执行

用法:
    python scripts/run_perf_tuning.py --scenario training_default
    python scripts/run_perf_tuning.py --scenario inference_vllm --script train.py
    python scripts/run_perf_tuning.py --detect-tcmalloc
    python scripts/run_perf_tuning.py --detect-numa
    python scripts/run_perf_tuning.py --compile python --pgo
    python scripts/run_perf_tuning.py --compile pytorch --version 2.1.0 --pgo
    python scripts/run_perf_tuning.py --compile torch_npu --version 2.1.0 --pgo
"""

import argparse
import json
import os
import sys

# 添加项目根目录到 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.perf_tuning import (
    AffinityMode,
    ProgressiveTuningExecutor,
    TaskQueueMode,
    detect_numa_topology,
    detect_tcmalloc,
    generate_launch_command,
    generate_python_compile_script,
    generate_pytorch_compile_script,
    generate_torch_npu_compile_script,
    get_recommended_configs,
    install_tcmalloc_instructions,
)


def cmd_apply(args):
    """应用调优配置"""
    configs = get_recommended_configs()

    if args.scenario not in configs:
        print(f"错误: 未知场景 '{args.scenario}'")
        print(f"可用场景: {', '.join(configs.keys())}")
        sys.exit(1)

    config = configs[args.scenario]

    # 命令行覆盖
    if args.task_queue is not None:
        config.task_queue_enable = TaskQueueMode(args.task_queue)
    if args.affinity is not None:
        config.cpu_affinity_mode = AffinityMode(args.affinity)
    if args.tcmalloc:
        config.tcmalloc_enabled = True
    if args.tcmalloc_path:
        config.tcmalloc_path = args.tcmalloc_path
    if args.no_tcmalloc:
        config.tcmalloc_enabled = False

    print("=" * 60)
    print("昇腾 NPU 性能调优")
    print("=" * 60)
    print(f"\n场景: {args.scenario}")
    print(f"配置: {json.dumps(config.to_dict(), indent=2, ensure_ascii=False)}")

    # 渐进式执行
    executor = ProgressiveTuningExecutor(config)
    report = executor.run_all_basic()

    print("\n" + "=" * 60)
    print("调优结果")
    print("=" * 60)

    for result in report.results:
        status_icon = {
            "applied": "✓",
            "skipped": "○",
            "failed": "✗",
            "pending": "·",
        }.get(result.status, "?")

        print(f"\n  [{status_icon}] {result.tuning_level}: {result.status}")
        if result.error:
            print(f"      错误: {result.error}")
        if result.config_applied:
            for k, v in result.config_applied.items():
                print(f"      {k}: {v}")

    if report.warnings:
        print("\n⚠️  警告:")
        for w in report.warnings:
            print(f"  - {w}")

    if report.recommendations:
        print("\n📋 建议:")
        for r in report.recommendations:
            print(f"  - {r}")

    print("\n已设置的环境变量:")
    for k, v in executor.applied_env.items():
        print(f"  {k}={v}")

    # 生成启动命令
    if args.script:
        command = generate_launch_command(config, script_path=args.script)
        print("\n启动命令:")
        print(command)


def cmd_detect_tcmalloc(args):
    """检测 tcmalloc"""
    print("检测 tcmalloc 安装状态...")
    result = detect_tcmalloc()

    if result["installed"]:
        print("✓ tcmalloc 已安装")
        print(f"  路径: {result['path']}")
        print(f"  检测方式: {result['method']}")
    else:
        print("✗ tcmalloc 未安装")
        print("\n安装指引:")
        print(install_tcmalloc_instructions())


def cmd_detect_numa(args):
    """检测 NUMA 拓扑"""
    print("检测 NUMA 拓扑...")
    result = detect_numa_topology()

    if result["available"]:
        print("✓ NUMA 拓扑信息已获取")
        print(f"  CPU 核心数: {result['cpu_count']}")
        if result["numa_info"]:
            print("  NUMA 详情:")
            for info in result["numa_info"]:
                print(f"    {info}")
    else:
        print("✗ 无法获取 NUMA 拓扑（可能不在 Linux 环境）")


def cmd_compile(args):
    """生成编译优化脚本"""
    compile_type = args.type

    if compile_type == "python":
        print("生成 Python 编译优化脚本...")
        script = generate_python_compile_script(
            python_version=args.version,
            install_dir=args.install_dir,
        )
        print(f"\nPython 版本: {args.version}")
        print(f"安装目录: {args.install_dir}")
        print(f"PGO: {'是' if args.pgo else '否'}")

    elif compile_type == "pytorch":
        print("生成 PyTorch 编译优化脚本...")
        script = generate_pytorch_compile_script(
            pytorch_version=args.version,
            profile_dir=args.profile_dir,
            pgo=args.pgo,
        )
        print(f"\nPyTorch 版本: {args.version}")
        print(f"PGO: {'是' if args.pgo else '否'}")
        if args.pgo:
            print(f"Profile 目录: {args.profile_dir}")

    elif compile_type == "torch_npu":
        print("生成 torch_npu 编译优化脚本...")
        script = generate_torch_npu_compile_script(
            torch_npu_version=args.version,
            profile_dir=args.profile_dir,
            pgo=args.pgo,
        )
        print(f"\ntorch_npu 版本: {args.version}")
        print(f"PGO: {'是' if args.pgo else '否'}")
        if args.pgo:
            print(f"Profile 目录: {args.profile_dir}")
    else:
        print(f"错误: 未知编译类型 '{compile_type}'")
        print("可用类型: python, pytorch, torch_npu")
        sys.exit(1)

    # 保存脚本
    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(script)
        print(f"\n脚本已保存到: {args.output}")
    else:
        print("\n" + "=" * 60)
        print(script)


def cmd_launch(args):
    """生成启动命令"""
    configs = get_recommended_configs()

    if args.scenario not in configs:
        print(f"错误: 未知场景 '{args.scenario}'")
        print(f"可用场景: {', '.join(configs.keys())}")
        sys.exit(1)

    config = configs[args.scenario]
    command = generate_launch_command(config, script_path=args.script)

    print("生成的启动命令:")
    print("=" * 60)
    print(command)


def main():
    parser = argparse.ArgumentParser(
        description="昇腾 NPU 性能调优 CLI 工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用推荐配置调优（训练场景）
  python scripts/run_perf_tuning.py --scenario training_default

  # 使用推荐配置调优（vLLM 推理场景）
  python scripts/run_perf_tuning.py --scenario inference_vllm

  # 检测 tcmalloc
  python scripts/run_perf_tuning.py --detect-tcmalloc

  # 生成 Python 编译优化脚本
  python scripts/run_perf_tuning.py --compile python --pgo

  # 生成 PyTorch PGO 编译脚本
  python scripts/run_perf_tuning.py --compile pytorch --version 2.1.0 --pgo

  # 生成启动命令
  python scripts/run_perf_tuning.py --launch --scenario training_default --script train.py

渐进式调优原则：
  1. 流水优化 → 绑核优化 → tcmalloc 替换，逐项开启
  2. 如果某项叠加后性能不升反降，应将其去掉
  3. 编译优化为进阶手段，需用户确认后才执行
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # apply 子命令
    apply_parser = subparsers.add_parser("apply", help="应用调优配置")
    apply_parser.add_argument(
        "--scenario",
        "-s",
        default="training_default",
        choices=list(get_recommended_configs().keys()),
        help="调优场景 (默认: training_default)",
    )
    apply_parser.add_argument(
        "--task-queue", type=int, choices=[0, 1, 2], help="覆盖流水优化模式"
    )
    apply_parser.add_argument(
        "--affinity", type=int, choices=[0, 1, 2], help="覆盖绑核模式"
    )
    apply_parser.add_argument("--tcmalloc", action="store_true", help="启用 tcmalloc")
    apply_parser.add_argument("--tcmalloc-path", type=str, help="tcmalloc 路径")
    apply_parser.add_argument(
        "--no-tcmalloc", action="store_true", help="禁用 tcmalloc"
    )
    apply_parser.add_argument(
        "--script", type=str, help="启动脚本路径（用于生成启动命令）"
    )

    # detect-tcmalloc 子命令
    subparsers.add_parser("detect-tcmalloc", help="检测 tcmalloc 安装状态")

    # detect-numa 子命令
    subparsers.add_parser("detect-numa", help="检测 NUMA 拓扑")

    # compile 子命令
    compile_parser = subparsers.add_parser("compile", help="生成编译优化脚本")
    compile_parser.add_argument(
        "type",
        choices=["python", "pytorch", "torch_npu"],
        help="编译类型",
    )
    compile_parser.add_argument(
        "--version", default="2.1.0", help="版本号 (默认: 2.1.0)"
    )
    compile_parser.add_argument(
        "--install-dir", default="/opt/python-ascend", help="Python 安装目录"
    )
    compile_parser.add_argument(
        "--profile-dir", default="/tmp/profile", help="PGO Profile 目录"
    )
    compile_parser.add_argument(
        "--pgo", action="store_true", help="启用 PGO（需两次编译）"
    )
    compile_parser.add_argument("--output", "-o", type=str, help="保存脚本到文件")

    # launch 子命令
    launch_parser = subparsers.add_parser("launch", help="生成启动命令")
    launch_parser.add_argument(
        "--scenario",
        "-s",
        default="training_default",
        choices=list(get_recommended_configs().keys()),
        help="调优场景",
    )
    launch_parser.add_argument("--script", default="train.py", help="启动脚本路径")

    args = parser.parse_args()

    if args.command == "apply":
        cmd_apply(args)
    elif args.command == "detect-tcmalloc":
        cmd_detect_tcmalloc(args)
    elif args.command == "detect-numa":
        cmd_detect_numa(args)
    elif args.command == "compile":
        cmd_compile(args)
    elif args.command == "launch":
        cmd_launch(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

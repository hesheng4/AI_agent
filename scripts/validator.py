#!/usr/bin/env python3
"""昇腾模型适配验证编排器

遵循 verify-agent-plus skill 规范的完整验证流水线。

用法:
    python scripts/validator.py \\
        --model-path Eco-Tech/Qwen3.5-27B-w8a8-mtp \\
        --model-name qwen3.5 \\
        --quantized \\
        --port 8000 \\
        --tp-size 2

一键验证:
    python scripts/validator.py \\
        --model-path Eco-Tech/Qwen3.5-27B-w8a8-mtp \\
        --preset Qwen3.5-27B
"""

import argparse
import json
import os
import sys

# 添加项目根目录到 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.validator import (
    BenchmarkConfig,
    ValidationConfig,
    ValidationExecutor,
    VLLMServerConfig,
    generate_vllm_serve_command,
    get_preset_config,
    list_supported_models,
    run_environment_check,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="昇腾模型适配验证编排器 (verify-agent-plus)"
    )
    parser.add_argument(
        "--model-path",
        required=True,
        help="模型权重路径，如 Eco-Tech/Qwen3.5-27B-w8a8-mtp",
    )
    parser.add_argument(
        "--model-name", default="Qwen3.5-27B", help="模型标识 (default: Qwen3.5-27B)"
    )
    parser.add_argument(
        "--preset", default=None, help="使用预设配置: Qwen3.5-27B, Qwen3.5-27B-w8a8"
    )
    parser.add_argument(
        "--quantized",
        action="store_true",
        help="模型已量化（添加 --quantization ascend）",
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="vLLM 服务监听地址 (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="vLLM 服务端口 (default: 8000)"
    )
    parser.add_argument(
        "--tp-size", type=int, default=2, help="张量并行大小 (default: 2)"
    )
    parser.add_argument(
        "--dp-size", type=int, default=1, help="数据并行大小 (default: 1)"
    )
    parser.add_argument(
        "--max-model-len",
        type=int,
        default=133000,
        help="最大上下文长度 (default: 133000)",
    )
    parser.add_argument(
        "--gpu-mem-util",
        type=float,
        default=0.90,
        help="GPU 显存利用率 (default: 0.90)",
    )
    parser.add_argument(
        "--served-model-name", default=None, help="服务模型名称 (default: auto)"
    )
    parser.add_argument("--skip-accuracy", action="store_true", help="跳过精度测试")
    parser.add_argument("--skip-perf", action="store_true", help="跳过性能基准测试")
    parser.add_argument(
        "--bench-modes",
        nargs="+",
        default=["serve", "latency", "throughput"],
        help="性能测试模式 (default: serve latency throughput)",
    )
    parser.add_argument(
        "--input-len", type=int, default=200, help="基准测试输入长度 (default: 200)"
    )
    parser.add_argument(
        "--num-prompts", type=int, default=200, help="serve 模式请求数 (default: 200)"
    )
    parser.add_argument(
        "--output-dir",
        default="./validation_reports",
        help="报告输出目录 (default: ./validation_reports)",
    )
    parser.add_argument(
        "--startup-timeout",
        type=int,
        default=300,
        help="服务启动超时秒数 (default: 300)",
    )
    parser.add_argument("--env-check-only", action="store_true", help="仅执行环境检查")
    parser.add_argument("--deploy-cmd-only", action="store_true", help="仅生成部署命令")
    parser.add_argument("--list-models", action="store_true", help="列出支持的模型")
    return parser.parse_args()


def main():
    args = parse_args()

    # 列出支持的模型
    if args.list_models:
        models = list_supported_models()
        print("支持的模型:")
        for m in models:
            print(
                "  - {} (tp={}, max_len={}, gsm8k={})".format(
                    m["model_name"],
                    m["tp_size"],
                    m["max_model_len"],
                    m["gsm8k_reference"],
                )
            )
        return

    # 仅环境检查
    if args.env_check_only:
        print("=" * 50)
        print("环境预检")
        print("=" * 50)
        result = run_environment_check()
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return

    # 构建配置
    if args.preset:
        config = get_preset_config(args.preset)
        if not config:
            print(
                f"错误: 未找到预设 '{args.preset}'，可用: Qwen3.5-27B, Qwen3.5-27B-w8a8"
            )
            sys.exit(1)
        config.model_path = args.model_path
        config.vllm_server.port = args.port
    else:
        served_name = args.served_model_name or args.model_name.lower().replace(
            "-", "."
        )

        server_config = VLLMServerConfig(
            host=args.host,
            port=args.port,
            tensor_parallel_size=args.tp_size,
            data_parallel_size=args.dp_size,
            max_model_len=args.max_model_len,
            gpu_memory_utilization=args.gpu_mem_util,
            quantization="ascend" if args.quantized else None,
            served_model_name=served_name,
        )

        benchmark_config = BenchmarkConfig(
            input_len=args.input_len,
            num_prompts=args.num_prompts,
        )

        config = ValidationConfig(
            model_path=args.model_path,
            model_name=args.model_name,
            is_quantized=args.quantized,
            vllm_server=server_config,
            benchmark=benchmark_config,
            run_accuracy_test=not args.skip_accuracy,
            run_performance_tests=[] if args.skip_perf else args.bench_modes,
            report_output_dir=args.output_dir,
            server_startup_timeout=args.startup_timeout,
        )

    # 仅生成部署命令
    if args.deploy_cmd_only:
        print("=" * 50)
        print("vLLM 部署命令")
        print("=" * 50)
        print(generate_vllm_serve_command(config))
        return

    # 执行完整验证
    print("=" * 50)
    print("昇腾模型适配验证")
    print("=" * 50)
    print(f"模型: {config.model_path}")
    print(f"硬件: {config.hardware_type}")
    print("精度测试: {}".format("是" if config.run_accuracy_test else "否"))
    print(f"性能测试: {config.run_performance_tests}")
    print("")

    executor = ValidationExecutor(config)
    report = executor.run()

    # 输出报告
    report_dict = report.to_dict()
    print("")
    print("=" * 50)
    print("验证结果")
    print("=" * 50)
    print(json.dumps(report_dict, indent=2, ensure_ascii=False))

    # 退出码
    sys.exit(0 if report.success else 1)


if __name__ == "__main__":
    main()

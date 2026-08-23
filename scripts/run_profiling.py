"""昇腾 NPU Profiling 采集脚本（L0/L1/L2 级别）

用法:
    # L0（默认）— 最小膨胀，快速定位热点
    python scripts/run_profiling.py --level L0 --output-dir ./profiling_output

    # L1 — 算子级分析
    python scripts/run_profiling.py --level L1 --output-dir ./profiling_output

    # L2 — 完整调用栈 + 内存
    python scripts/run_profiling.py --level L2 --output-dir ./profiling_output

    # 推理场景
    python scripts/run_profiling.py --scenario inference --level L0

    # 训练场景
    python scripts/run_profiling.py --scenario training --level L0 --skip-first 20

⚠️ 注意：不要修改训练/推理脚本中的 CUDA 代码。
   torch_npu 的自动迁移会在运行时将 CUDA 调用转为 NPU 调用。
   Profiling 代码使用 torch_npu.profiler 是必要的，但业务代码保持原样即可。
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# 设置环境变量（必须在 import torch 之前）
os.environ.setdefault("CPU_AFFINITY_CONF", "1")
os.environ.setdefault("TASK_QUEUE_ENABLE", "2")

sys.path.insert(0, str(Path(__file__).parent.parent))


def run_profiling_embedding(config: dict) -> dict:
    """对 NPULocalEmbedding 进行 Profiling 采集

    推理场景：Embedding 模型的 Profiling
    """
    import torch_npu

    from app.core.profiling import (
        ProfilingConfig,
        ProfilingLevel,
        build_profiler_kwargs,
    )

    level = ProfilingLevel(config["level"])
    pconfig = ProfilingConfig(
        level=level,
        scenario="inference",
        output_dir=config["output_dir"],
        num_inference_steps=config.get("num_steps", 5),
    )

    # 设置环境变量
    from app.core.profiling import setup_profiling_env

    setup_profiling_env(pconfig)

    # 构建 profiler 参数
    kwargs, output_path = build_profiler_kwargs(pconfig)

    # 加载 Embedding 模型
    from app.core.ascend import get_npu_embedding

    embedder = get_npu_embedding()

    if embedder is None:
        return {"status": "error", "message": "NPU Embedding 模型不可用"}

    # 测试文本
    test_texts = [
        "这是一个Profiling测试文本。",
        "量子计算是未来的重要方向。",
        "深度学习需要大量训练数据。",
    ]

    result = {
        "status": "pending",
        "level": config["level"],
        "output_path": output_path,
        "start_time": datetime.now().isoformat(),
    }

    try:
        # 采集
        if level == ProfilingLevel.L0:
            activities = [torch_npu.profiler.ProfilerActivity.NPU]
        else:
            activities = [
                torch_npu.profiler.ProfilerActivity.CPU,
                torch_npu.profiler.ProfilerActivity.NPU,
            ]

        with torch_npu.profiler.profile(
            activities=activities,
            on_trace_ready=torch_npu.profiler.tensorboard_trace_handler(output_path),
        ) as prof:
            for step in range(pconfig.num_inference_steps):
                _ = embedder.encode(test_texts)
                prof.step()

        result["status"] = "completed"
        result["end_time"] = datetime.now().isoformat()

    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)

    return result


def run_profiling_vllm(config: dict) -> dict:
    """对 vLLM-Ascend 推理服务进行 Profiling 采集

    推理场景：通过 API 调用 vLLM-Ascend 服务
    注意：vLLM-Ascend 服务本身需要在启动时开启 Profiling，
    此脚本仅记录 API 调用的端到端延迟。
    """
    import asyncio

    import httpx

    from app.config import get_settings

    settings = get_settings()

    base_url = settings.ASCEND_VLLM_BASE_URL
    model = settings.ASCEND_LLM_MODEL

    # 测试 prompts
    test_prompts = [
        {"role": "user", "content": "请用一句话介绍量子计算。"},
        {"role": "user", "content": "What is machine learning?"},
        {"role": "user", "content": "解释牛顿第三定律。"},
    ]

    num_steps = config.get("num_steps", 5)
    output_dir = config["output_dir"]

    result = {
        "status": "pending",
        "level": config["level"],
        "output_dir": output_dir,
        "start_time": datetime.now().isoformat(),
        "latencies_ms": [],
    }

    try:

        async def _measure():
            async with httpx.AsyncClient(timeout=120.0) as client:
                for step in range(num_steps):
                    for prompt in test_prompts:
                        start = time.perf_counter()
                        response = await client.post(
                            f"{base_url}/chat/completions",
                            json={
                                "model": model,
                                "messages": [prompt],
                                "temperature": 0.0,
                                "max_tokens": 128,
                            },
                            headers={
                                "Content-Type": "application/json",
                                "Authorization": "Bearer EMPTY",
                            },
                        )
                        elapsed = (time.perf_counter() - start) * 1000  # ms
                        result["latencies_ms"].append(round(elapsed, 2))

                        if response.status_code != 200:
                            raise RuntimeError(
                                f"API 调用失败: HTTP {response.status_code}"
                            )

        asyncio.run(_measure())

        # 统计
        latencies = result["latencies_ms"]
        result["latency_avg_ms"] = (
            round(sum(latencies) / len(latencies), 2) if latencies else 0
        )
        result["latency_p50_ms"] = (
            round(sorted(latencies)[len(latencies) // 2], 2) if latencies else 0
        )
        result["latency_p99_ms"] = (
            round(sorted(latencies)[int(len(latencies) * 0.99)], 2) if latencies else 0
        )
        result["latency_min_ms"] = round(min(latencies), 2) if latencies else 0
        result["latency_max_ms"] = round(max(latencies), 2) if latencies else 0
        result["total_requests"] = len(latencies)

        result["status"] = "completed"
        result["end_time"] = datetime.now().isoformat()

    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)

    return result


def generate_script(config: dict) -> dict:
    """生成 Profiling 采集脚本（不直接执行）"""
    from app.core.profiling import (
        ProfilingConfig,
        ProfilingLevel,
        ProfilingScenario,
        generate_profiling_script,
    )

    level = ProfilingLevel(config["level"])
    scenario = ProfilingScenario(config.get("scenario", "inference"))

    pconfig = ProfilingConfig(
        level=level,
        scenario=scenario,
        output_dir=config["output_dir"],
        skip_first=config.get("skip_first", 20),
        num_inference_steps=config.get("num_steps", 5),
    )

    script_content = generate_profiling_script(pconfig)

    output_path = os.path.join(
        config["output_dir"], f"profile_{config['level']}_{scenario.value}.py"
    )
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(script_content)

    return {
        "status": "generated",
        "script_path": output_path,
        "level": config["level"],
        "scenario": scenario.value,
    }


def main():
    parser = argparse.ArgumentParser(description="昇腾 NPU Profiling 采集")
    parser.add_argument(
        "--level", default="L0", choices=["L0", "L1", "L2"], help="采集级别（默认 L0）"
    )
    parser.add_argument(
        "--scenario",
        default="inference",
        choices=["training", "inference"],
        help="采集场景",
    )
    parser.add_argument("--output-dir", default="./profiling_output", help="输出目录")
    parser.add_argument("--skip-first", type=int, default=20, help="训练场景跳过前N步")
    parser.add_argument("--num-steps", type=int, default=5, help="推理采集步数")
    parser.add_argument(
        "--target",
        default="vllm",
        choices=["vllm", "embedding", "script"],
        help="Profiling 目标: vllm(API延迟), embedding(本地), script(生成脚本)",
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出结果")
    args = parser.parse_args()

    config = {
        "level": args.level,
        "scenario": args.scenario,
        "output_dir": args.output_dir,
        "skip_first": args.skip_first,
        "num_steps": args.num_steps,
    }

    print(f"{'=' * 60}")
    print("  昇腾 NPU Profiling 采集")
    print(f"{'=' * 60}")
    print(f"  级别: {args.level}")
    print(f"  场景: {args.scenario}")
    print(f"  目标: {args.target}")
    print(f"  输出: {args.output_dir}")
    print(
        f"  环境变量: CPU_AFFINITY_CONF={os.environ.get('CPU_AFFINITY_CONF')}, "
        f"TASK_QUEUE_ENABLE={os.environ.get('TASK_QUEUE_ENABLE')}"
    )
    print()

    if args.target == "script":
        result = generate_script(config)
    elif args.target == "embedding":
        result = run_profiling_embedding(config)
    elif args.target == "vllm":
        result = run_profiling_vllm(config)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"\n结果: {result['status']}")
        if result.get("output_path"):
            print(f"数据路径: {result['output_path']}")
        if result.get("latency_avg_ms"):
            print(f"平均延迟: {result['latency_avg_ms']:.2f} ms")
            print(f"P50 延迟: {result['latency_p50_ms']:.2f} ms")
            print(f"P99 延迟: {result['latency_p99_ms']:.2f} ms")
        if result.get("script_path"):
            print(f"脚本路径: {result['script_path']}")

    # 保存结果
    os.makedirs(args.output_dir, exist_ok=True)
    result_file = os.path.join(
        args.output_dir,
        f"result_{args.level}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
    )
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存: {result_file}")


if __name__ == "__main__":
    main()

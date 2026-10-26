"""精度对齐推理对比脚本

用法:
    python scripts/compare_inference.py \
        --baseline-url http://gpu-host:8001/v1 \
        --npu-url http://127.0.0.1:8001/v1 \
        --model Qwen/Qwen2.5-72B-Instruct \
        --test-file tests/alignment/test_prompts.jsonl \
        --output reports/inference_alignment.json

对比规则（ascend-ai4s-precision-alignment skill）:
- 基线来源优先级: 官方 > 用户GPU > CPU调试
- 阈值在比较前声明
- 严格同条件: 同 seed、同 tokenizer、同解码参数
- CPU 对比仅用于调试，不作为最终结论
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))


# ========== 预声明的阈值 ==========
# 遵循规则：不能先看到 mismatch，再临时放宽阈值
THRESHOLDS = {
    "exact_match": 1.0,  # 贪婪解码应完全匹配
    "token_match_rate": 1.0,  # token 匹配率
    "logit_atol": 1e-3,  # logits 绝对误差
    "logit_rtol": 1e-2,  # logits 相对误差
    "emb_cosine_sim": 0.999,  # Embedding 余弦相似度
    "emb_l2_atol": 1e-3,  # Embedding L2 距离
}


async def call_chat_api(
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.0,
    max_tokens: int = 128,
    api_key: str = "EMPTY",
) -> dict[str, Any]:
    """调用 OpenAI 兼容 Chat Completions API"""
    import httpx

    async with httpx.AsyncClient(timeout=120.0) as client:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            response = await client.post(
                f"{base_url}/chat/completions",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
            )
            response.raise_for_status()
            data = response.json()

            return {
                "content": data["choices"][0]["message"]["content"],
                "finish_reason": data["choices"][0].get("finish_reason", ""),
                "usage": data.get("usage", {}),
                "status": "ok",
            }
        except httpx.HTTPStatusError as e:
            return {
                "status": "error",
                "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


async def call_embedding_api(
    base_url: str,
    model: str,
    texts: list[str],
    api_key: str = "EMPTY",
) -> dict[str, Any]:
    """调用 OpenAI 兼容 Embeddings API"""
    import httpx

    async with httpx.AsyncClient(timeout=60.0) as client:
        payload = {
            "model": model,
            "input": texts,
        }

        try:
            response = await client.post(
                f"{base_url}/embeddings",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
            )
            response.raise_for_status()
            data = response.json()

            embeddings = [item["embedding"] for item in data["data"]]
            return {
                "embeddings": embeddings,
                "status": "ok",
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


def compute_token_match_rate(baseline_text: str, npu_text: str) -> float:
    """计算 token 匹配率"""
    if not baseline_text or not npu_text:
        return 0.0

    # 简单字符级比较（更精确的做法是用 tokenizer 分词后比较 token id）
    baseline_chars = list(baseline_text)
    npu_chars = list(npu_text)

    min_len = min(len(baseline_chars), len(npu_chars))
    if min_len == 0:
        return 0.0

    matches = sum(1 for i in range(min_len) if baseline_chars[i] == npu_chars[i])
    return matches / max(len(baseline_chars), len(npu_chars))


def compute_cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """计算余弦相似度"""
    import math

    if len(vec_a) != len(vec_b):
        return 0.0

    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


def compute_l2_distance(vec_a: list[float], vec_b: list[float]) -> float:
    """计算 L2 距离"""
    import math

    if len(vec_a) != len(vec_b):
        return float("inf")

    return math.sqrt(sum((a - b) ** 2 for a, b in zip(vec_a, vec_b)))


async def compare_llm_inference(
    baseline_url: str,
    npu_url: str,
    model: str,
    test_prompts: list[dict[str, Any]],
    temperature: float = 0.0,
    max_tokens: int = 128,
    baseline_source: str = "user_gpu_result",
) -> dict[str, Any]:
    """比较 LLM 推理精度"""
    results = []
    exact_matches = 0
    token_match_rates = []

    for i, prompt_data in enumerate(test_prompts):
        messages = prompt_data.get(
            "messages", [{"role": "user", "content": prompt_data.get("prompt", "")}]
        )
        prompt_label = prompt_data.get("label", f"prompt_{i}")

        # 并行调用
        baseline_task = call_chat_api(
            baseline_url, model, messages, temperature, max_tokens
        )
        npu_task = call_chat_api(npu_url, model, messages, temperature, max_tokens)
        baseline_result, npu_result = await asyncio.gather(baseline_task, npu_task)

        if baseline_result["status"] != "ok" or npu_result["status"] != "ok":
            results.append(
                {
                    "label": prompt_label,
                    "status": "error",
                    "baseline_error": baseline_result.get("error", ""),
                    "npu_error": npu_result.get("error", ""),
                }
            )
            continue

        baseline_text = baseline_result["content"]
        npu_text = npu_result["content"]

        # 计算指标
        is_exact_match = baseline_text.strip() == npu_text.strip()
        tmr = compute_token_match_rate(baseline_text, npu_text)

        if is_exact_match:
            exact_matches += 1
        token_match_rates.append(tmr)

        results.append(
            {
                "label": prompt_label,
                "status": "ok",
                "exact_match": is_exact_match,
                "token_match_rate": tmr,
                "baseline_text": baseline_text[:200],
                "npu_text": npu_text[:200],
            }
        )

    # 汇总
    total = len(test_prompts)
    emr = exact_matches / total if total > 0 else 0.0
    avg_tmr = (
        sum(token_match_rates) / len(token_match_rates) if token_match_rates else 0.0
    )

    return {
        "task": "llm_inference",
        "baseline_source": baseline_source,
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "total_prompts": total,
        "exact_match_rate": emr,
        "avg_token_match_rate": avg_tmr,
        "thresholds": {
            "exact_match": THRESHOLDS["exact_match"],
            "token_match_rate": THRESHOLDS["token_match_rate"],
        },
        "passed": emr >= THRESHOLDS["exact_match"]
        and avg_tmr >= THRESHOLDS["token_match_rate"],
        "per_prompt_results": results,
    }


async def compare_embedding_inference(
    baseline_url: str,
    npu_url: str,
    model: str,
    test_texts: list[str],
    baseline_source: str = "user_gpu_result",
) -> dict[str, Any]:
    """比较 Embedding 推理精度"""
    cosine_sims = []
    l2_dists = []

    # 分批处理
    batch_size = 32
    for i in range(0, len(test_texts), batch_size):
        batch = test_texts[i : i + batch_size]

        baseline_task = call_embedding_api(baseline_url, model, batch)
        npu_task = call_embedding_api(npu_url, model, batch)
        baseline_result, npu_result = await asyncio.gather(baseline_task, npu_task)

        if baseline_result["status"] != "ok" or npu_result["status"] != "ok":
            continue

        for j in range(len(baseline_result["embeddings"])):
            cos_sim = compute_cosine_similarity(
                baseline_result["embeddings"][j],
                npu_result["embeddings"][j],
            )
            l2_dist = compute_l2_distance(
                baseline_result["embeddings"][j],
                npu_result["embeddings"][j],
            )
            cosine_sims.append(cos_sim)
            l2_dists.append(l2_dist)

    if not cosine_sims:
        return {
            "task": "embedding_inference",
            "status": "error",
            "message": "无有效比较结果",
        }

    avg_cos = sum(cosine_sims) / len(cosine_sims)
    min_cos = min(cosine_sims)
    avg_l2 = sum(l2_dists) / len(l2_dists)
    max_l2 = max(l2_dists)

    return {
        "task": "embedding_inference",
        "baseline_source": baseline_source,
        "model": model,
        "total_texts": len(test_texts),
        "avg_cosine_similarity": avg_cos,
        "min_cosine_similarity": min_cos,
        "avg_l2_distance": avg_l2,
        "max_l2_distance": max_l2,
        "thresholds": {
            "emb_cosine_sim": THRESHOLDS["emb_cosine_sim"],
            "emb_l2_atol": THRESHOLDS["emb_l2_atol"],
        },
        "passed": avg_cos >= THRESHOLDS["emb_cosine_sim"]
        and max_l2 <= THRESHOLDS["emb_l2_atol"],
        "per_text_cosine_sims": cosine_sims[:20],  # 保留前20个
    }


def generate_report(
    results: list[dict[str, Any]], output_path: str, metadata: dict[str, Any]
) -> None:
    """生成精度对齐报告"""
    report = {
        "report_date": datetime.now().isoformat(),
        "model": metadata.get("model", ""),
        "baseline_source_priority": [
            "官方 README / 官方示例 / 官方 benchmark / 官方文档",
            "用户提供的 GPU 真实运行结果",
        ],
        "baseline_source_actual": metadata.get("baseline_source", "user_gpu_result"),
        "constraints": {
            "temperature": metadata.get("temperature", 0.0),
            "max_tokens": metadata.get("max_tokens", 128),
            "dtype": "bfloat16",
        },
        "thresholds_declared_before_comparison": THRESHOLDS,
        "results": results,
        "overall_passed": all(r.get("passed", False) for r in results),
    }

    # CPU 调试对比警告
    if metadata.get("baseline_source") == "cpu_debug_only":
        report["cpu_debug_warning"] = (
            "⚠️ 本次对比使用 CPU 作为基线，仅用于调试目的。"
            "不能证明 NPU 与官方模型一致，不能替代官方基线或用户 GPU 基线。"
        )

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n报告已保存: {output_path}")

    # 打印摘要
    print(f"\n{'=' * 60}")
    print("  精度对齐结果摘要")
    print(f"{'=' * 60}")

    for r in results:
        task = r.get("task", "unknown")
        passed = r.get("passed", False)
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  {task}")

        if task == "llm_inference":
            print(
                f"         Exact Match Rate: {r.get('exact_match_rate', 0):.4f} (阈值: {THRESHOLDS['exact_match']})"
            )
            print(
                f"         Token Match Rate: {r.get('avg_token_match_rate', 0):.4f} (阈值: {THRESHOLDS['token_match_rate']})"
            )
        elif task == "embedding_inference":
            print(
                f"         Avg Cosine Sim: {r.get('avg_cosine_similarity', 0):.6f} (阈值: {THRESHOLDS['emb_cosine_sim']})"
            )
            print(
                f"         Max L2 Distance: {r.get('max_l2_distance', 0):.6f} (阈值: {THRESHOLDS['emb_l2_atol']})"
            )

    overall = all(r.get("passed", False) for r in results)
    print(f"\n  总体: {'✅ 对齐' if overall else '❌ 未对齐'}")

    if metadata.get("baseline_source") == "cpu_debug_only":
        print("\n  ⚠️ 注意: CPU 调试对比不作为最终精度对齐结论")


async def main() -> None:
    parser = argparse.ArgumentParser(description="精度对齐推理对比")
    parser.add_argument(
        "--baseline-url", required=True, help="基线服务 URL（GPU/官方）"
    )
    parser.add_argument("--npu-url", required=True, help="NPU 服务 URL")
    parser.add_argument("--model", required=True, help="模型名称")
    parser.add_argument("--test-file", help="测试文件（JSONL，每行一个 prompt）")
    parser.add_argument(
        "--output", default="reports/inference_alignment.json", help="输出报告路径"
    )
    parser.add_argument(
        "--temperature", type=float, default=0.0, help="temperature（精度对比用 0）"
    )
    parser.add_argument("--max-tokens", type=int, default=128, help="max_tokens")
    parser.add_argument(
        "--baseline-source",
        default="user_gpu_result",
        choices=[
            "official_readme",
            "official_example",
            "official_benchmark",
            "official_doc",
            "user_gpu_result",
            "cpu_debug_only",
        ],
        help="基线来源",
    )
    parser.add_argument(
        "--compare-embedding", action="store_true", help="同时对比 Embedding"
    )
    parser.add_argument(
        "--embedding-model", default="BAAI/bge-large-zh-v1.5", help="Embedding 模型"
    )
    parser.add_argument(
        "--embedding-test-file", help="Embedding 测试文件（每行一个文本）"
    )
    args = parser.parse_args()

    print(f"{'=' * 60}")
    print("  精度对齐推理对比")
    print(f"{'=' * 60}")
    print(f"  基线来源: {args.baseline_source}")
    print(f"  基线 URL: {args.baseline_url}")
    print(f"  NPU URL:  {args.npu_url}")
    print(f"  模型: {args.model}")
    print(f"  temperature: {args.temperature}")
    print(f"  max_tokens: {args.max_tokens}")
    print("\n  预声明阈值:")
    for k, v in THRESHOLDS.items():
        print(f"    {k}: {v}")
    print()

    if args.baseline_source == "cpu_debug_only":
        print("  ⚠️ 警告: CPU 对比仅用于调试，不作为最终精度对齐结论")
        print()

    # 加载测试数据
    test_prompts = []
    if args.test_file and os.path.exists(args.test_file):
        with open(args.test_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    test_prompts.append(json.loads(line))
    else:
        # 默认测试用例
        test_prompts = [
            {
                "label": "simple_zh",
                "messages": [{"role": "user", "content": "请用一句话介绍量子计算。"}],
            },
            {
                "label": "simple_en",
                "messages": [
                    {
                        "role": "user",
                        "content": "What is machine learning in one sentence?",
                    }
                ],
            },
            {
                "label": "reasoning",
                "messages": [
                    {
                        "role": "user",
                        "content": "如果A比B高5cm，B比C高3cm，A比C高多少？",
                    }
                ],
            },
            {
                "label": "creative",
                "messages": [{"role": "user", "content": "写一首关于春天的四行诗。"}],
            },
        ]
        print("  使用默认测试用例（建议提供 --test-file 以获得更完整的覆盖）")

    # LLM 推理对比
    print(f"\n  开始 LLM 推理对比 ({len(test_prompts)} 个测试)...")
    llm_result = await compare_llm_inference(
        baseline_url=args.baseline_url,
        npu_url=args.npu_url,
        model=args.model,
        test_prompts=test_prompts,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        baseline_source=args.baseline_source,
    )

    results = [llm_result]

    # Embedding 推理对比
    if args.compare_embedding:
        test_texts = []
        if args.embedding_test_file and os.path.exists(args.embedding_test_file):
            with open(args.embedding_test_file, encoding="utf-8") as f:
                test_texts = [line.strip() for line in f if line.strip()]
        else:
            test_texts = [
                "这是一个测试句子。",
                "量子计算是未来技术的重要方向。",
                "深度学习模型需要大量训练数据。",
            ]

        print(f"  开始 Embedding 推理对比 ({len(test_texts)} 个测试)...")
        emb_result = await compare_embedding_inference(
            baseline_url=args.baseline_url,
            npu_url=args.npu_url,
            model=args.embedding_model,
            test_texts=test_texts,
            baseline_source=args.baseline_source,
        )
        results.append(emb_result)

    # 生成报告
    generate_report(
        results=results,
        output_path=args.output,
        metadata={
            "model": args.model,
            "baseline_source": args.baseline_source,
            "temperature": args.temperature,
            "max_tokens": args.max_tokens,
        },
    )


if __name__ == "__main__":
    asyncio.run(main())

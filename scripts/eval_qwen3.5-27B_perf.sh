#!/bin/bash
# Qwen3.5-27B 性能评估脚本
# 三种模式: serve (在线吞吐), latency (延迟), throughput (离线吞吐)

set -e

MODEL_PATH="${MODEL_PATH:-Eco-Tech/Qwen3.5-27B-w8a8-mtp}"
RESULT_DIR="${RESULT_DIR:-./perf_results}"

mkdir -p "${RESULT_DIR}"

echo "=========================================="
echo "Qwen3.5-27B 性能评估"
echo "=========================================="
echo "模型: ${MODEL_PATH}"
echo "结果目录: ${RESULT_DIR}"
echo ""

# ===== serve 模式: 在线吞吐 (QPS, TTFT, TPOT) =====
echo "[1/3] serve 模式 (在线吞吐)..."
vllm bench serve \
    --model "${MODEL_PATH}" \
    --dataset-name random \
    --random-input 200 \
    --num-prompts 200 \
    --request-rate 1 \
    --save-result \
    --result-dir "${RESULT_DIR}" || echo "serve 模式失败"

echo ""

# ===== latency 模式: 单请求延迟 (P50/P90/P99) =====
echo "[2/3] latency 模式 (延迟)..."
vllm bench latency \
    --model "${MODEL_PATH}" \
    --input-len 200 \
    --output-len 200 \
    --num-iterations 10 || echo "latency 模式失败"

echo ""

# ===== throughput 模式: 离线吞吐 (tokens/sec) =====
echo "[3/3] throughput 模式 (离线吞吐)..."
vllm bench throughput \
    --model "${MODEL_PATH}" \
    --input-len 200 \
    --output-len 200 \
    --num-batches 16 || echo "throughput 模式失败"

echo ""
echo "=========================================="
echo "性能评估完成"
echo "结果目录: ${RESULT_DIR}"
echo "=========================================="

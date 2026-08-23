#!/bin/bash
# Qwen3.5-27B 精度评估脚本 (GSM8K)
# 参考 GSM8K accuracy: 96.74

set -e

MODEL_PATH="${MODEL_PATH:-Eco-Tech/Qwen3.5-27B-w8a8-mtp}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
VLLM_URL="http://${HOST}:${PORT}/v1"

echo "=========================================="
echo "Qwen3.5-27B 精度评估 (GSM8K)"
echo "=========================================="
echo "模型: ${MODEL_PATH}"
echo "参考准确率: 96.74%"
echo ""

# ===== 确保 lm-eval 已安装 =====
if ! command -v lm_eval &> /dev/null; then
    echo "安装 lm-eval-harness..."
    pip install lm-eval
fi

# ===== 运行 GSM8K 评估 =====
echo "开始 GSM8K 评估..."
lm_eval \
    --model vllm \
    --model_args "pretrained=${MODEL_PATH},tensor_parallel_size=1,data_parallel_size=1,max_model_len=8192,trust_remote_code=true,base_url=${VLLM_URL}" \
    --tasks gsm8k \
    --num_fewshot 5 \
    --batch_size 1

echo ""
echo "=========================================="
echo "精度评估完成"
echo "参考准确率: 96.74%"
echo "=========================================="

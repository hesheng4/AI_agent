#!/bin/bash
# Qwen3.5-27B vLLM 服务启动脚本
# 参考: https://docs.vllm.ai/projects/ascend/en/latest/tutorials/models/Qwen3.5-27B.html

set -e

# ===== 环境变量 =====
export VLLM_USE_MODELSCOPE=true
export PYTORCH_NPU_ALLOC_CONF=expandable_segments:True
export HCCL_BUFFSIZE=512
export OMP_PROC_BIND=false
export OMP_NUM_THREADS=1
export TASK_QUEUE_ENABLE=1

# ===== 参数 =====
MODEL_PATH="${MODEL_PATH:-Eco-Tech/Qwen3.5-27B-w8a8-mtp}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
TP_SIZE="${TP_SIZE:-2}"
DP_SIZE="${DP_SIZE:-1}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-133000}"
GPU_MEM_UTIL="${GPU_MEM_UTIL:-0.90}"
SERVED_NAME="${SERVED_NAME:-qwen3.5}"

echo "=========================================="
echo "Qwen3.5-27B vLLM 服务启动"
echo "=========================================="
echo "模型: ${MODEL_PATH}"
echo "端口: ${PORT}"
echo "TP: ${TP_SIZE}, DP: ${DP_SIZE}"
echo "Max Model Len: ${MAX_MODEL_LEN}"
echo "=========================================="

# ===== 硬件检查 =====
echo "[1/3] 硬件检查..."
if command -v npu-smi &> /dev/null; then
    npu-smi info
    echo "NPU 硬件检查通过"
else
    echo "警告: npu-smi 未找到，跳过硬件检查"
fi

# ===== 启动服务 =====
echo "[2/3] 启动 vLLM 服务..."
vllm serve "${MODEL_PATH}" \
  --host "${HOST}" \
  --port "${PORT}" \
  --data-parallel-size "${DP_SIZE}" \
  --tensor-parallel-size "${TP_SIZE}" \
  --seed 1024 \
  --quantization ascend \
  --served-model-name "${SERVED_NAME}" \
  --max-num-seqs 32 \
  --max-model-len "${MAX_MODEL_LEN}" \
  --max-num-batched-tokens 8096 \
  --trust-remote-code \
  --gpu-memory-utilization "${GPU_MEM_UTIL}" \
  --no-enable-prefix-caching \
  --compilation-config '{"cudagraph_mode":"FULL_DECODE_ONLY"}' \
  --additional-config '{"enable_cpu_binding":true}' \
  --async-scheduling &

VLLM_PID=$!
echo "vLLM 服务 PID: ${VLLM_PID}"

# ===== 等待就绪 =====
echo "[3/3] 等待服务就绪..."
MAX_WAIT=300
ELAPSED=0
while [ ${ELAPSED} -lt ${MAX_WAIT} ]; do
    if curl -s "http://${HOST}:${PORT}/v1/models" > /dev/null 2>&1; then
        echo "服务已就绪: http://${HOST}:${PORT}"
        echo ""
        echo "验证命令:"
        echo "  curl http://${HOST}:${PORT}/v1/chat/completions -H 'Content-Type: application/json' -d '{\"model\": \"${SERVED_NAME}\", \"messages\": [{\"role\": \"user\", \"content\": \"Hello\"}], \"max_completion_tokens\": 50}'"
        exit 0
    fi
    sleep 5
    ELAPSED=$((ELAPSED + 5))
    echo "等待中... (${ELAPSED}s / ${MAX_WAIT}s)"
done

echo "错误: 服务在 ${MAX_WAIT}s 内未就绪"
kill ${VLLM_PID} 2>/dev/null || true
exit 1

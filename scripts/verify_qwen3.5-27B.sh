#!/bin/bash
# Qwen3.5-27B 功能验证脚本
# 验证模型服务是否正常工作

set -e

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
MODEL="${MODEL:-qwen3.5}"
BASE_URL="http://${HOST}:${PORT}"

echo "=========================================="
echo "Qwen3.5-27B 功能验证"
echo "=========================================="

# ===== 检查服务状态 =====
echo "[1/3] 检查服务状态..."
if curl -s "${BASE_URL}/v1/models" | grep -q "qwen"; then
    echo "服务正常"
else
    echo "错误: 服务未响应"
    exit 1
fi

# ===== Completions 测试 =====
echo "[2/3] Completions 测试..."
RESPONSE=$(curl -s "${BASE_URL}/v1/completions" \
    -H "Content-Type: application/json" \
    -d '{
        "model": "'"${MODEL}"'",
        "prompt": "The future of AI is",
        "max_completion_tokens": 50,
        "temperature": 0
    }')

if echo "${RESPONSE}" | grep -q "choices"; then
    echo "Completions 测试通过"
    echo "响应: $(echo ${RESPONSE} | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["choices"][0]["text"][:100])' 2>/dev/null || echo '(解析失败)')"
else
    echo "Completions 测试失败"
    echo "响应: ${RESPONSE}"
fi

# ===== Chat Completions 测试 =====
echo "[3/3] Chat Completions 测试..."
RESPONSE=$(curl -s "${BASE_URL}/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d '{
        "model": "'"${MODEL}"'",
        "messages": [
            {"role": "user", "content": "Give me a short introduction to large language models."}
        ],
        "temperature": 0.6,
        "top_p": 0.95,
        "top_k": 20,
        "max_completion_tokens": 4096
    }')

if echo "${RESPONSE}" | grep -q "choices"; then
    echo "Chat Completions 测试通过"
    CONTENT=$(echo "${RESPONSE}" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["choices"][0]["message"]["content"][:200])' 2>/dev/null || echo '(解析失败)')
    echo "内容: ${CONTENT}"
else
    echo "Chat Completions 测试失败"
    echo "响应: ${RESPONSE}"
fi

echo ""
echo "=========================================="
echo "功能验证完成"
echo "=========================================="

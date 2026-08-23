# 精度对齐快速参考

## 本项目涉及的模型与基线

| 模型 | 类型 | 用途 | 官方基线来源 |
|------|------|------|------------|
| Qwen/Qwen2.5-72B-Instruct | LLM | 文献分析/写作/推理 | [Qwen 官方 README](https://huggingface.co/Qwen/Qwen2.5-72B-Instruct) |
| BAAI/bge-large-zh-v1.5 | Embedding | 向量检索/语义搜索 | [BGE 官方 README](https://huggingface.co/BAAI/bge-large-zh-v1.5) |

## 基线来源策略

1. **官方 README / 官方示例 / 官方 benchmark / 官方文档**（最高优先级）
2. **用户提供的 GPU 真实运行结果**（次优先级）
3. ❌ **禁止默认做 CPU vs NPU 作为最终结论**

## 预声明阈值

### LLM 推理

| 指标 | 阈值 | 说明 |
|------|------|------|
| exact_match | 1.0 | 贪婪解码应完全匹配 |
| token_match_rate | 1.0 | token 匹配率 |
| logit_atol | 1e-3 | logits 绝对误差 |
| logit_rtol | 1e-2 | logits 相对误差 |

### Embedding 推理

| 指标 | 阈值 | 说明 |
|------|------|------|
| emb_cosine_sim | 0.999 | 余弦相似度 |
| emb_l2_atol | 1e-3 | L2 距离绝对误差 |
| emb_element_atol | 1e-4 | 逐元素绝对误差 |
| emb_element_rtol | 1e-3 | 逐元素相对误差 |

## 对比约束（必须严格同条件）

- ✅ 同 seed、同 tokenizer、同解码参数
- ✅ 同 temperature=0（贪婪解码）、同 max_tokens
- ✅ 同 dtype、同 padding/truncation 策略
- ❌ 不能拿不同 seed 或不同 prompt 模板的结果直接对比

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| /api/v1/alignment/status | GET | 查看对齐状态 |
| /api/v1/alignment/run | POST | 触发精度对齐 |
| /api/v1/alignment/report | GET | 获取最新报告 |
| /api/v1/alignment/thresholds | GET | 查看预声明阈值 |
| /api/v1/alignment/constraints | GET | 查看默认对比约束 |

## CLI 使用

```bash
# 基本用法
python scripts/compare_inference.py \
    --baseline-url http://gpu-host:8001/v1 \
    --npu-url http://127.0.0.1:8001/v1 \
    --model Qwen/Qwen2.5-72B-Instruct

# 完整用法
python scripts/compare_inference.py \
    --baseline-url http://gpu-host:8001/v1 \
    --npu-url http://127.0.0.1:8001/v1 \
    --model Qwen/Qwen2.5-72B-Instruct \
    --test-file tests/alignment/test_prompts.jsonl \
    --temperature 0.0 \
    --max-tokens 128 \
    --baseline-source user_gpu_result \
    --compare-embedding \
    --embedding-model BAAI/bge-large-zh-v1.5 \
    --output reports/inference_alignment.json
```

## ⚠️ CPU 调试对比声明

如果使用 CPU 作为基线，报告中必须包含：

> 本次对比使用 CPU 结果，仅用于调试目的。不能证明 NPU 与官方模型一致，不能替代官方基线或用户 GPU 基线。

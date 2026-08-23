# 昇腾模型适配验证快速参考

## 验证流程

```
1. 环境预检 ──→ 2. 模型部署 ──→ 3. 执行验证 ──→ 4. 资源清理 ──→ 5. 生成报告
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/validator/status` | 验证模块状态 |
| GET | `/api/v1/validator/env-check` | Step 1: 环境预检 |
| POST | `/api/v1/validator/deploy-command` | Step 2: 生成 vLLM 启动命令 |
| POST | `/api/v1/validator/accuracy` | Step 3.1: 精度验证 |
| POST | `/api/v1/validator/benchmark/serve` | Step 3.2a: 在线吞吐 (QPS, TTFT, TPOT) |
| POST | `/api/v1/validator/benchmark/latency` | Step 3.2b: 延迟 (P50/P90/P99) |
| POST | `/api/v1/validator/benchmark/throughput` | Step 3.2c: 离线吞吐 (tokens/sec) |
| POST | `/api/v1/validator/run` | 一键完整验证 |
| GET | `/api/v1/validator/models` | 支持模型列表 |
| POST | `/api/v1/validator/preset/{model_name}` | 预设配置验证 |
| GET | `/api/v1/validator/quick-reference` | 快速参考 |

## CLI 编排器

```bash
# 一键完整验证
python scripts/validator.py \
    --model-path Eco-Tech/Qwen3.5-27B-w8a8-mtp \
    --model-name qwen3.5 \
    --quantized \
    --port 8000 \
    --tp-size 2

# 使用预设配置
python scripts/validator.py \
    --model-path Eco-Tech/Qwen3.5-27B-w8a8-mtp \
    --preset Qwen3.5-27B

# 仅环境检查
python scripts/validator.py --env-check-only

# 仅生成部署命令
python scripts/validator.py \
    --model-path Eco-Tech/Qwen3.5-27B-w8a8-mtp \
    --deploy-cmd-only

# 列出支持的模型
python scripts/validator.py --list-models
```

## Shell 脚本

| 脚本 | 功能 |
|------|------|
| `scripts/serve_qwen3.5-27B.sh` | Qwen3.5-27B 服务启动 |
| `scripts/verify_qwen3.5-27B.sh` | Qwen3.5-27B 功能验证 |
| `scripts/eval_qwen3.5-27B_accuracy.sh` | GSM8K 精度评估 |
| `scripts/eval_qwen3.5-27B_perf.sh` | 三模式性能评估 |

## Qwen3.5-27B 参考配置

| 参数 | 值 | 说明 |
|------|-----|------|
| model_path | `Eco-Tech/Qwen3.5-27B-w8a8-mtp` | 量化模型路径 |
| tp_size | 2 | 张量并行 |
| max_model_len | 133000 | 最大上下文 128K |
| quantization | ascend | 昇腾量化 |
| gpu_mem_util | 0.90 | 显存利用率 |
| compilation_config | `FULL_DECODE_ONLY` | 图编译模式 |
| GSM8K 准确率 | **96.74%** | 参考基线 |

## 必需环境变量

```bash
export VLLM_USE_MODELSCOPE=true
export PYTORCH_NPU_ALLOC_CONF=expandable_segments:True
export HCCL_BUFFSIZE=512
export OMP_PROC_BIND=false
export OMP_NUM_THREADS=1
export TASK_QUEUE_ENABLE=1
```

## 性能基准测试模式

| 模式 | 说明 | 关键指标 |
|------|------|----------|
| `serve` | 在线吞吐 | QPS, TTFT (ms), TPOT (ms) |
| `latency` | 单请求延迟 | P50/P90/P99 (ms) |
| `throughput` | 离线吞吐 | tokens/sec |

## 验证报告格式

```json
{
  "success": true,
  "summary": "验证完成，耗时 320.5 秒",
  "detailed_report": {
    "environment_check": { "npu_smi": true, "vllm_installed": true },
    "deploy_status": "passed",
    "accuracy_evaluation": [
      { "dataset": "chat_completions", "status": "passed" },
      { "dataset": "gsm8k", "accuracy": 96.74, "reference_value": 96.74 }
    ],
    "performance_benchmarks": {
      "serve": { "qps": 45.2, "ttft_ms": 120, "tpot_ms": 35 },
      "latency": { "p50_ms": 85, "p90_ms": 150 },
      "throughput": { "tokens_per_sec": 1250 }
    }
  },
  "logs": ["步骤1完成", "服务启动成功"],
  "report_path": "./validation_reports/validation_Qwen3_5-27B_20250101_120000.json"
}
```

## 错误处理

| 场景 | 行为 |
|------|------|
| 环境检查失败 | 记录错误，直接返回失败报告 |
| 服务启动失败 | 捕获异常，清理进程，报告原因 |
| API 调用超时 | 60s 超时，自动重试 2 次 |
| 测试执行失败 | 记录失败环节，继续后续测试 |

## 参考文档

- [Qwen3.5-27B 部署教程](https://docs.vllm.ai/projects/ascend/en/latest/tutorials/models/Qwen3.5-27B.html)
- [AISBench 精度评估](https://docs.vllm.ai/projects/ascend/en/latest/developer_guide/evaluation/using_ais_bench.html)
- [vLLM Benchmark](https://docs.vllm.ai/en/latest/contributing/benchmarks.html)

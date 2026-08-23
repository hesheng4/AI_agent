# 昇腾 NPU 推理工具链快速参考

## 工作流总览

```
1. 硬件检查 → 2. 环境设置 → 3. 安装 vLLM → 4. 启动服务 → 5. [可选] 量化/评测
```

## 必需环境变量

| 变量 | 值 | 说明 |
|------|-----|------|
| `VLLM_WORKER_MULTIPROC_METHOD` | `spawn` | vLLM 多进程必需 |
| `VLLM_USE_MODELSCOPE` | `true` | 国内推荐，加速模型下载 |
| `ASCEND_RT_VISIBLE_DEVICES` | `0,1,2,3` | 控制 vLLM 和 msmodelslim 可见 NPU |
| `TASK_QUEUE_ENABLE` | `2` | 性能优化：流水并行 |
| `PYTORCH_NPU_ALLOC_CONF` | `expandable_segments` | 内存分配优化 |
| `ASCEND_ENABLE_ACL_GRAPH` | `1` | ACL Graph 加速 |

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/toolchain/status` | 工具链状态 |
| GET | `/api/v1/toolchain/hardware-check` | NPU 硬件检查（npu-smi info） |
| GET | `/api/v1/toolchain/env-setup` | 推荐环境变量 |
| GET | `/api/v1/toolchain/verify-environment` | 完整环境验证 |
| GET | `/api/v1/toolchain/vllm-install-guide` | vLLM-Ascend 安装指引 |
| POST | `/api/v1/toolchain/vllm-launch` | 生成 vLLM 启动命令 |
| POST | `/api/v1/toolchain/vllm-diagnose` | 诊断 vLLM 运行错误 |
| POST | `/api/v1/toolchain/quantize` | 生成 msmodelslim 量化脚本 |
| POST | `/api/v1/toolchain/sensitivity` | 生成敏感度分析脚本 |
| POST | `/api/v1/toolchain/aisbench` | 生成 AISBench 评测脚本 |
| POST | `/api/v1/toolchain/recommended-config` | 推荐运行配置 |
| GET | `/api/v1/toolchain/quick-reference` | 快速参考 |

## 量化迭代流程

1. 运行量化脚本生成量化模型
2. 启动量化后的 vLLM 服务进行推理验证
3. 如精度不达标，使用 `/toolchain/sensitivity` 敏感度分析
4. 根据敏感度结果跳过敏感层重新量化
5. 使用 `/toolchain/aisbench` 评测最终精度

## 常见故障排查

| 问题 | 解决方案 |
|------|----------|
| OOM | 减小 `max_model_len`，降低 `gpu_memory_utilization`，增大 TP |
| HCCL 初始化失败 | `export HCCL_CONNECT_TIMEOUT=7200`，检查 NPU 间网络 |
| Worker 崩溃 | 确认 `VLLM_WORKER_MULTIPROC_METHOD=spawn` |
| torch_npu 导入失败 | `pip install torch_npu`，版本匹配 PyTorch |
| 模型下载超时 | 设置 `VLLM_USE_MODELSCOPE=true` |
| 首次推理慢 | 正常现象（算子编译），后续加速；可调用 `/ascend/warmup` 预热 |

## 模型 TP 推荐配置

| 模型规模 | 推荐 TP | NPU 卡数 |
|----------|---------|----------|
| 7B/8B | 1 | 1 |
| 13B/14B | 2 | 2 |
| 32B/34B | 4 | 4 |
| 70B/72B | 4 | 4 |
| 110B+ | 8 | 8 |
| MoE (如 DeepSeek-V3) | 8 | 8+ (启用 EP) |

## 源码调试技巧

```bash
# 查找可编辑源码位置
pip show vllm-ascend
pip show torch_npu
pip show msmodelslim

# 直接修改源码进行深度调试
# Location: /path/to/site-packages/...
```

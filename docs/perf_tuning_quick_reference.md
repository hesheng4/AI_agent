# 昇腾 NPU 性能调优快速参考

## 调优流程

```
0. 环境准备与基线性能采集
→ 1. 流水优化（TASK_QUEUE_ENABLE）
→ 2. CPU 绑核优化（CPU_AFFINITY_CONF）
→ 3. 高性能内存库替换（tcmalloc）
→ 4. 调优效果验证
→ 5. [进阶·需确认] Python 编译优化（LTO + PGO）
→ 6. [进阶·需确认] PyTorch 编译优化（LTO + PGO）
→ 7. [进阶·需确认] torch_npu 编译优化（LTO + PGO）
→ 8. 最终效果验证
```

## ⚠️ 渐进式调优原则

1. **逐项开启**：流水优化 → 绑核优化 → tcmalloc 替换，每次只变更一个配置
2. **负优化回退**：如果某项叠加后性能不升反降，应将其去掉，用剩余项重新测试
3. **编译优化为进阶手段**：需用户确认后才执行，耗时较长

## 优化项速查

| 优化项 | 环境变量 / 方式 | 适用场景 | 风险 |
|--------|----------------|----------|------|
| 流水优化 | `TASK_QUEUE_ENABLE=2` | host-bound 网络 | 内存峰值上升 |
| 粗粒度绑核 | `CPU_AFFINITY_CONF=1` | CPU 瓶颈模型 | vLLM 等推理框架可能负优化 |
| 细粒度绑核 | `CPU_AFFINITY_CONF=2` | CPU 瓶颈 + 核间切换 | 同上 |
| tcmalloc | `LD_PRELOAD=...libtcmalloc.so` | 频繁内存分配 | 需安装 gperftools |
| 内存分配策略 | `PYTORCH_NPU_ALLOC_CONF=expandable_segments` | 内存碎片化 | — |
| ACL Graph | `ASCEND_ENABLE_ACL_GRAPH=1` | 固定计算图 | — |
| Python 编译优化 | 毕昇编译器 + `--with-lto --enable-optimizations` | 所有场景 | 需从源码重编 Python |
| PyTorch 编译优化 | 毕昇编译器 + LTO + PGO | Torch 模型 | 需从源码重编，耗时长 |
| torch_npu 编译优化 | 毕昇编译器 + LTO + PGO | Torch 模型 | 依赖重编后的 PyTorch |

## 推荐组合配置

### 训练场景（默认）
```bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh
export TASK_QUEUE_ENABLE=2
export CPU_AFFINITY_CONF=1
export LD_PRELOAD="$LD_PRELOAD:/path/to/libtcmalloc.so"
export PYTORCH_NPU_ALLOC_CONF=expandable_segments
export ASCEND_ENABLE_ACL_GRAPH=1
```

### vLLM 推理场景
```bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh
export TASK_QUEUE_ENABLE=2
# 不启用绑核 — vLLM 可能负优化
export LD_PRELOAD="$LD_PRELOAD:/path/to/libtcmalloc.so"
export PYTORCH_NPU_ALLOC_CONF=expandable_segments
```

### 保守配置（调试用）
```bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh
export TASK_QUEUE_ENABLE=1
# 不启用绑核和 tcmalloc
export PYTORCH_NPU_ALLOC_CONF=expandable_segments
```

## CLI 使用

```bash
# 使用推荐配置调优
python scripts/run_perf_tuning.py apply --scenario training_default

# vLLM 推理场景
python scripts/run_perf_tuning.py apply --scenario inference_vllm

# 检测 tcmalloc
python scripts/run_perf_tuning.py detect-tcmalloc

# 检测 NUMA 拓扑
python scripts/run_perf_tuning.py detect-numa

# 生成 Python 编译脚本
python scripts/run_perf_tuning.py compile python --pgo

# 生成 PyTorch PGO 编译脚本
python scripts/run_perf_tuning.py compile pytorch --version 2.1.0 --pgo

# 生成 torch_npu PGO 编译脚本
python scripts/run_perf_tuning.py compile torch_npu --version 2.1.0 --pgo

# 生成启动命令
python scripts/run_perf_tuning.py launch --scenario training_default --script train.py
```

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| /api/v1/perf-tuning/status | GET | 调优模块状态 |
| /api/v1/perf-tuning/recommended-configs | GET | 推荐配置 |
| /api/v1/perf-tuning/apply | POST | 应用调优配置（渐进式） |
| /api/v1/perf-tuning/launch-command | POST | 生成启动命令 |
| /api/v1/perf-tuning/detect-tcmalloc | GET | 检测 tcmalloc |
| /api/v1/perf-tuning/detect-numa | GET | 检测 NUMA 拓扑 |
| /api/v1/perf-tuning/quick-reference | GET | 快速参考 |
| /api/v1/perf-tuning/verify-env | GET | 验证环境变量 |
| /api/v1/perf-tuning/generate-compile-script/python | POST | Python 编译脚本 |
| /api/v1/perf-tuning/generate-compile-script/pytorch | POST | PyTorch 编译脚本 |
| /api/v1/perf-tuning/generate-compile-script/torch-npu | POST | torch_npu 编译脚本 |

## 注意事项

1. **ASCEND_LAUNCH_BLOCKING=1** 时 task_queue 算子队列关闭，TASK_QUEUE_ENABLE 设置不生效
2. **TASK_QUEUE_ENABLE=2** 可能导致 NPU 内存峰值上升，如遇 OOM 请减小 batch_size 或回退到 1
3. **CPU 绑核对 vLLM** 等推理框架可能负优化，先单独测试效果
4. **编译优化顺序**：Python → PyTorch → torch_npu，必须按此顺序执行
5. **配合 Profiling**：调优前后各采集一次 L0 Profiling 量化收益
6. **不要修改 CUDA 代码**：torch_npu 的 transfer_to_npu 会自动迁移 CUDA 调用

## 参考资料

- [流水优化](https://www.hiascend.com/document/detail/zh/Pytorch/600/ptmoddevg/trainingmigrguide/performance_tuning_0058.html)
- [绑核优化](https://www.hiascend.com/document/detail/zh/Pytorch/600/ptmoddevg/trainingmigrguide/performance_tuning_0059.html)
- [高性能内存库替换](https://www.hiascend.com/document/detail/zh/Pytorch/600/ptmoddevg/trainingmigrguide/performance_tuning_0067.html)
- [编译优化-Python](https://www.hiascend.com/document/detail/zh/Pytorch/600/ptmoddevg/trainingmigrguide/performance_tuning_0063.html)
- [编译优化-PyTorch](https://www.hiascend.com/document/detail/zh/Pytorch/600/ptmoddevg/trainingmigrguide/performance_tuning_0064.html)
- [编译优化-torch_npu](https://www.hiascend.com/document/detail/zh/Pytorch/600/ptmoddevg/trainingmigrguide/performance_tuning_0065.html)

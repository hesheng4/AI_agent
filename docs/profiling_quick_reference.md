# 昇腾 NPU Profiling 快速参考

## 工作流总览

```
1. 环境验证 → 2. 采集 Profiling → 3. 分析结果 → 4. 性能调优
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/profiling/status` | Profiling 模块状态 |
| POST | `/api/v1/profiling/collect` | 采集 Profiling 数据 |
| GET | `/api/v1/profiling/results/{task_id}` | 获取采集结果 |
| POST | `/api/v1/profiling/analyze` | 分析 Profiling 数据 |
| GET | `/api/v1/profiling/checklist` | Profiling 分析检查清单 |

## Profiling 级别

| 级别 | 名称 | 采集内容 |
|------|------|----------|
| L0 | 算子级 | 算子耗时、调用次数 |
| L1 | 模块级 | 模块调用栈、计算图 |
| L2 | 系统级 | 内存、通信、流水线分析 |

## 环境要求

- CANN Toolkit 已安装
- torch_npu 已安装
- `source /usr/local/Ascend/ascend-toolkit/set_env.sh`

## 分析检查清单

1. 检查算子耗时分布，找出 Top-10 耗时算子
2. 检查通信开销（HCCL AllReduce 等）
3. 检查内存使用峰值和碎片
4. 检查 CPU-GPU 流水是否有气泡
5. 检查算子是否已融合（ACL Graph 命中率）

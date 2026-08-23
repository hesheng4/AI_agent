# Research Agent Platform - 昇腾 NPU 适配指南

## 概述

本项目已完成昇腾 NPU 适配，支持基于 vLLM-Ascend 的本地大模型推理和 Embedding 服务，
实现全本地化的行业 Agent 推理能力，无需依赖远程 API。

## 架构

```
┌─────────────────────────────────────────────────┐
│              Research Agent Platform              │
├─────────────────────────────────────────────────┤
│  LLM Client    │  Embedding Client  │  Agents   │
│  (remote/ascend)│  (remote/ascend)  │           │
├─────────────────────────────────────────────────┤
│           app/core/ascend.py                     │
│  ┌──────────────┐  ┌──────────────────────────┐ │
│  │AscendNPUManager│  │VLLMAscendClient          │ │
│  │(环境检测/设备管理)│  │(Chat/Embedding API)     │ │
│  └──────────────┘  └──────────────────────────┘ │
│  ┌──────────────────────────────────────────────┐│
│  │NPULocalEmbedding (torch_npu 本地推理)         ││
│  └──────────────────────────────────────────────┘│
├─────────────────────────────────────────────────┤
│           vLLM-Ascend 推理服务                    │
│  ┌──────────────────┐ ┌────────────────────────┐│
│  │ Qwen2.5-72B (TP=4)│ │ bge-large-zh (Embed)  ││
│  │ :8001             │ │ :8002                  ││
│  └──────────────────┘ └────────────────────────┘│
├─────────────────────────────────────────────────┤
│           昇腾 NPU 硬件层                         │
│  Ascend 910B/910C × N 卡  │  CANN >= 8.0        │
└─────────────────────────────────────────────────┘
```

## 快速开始

### 1. 环境准备

#### 硬件要求
- 昇腾 910B/910C 系列 NPU（≥2 卡推荐）
- 内存 ≥ 128GB（72B 模型需要）
- 磁盘空间 ≥ 200GB（模型文件）

#### 软件要求
- CANN >= 8.0
- Python 3.10（推荐）
- PyTorch >= 2.1.0（需匹配 CANN 版本）
- torch_npu（需匹配 CANN 版本）

### 2. 环境预检

```bash
python scripts/check_npu_env.py
```

该脚本会检查：
- Python 版本
- torch / torch_npu 安装
- NPU 设备可用性
- vLLM-Ascend 服务连通性
- 项目配置

### 3. 配置

复制环境配置模板并修改：

```bash
cp .env.ascend .env
```

关键配置项：

| 配置 | 说明 | 推荐值 |
|------|------|--------|
| `LLM_MODE` | LLM 推理模式 | `ascend` |
| `ASCEND_VLLM_BASE_URL` | vLLM-Ascend 地址 | `http://127.0.0.1:8001/v1` |
| `ASCEND_LLM_MODEL` | LLM 模型名称 | `Qwen/Qwen2.5-72B-Instruct` |
| `ASCEND_TP_SIZE` | 张量并行度 | 4（4卡）/ 8（8卡） |
| `EMBEDDING_MODE` | Embedding 模式 | `ascend_api` |
| `ASCEND_EMBEDDING_MODEL` | Embedding 模型 | `BAAI/bge-large-zh-v1.5` |

### 4. 启动 vLLM-Ascend 服务

#### LLM 服务

```bash
vllm serve /models/Qwen2.5-72B-Instruct \
    --tensor-parallel-size 4 \
    --dtype bfloat16 \
    --max-model-len 8192 \
    --max-num-seqs 16 \
    --port 8001 \
    --trust-remote-code
```

#### Embedding 服务

```bash
vllm serve /models/bge-large-zh-v1.5 \
    --task embed \
    --dtype bfloat16 \
    --max-model-len 512 \
    --port 8002
```

### 5. 启动应用

```bash
# 安装依赖
pip install -r requirements.ascend.txt

# 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 6. Docker 部署（推荐）

```bash
# 使用 docker-compose 一键部署
docker-compose -f docker-compose.ascend.yml up -d
```

包含服务：
- `vllm-ascend` — LLM 推理服务（4×NPU）
- `vllm-embedding` — Embedding 服务（1×NPU）
- `research-agent` — 应用主服务
- `milvus` — 向量数据库
- `redis` — 缓存

## API 接口

### 昇腾状态 API

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/ascend/info` | GET | 获取 NPU 环境信息 |
| `/api/v1/ascend/vllm-health` | GET | 检查 vLLM-Ascend 健康状态 |
| `/api/v1/ascend/warmup` | POST | 预热推理服务 |

### 健康检查

```bash
curl http://localhost:8000/health
```

返回包含 NPU 状态和 vLLM-Ascend 连通性的信息。

## 模式切换

项目支持三种 LLM 模式和三种 Embedding 模式，通过环境变量一键切换：

### LLM 模式

| 模式 | 配置 | 说明 |
|------|------|------|
| 远程 API | `LLM_MODE=remote` | 使用 OpenAI 兼容远程 API |
| 昇腾 NPU | `LLM_MODE=ascend` | 使用本地 vLLM-Ascend |

### Embedding 模式

| 模式 | 配置 | 说明 |
|------|------|------|
| 远程 API | `EMBEDDING_MODE=remote` | 使用远程 Embedding API |
| vLLM-Ascend | `EMBEDDING_MODE=ascend_api` | 使用 vLLM-Ascend Embedding 端点 |
| 本地推理 | `EMBEDDING_MODE=ascend_local` | 使用 torch_npu + sentence-transformers |

## 性能优化

### NPU 性能调优参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `ASCEND_ENABLE_ACL_GRAPH` | `true` | ACL Graph 加速（推荐开启） |
| `ASCEND_TASK_QUEUE_ENABLE` | `1` | Task Queue 并行下发 |
| `ASCEND_CPU_AFFINITY` | `0` | CPU 绑核优化 |
| `ASCEND_ALLOC_CONF` | `expandable_segments` | 内存分配策略 |
| `ASCEND_RT_VISIBLE_DEVICES` | `""` | 可见 NPU 设备 |

### 推荐配置

- **4 卡环境**：TP=4, Qwen2.5-72B-Instruct, max_model_len=8192
- **8 卡环境**：TP=8, DeepSeek-V3, max_model_len=16384
- **2 卡环境**：TP=2, Qwen2.5-14B-Instruct, max_model_len=4096

## 故障排查

### 常见问题

1. **NPU 不可用**
   - 检查 CANN 驱动安装：`npu-smi info`
   - 检查 torch_npu：`python -c "import torch_npu; print(torch.npu.is_available())"`

2. **vLLM-Ascend 连接失败**
   - 确认服务已启动：`curl http://127.0.0.1:8001/v1/models`
   - 检查端口占用：`netstat -tlnp | grep 8001`

3. **OOM (Out of Memory)**
   - 减少 `ASCEND_TP_SIZE` 或使用更小模型
   - 减少 `ASCEND_MAX_MODEL_LEN`
   - 减少 `--max-num-seqs`

4. **推理速度慢**
   - 开启 `ASCEND_ENABLE_ACL_GRAPH=true`
   - 开启 `ASCEND_TASK_QUEUE_ENABLE=1`
   - 检查 NPU 利用率：`npu-smi info`

## 文件清单

| 文件 | 说明 |
|------|------|
| `app/core/ascend.py` | 昇腾核心模块（NPU管理、vLLM客户端、本地Embedding） |
| `app/config.py` | 配置（含昇腾配置项） |
| `app/utils/llm.py` | 统一 LLM 客户端（remote/ascend 双模式） |
| `app/utils/embedding.py` | 统一 Embedding 客户端（三模式） |
| `app/api/v1/ascend.py` | 昇腾状态 API |
| `app/main.py` | 应用入口（含昇腾初始化） |
| `scripts/check_npu_env.py` | NPU 环境预检脚本 |
| `.env.ascend` | 昇腾环境配置模板 |
| `docker-compose.ascend.yml` | 昇腾 Docker Compose |
| `Dockerfile.ascend` | 昇腾 Dockerfile |
| `requirements.ascend.txt` | 昇腾版依赖 |

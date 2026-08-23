# 昇腾 NPU Skills 使用流程与规范

## 一、技能体系总览

### 1.1 技能分层架构

```
┌─────────────────────────────────────────────────────────┐
│                    总入口层 (Entry)                       │
│  ai4s-main ─── 路由判断，分流到五条主路线                   │
└──────────────────────┬──────────────────────────────────┘
                       │
        ┌──────────────┼──────────────────────────┐
        │              │                          │
┌───────▼──────┐ ┌─────▼──────┐ ┌────────────────▼──────────────┐
│  模型迁移层    │ │  验证部署层  │ │        优化调优层              │
│  (Migration)  │ │  (Verify)  │ │     (Optimization)            │
│               │ │            │ │                               │
│ ai4s-basic    │ │ verify-agent      ai4s-precision-alignment  │
│ adapt-agent   │ │ verify-agent-plus ai4s-profiling            │
│ tf-to-pytorch │ │ quantify-agent    ai4s-perf-tuning          │
│ ascend-tf-    │ │                   ascend-optimization       │
│  community    │ │                   optimizer-agent            │
│               │ │                   optimizer-agent-plus       │
│ [模型专属]     │ │                                            │
│ boltz2        │ │                                            │
│ boltzgen      │ │                                            │
│ deepfri       │ │                                            │
│ deepfri-tf-npu│ │                                            │
│ diffsbdd      │ │                                            │
│ generator     │ │                                            │
│ goedel-prover │ │                                            │
│ oligoformer   │ │                                            │
│ proteinbert   │ │                                            │
└───────────────┘ └────────────┘ └───────────────────────────────┘
        │              │                     │
        └──────────────┼─────────────────────┘
                       │
              ┌────────▼────────┐
              │   辅助工具层      │
              │  (Utilities)     │
              │                  │
              │ ascend-history-  │
              │  to-skill        │
              │ gitcode-publish  │
              └─────────────────┘
```

### 1.2 技能分类速查

| 层级 | 技能名 | 用途 | 触发词示例 |
|------|--------|------|-----------|
| **总入口** | ai4s-main | 路由分流 | "AI4S"、"昇腾迁移"、"帮我迁到昇腾" |
| **通用迁移** | ai4s-basic | PyTorch 模型通用迁移 | "昇腾迁移"、"NPU 适配"、"CUDA 转 NPU" |
| **通用迁移** | adapt-agent | vLLM-Ascend 模型适配 | "adapt agent"、"vLLM 适配新模型" |
| **TF 框架** | tf-to-pytorch | TF→PyTorch 改写 | "TF 转 PyTorch"、"Keras 迁移" |
| **TF 框架** | ascend-tf-community | TF 原生昇腾部署 | "TF 昇腾"、"npu_device" |
| **验证部署** | verify-agent | vLLM 模型部署验证 | "验证模型部署"、"verify-agent" |
| **验证部署** | verify-agent-plus | 部署+精度+性能一站式验证 | "一键验证"、"验证报告" |
| **验证部署** | quantify-agent | 量化工具链入口 | "模型量化"、"msmodelslim" |
| **精度对齐** | ai4s-precision-alignment | GPU vs NPU 精度对比 | "精度对齐"、"dump 定位"、"loss 对比" |
| **性能采集** | ai4s-profiling | NPU Profiling 采集 | "profiling"、"性能采集" |
| **性能调优** | ai4s-perf-tuning | OS/调度级性能调优 | "性能调优"、"CPU 绑核"、"tcmalloc" |
| **推理优化** | ascend-optimization | torch_npu 推理优化 | "torch_npu 优化"、"推理优化" |
| **推理优化** | optimizer-agent | vLLM-Ascend 交互式优化 | "优化 vLLM"、"调优 Ascend" |
| **推理优化** | optimizer-agent-plus | vLLM-Ascend 深度优化 | "vLLM 性能调优"、"TPOT 延迟" |
| **亲和算子** | ascend-affinity-operator | 融合算子替换 | "亲和算子"、"算子替换" |
| **辅助** | ascend-history-to-skill | 历史记录转技能 | "从历史里找"、"整理成 skill" |
| **辅助** | gitcode-publish | GitCode 发布 | "发布到 GitCode" |

---

## 二、核心使用流程

### 2.1 总体决策树

用户提出昇腾相关需求时，按以下决策树选择技能：

```
用户需求
  │
  ├─ 是否涉及具体模型名？
  │   ├─ 是 → 查模型分流表（2.2节）
  │   └─ 否 → 继续
  │
  ├─ 原项目框架？
  │   ├─ TensorFlow/Keras → 是否保留 TF？
  │   │   ├─ 保留 TF → ascend-tf-community
  │   │   └─ 转 PyTorch → tf-to-pytorch
  │   ├─ PyTorch → 继续
  │   └─ vLLM → adapt-agent
  │
  ├─ 当前阶段？
  │   ├─ 尚未迁移 → ai4s-basic（通用迁移）
  │   ├─ 已迁移，需验证 → verify-agent / verify-agent-plus
  │   ├─ 已迁移，精度不对 → ai4s-precision-alignment
  │   ├─ 已迁移，需量化 → quantify-agent
  │   ├─ 已跑通，需采集热点 → ai4s-profiling
  │   ├─ 已跑通，需提升性能 → ai4s-perf-tuning / ascend-optimization
  │   └─ vLLM 部署优化 → optimizer-agent / optimizer-agent-plus
  │
  └─ 不确定 → ai4s-main（总入口自动分流）
```

### 2.2 模型分流表

| 模型名 | 推荐技能 | 备选技能 | 说明 |
|--------|---------|---------|------|
| Boltz2 | boltz2 | ai4s-basic | 蛋白质结构预测 |
| BoltzGen | boltzgen | ai4s-basic | 蛋白质生成 |
| DeepFRI（保留TF） | deepfri-tf-npu | ascend-tf-community | TF 原生部署 |
| DeepFRI（转PyTorch） | deepfri | tf-to-pytorch | TF→PyTorch→NPU |
| DiffSBDD | diffsbdd | ai4s-basic | 药物分子设计 |
| GENERator | generator | ai4s-basic | DNA 序列生成 |
| Goedel-Prover | goedel-prover | adapt-agent | vLLM 定理证明 |
| OligoFormer | oligoformer | ai4s-basic | siRNA 效能预测 |
| ProteinBERT | proteinbert | tf-to-pytorch | 蛋白语言模型 |
| 其他新模型 | ai4s-basic | — | 通用迁移，完成后沉淀 |

### 2.3 六大典型工作流

---

#### 工作流 A：全新 AI4S 模型迁移（PyTorch）

```
阶段1: 环境准备
  ┌──────────────────────────────────────┐
  │ 1. npu-smi info 确认硬件              │
  │ 2. source set_env.sh 拉起 CANN       │
  │ 3. conda create + pip install        │
  │ 4. python -c "import torch_npu" 验证 │
  └──────────────┬───────────────────────┘
                 │
阶段2: 代码迁移 ──→ 触发 ai4s-basic
  ┌──────────────────────────────────────┐
  │ 1. 分析 CUDA 依赖                    │
  │ 2. 入口注入 transfer_to_npu          │
  │ 3. 手动修复不兼容 API                │
  │ 4. 分布式改造 nccl → hccl           │
  │ 5. 第三方库适配                      │
  └──────────────┬───────────────────────┘
                 │
阶段3: 推理验证
  ┌──────────────────────────────────────┐
  │ 1. 单卡推理跑通                      │
  │ 2. 输出数值合理性检查                 │
  │ 3. 如有 GPU 基线 → 精度对比          │
  └──────────────┬───────────────────────┘
                 │
阶段4: 精度对齐（可选）──→ 触发 ai4s-precision-alignment
  ┌──────────────────────────────────────┐
  │ 1. 采集 GPU baseline dump            │
  │ 2. 采集 NPU dump                     │
  │ 3. 逐层对比，定位首漂移              │
  │ 4. 修复精度差异                      │
  └──────────────┬───────────────────────┘
                 │
阶段5: 性能优化（可选）──→ 触发 ai4s-perf-tuning / ascend-optimization
  ┌──────────────────────────────────────┐
  │ 1. profiling 采集热点                │
  │ 2. 调度/OS 级优化                    │
  │ 3. 亲和算子替换                      │
  │ 4. 性能基准测试                      │
  └──────────────┬───────────────────────┘
                 │
阶段6: 沉淀 ──→ 触发 ascend-history-to-skill
  ┌──────────────────────────────────────┐
  │ 1. 整理迁移步骤                      │
  │ 2. 生成模型专属 skill                │
  │ 3. 可选: gitcode-publish 发布        │
  └──────────────────────────────────────┘
```

---

#### 工作流 B：TF/Keras 模型迁移

```
用户需求: TF/Keras 模型 → 昇腾
         │
         ├─ 保留 TF 运行时？
         │   │
         │   ├─ 是 ──→ ascend-tf-community
         │   │         1. aarch64 编译 TF 2.6.5
         │   │         2. 安装 tfplugin
         │   │         3. npu_device.open().as_default()
         │   │         4. 精度验证
         │   │
         │   └─ 否，转 PyTorch ──→ tf-to-pytorch
         │                  1. 层级映射（Dense→Linear 等）
         │                  2. 权重转换（kernel 转置等）
         │                  3. 逐层数值验证
         │                  4. 端到端精度对比
         │                  5. 再走 ai4s-basic 迁移到 NPU
         │
         └─ 有模型专属 skill？
             ├─ DeepFRI+TF → deepfri-tf-npu
             ├─ DeepFRI+PyTorch → deepfri
             └─ ProteinBERT → proteinbert
```

---

#### 工作流 C：vLLM-Ascend 模型适配

```
用户需求: 新模型 → vLLM-Ascend 部署
         │
         ├─ 适配新模型 ──→ adapt-agent
         │   1. 收集模型上下文
         │   2. 分析模型架构
         │   3. 算子兼容性门控
         │   4. 框架侧代码分析
         │   5. 实现适配代码
         │   6. 两阶段验证
         │   7. 交付文档
         │
         ├─ 验证已适配模型 ──→ verify-agent / verify-agent-plus
         │   1. 环境预检
         │   2. 模型服务部署
         │   3. 精度测试
         │   4. 性能基准测试
         │   5. 资源清理 + 报告生成
         │
         └─ 优化 vLLM 性能 ──→ optimizer-agent / optimizer-agent-plus
             1. 收集部署配置
             2. 输出优化方案
             3. 用户确认后执行
             4. 验证优化效果
```

---

#### 工作流 D：精度对齐

```
用户需求: GPU vs NPU 精度不一致
         │
         └─→ ai4s-precision-alignment
             1. 确认基线来源（GPU / 官方基准）
             2. 采集 baseline dump（GPU 侧）
             3. 采集 NPU dump
             4. 逐层对比，定位首漂移层
             5. 分析根因（算子精度/eps/数据类型）
             6. 修复并验证
             7. 输出对齐报告
```

---

#### 工作流 E：性能调优

```
用户需求: NPU 上性能不达标
         │
         ├─ 先采集热点 ──→ ai4s-profiling
         │   1. torch_npu.profiler 采集 L0/L1/L2
         │   2. 分析算子耗时、调用栈、内存
         │   3. 输出瓶颈报告
         │
         └─ 根据瓶颈选调优方式
             │
             ├─ 调度/OS 级 ──→ ai4s-perf-tuning
             │   • TASK_QUEUE_ENABLE 流水优化
             │   • CPU_AFFINITY_CONF 绑核
             │   • tcmalloc 内存库替换
             │   • 毕昇编译器 LTO + PGO
             │
             ├─ 推理算子级 ──→ ascend-optimization
             │   • RMSNorm → npu_rms_norm
             │   • SwiGLU → npu_swiglu
             │   • Attention → npu_fusion_attention
             │   • RoPE → npu_rotary_mul
             │
             └─ vLLM 部署级 ──→ optimizer-agent-plus
                 • TPOT 延迟优化
                 • 吞吐量优化
                 • 多卡并行配置
```

---

#### 工作流 F：模型量化

```
用户需求: 模型量化部署
         │
         └─→ quantify-agent
             1. 确认模型和硬件
             2. msmodelslim 量化
             3. 精度评估（AISBench）
             4. vLLM-Ascend 部署验证
             5. 性能基准测试
```

---

## 三、使用规范

### 3.1 环境规范

#### 3.1.1 硬件要求

| 项目 | 最低要求 | 推荐配置 |
|------|---------|---------|
| NPU 芯片 | Ascend 910 / 910B | Ascend 910B / 910C |
| 驱动 | npu-smi info 正常 | 最新稳定版 |
| 操作系统 | Linux aarch64 | EulerOS / Ubuntu 22.04 |
| 内存 | ≥ 64 GB | ≥ 256 GB |

#### 3.1.2 软件版本约定

| 组件 | 版本要求 | 检查命令 |
|------|---------|---------|
| CANN Toolkit | ≥ 8.2 | `cat /usr/local/Ascend/ascend-toolkit/latest/version.cfg` |
| Python | 3.10 / 3.11 | `python --version` |
| PyTorch | 与 CANN 匹配 | `python -c "import torch; print(torch.__version__)"` |
| torch_npu | 与 PyTorch 同版本 | `python -c "import torch_npu; print(torch_npu.__version__)"` |

#### 3.1.3 环境初始化标准流程

每次开始工作前，必须执行：

```bash
# 1. 拉起 CANN 环境
source /usr/local/Ascend/ascend-toolkit/set_env.sh

# 2. 激活 Conda 环境
conda activate <env_name>

# 3. 验证 NPU 可用
npu-smi info
python -c "import torch, torch_npu; print(f'torch={torch.__version__}, torch_npu={torch_npu.__version__}'); a = torch.randn(3,4).npu(); print('NPU OK:', (a+a).shape)"
```

### 3.2 迁移规范

#### 3.2.1 代码迁移检查清单

- [ ] 入口文件顶部注入 `import torch_npu; from torch_npu.contrib import transfer_to_npu`
- [ ] 搜索并替换所有 `torch.cuda` 硬编码为兼容写法
- [ ] 搜索 `autocast("cuda")` 替换为 `autocast("npu")`
- [ ] 分布式通信 `nccl` → `hccl`
- [ ] DataLoader `num_workers` 设为 0（NPU 安全配置）
- [ ] 检查所有 CUDA-only 算子，提供 NPU fallback
- [ ] 验证 `device` 参数传递链路无遗漏

#### 3.2.2 TF→PyTorch 迁移关键规则

| 转换项 | TF 格式 | PyTorch 格式 | 转换操作 |
|--------|---------|-------------|---------|
| Dense kernel | `(in, out)` | `(out, in)` | 转置 `.T` |
| Conv1D kernel | `(K, Cin, Cout)` | `(Cout, Cin, K)` | `np.transpose(w, (2,1,0))` |
| Conv1D 输入 | `(batch, length, ch)` | `(batch, ch, length)` | 前后 transpose |
| BatchNorm eps | 默认 `1e-3` | 默认 `1e-5` | **必须显式设 eps=1e-3** |
| CuDNNLSTM bias | `(8*H,)` | `bias_ih(4*H)` + `bias_hh(4*H)` | 前半+后半拆分 |
| CuDNNLSTM kernel | `(input, 4*H)` | `(4*H, input)` | 转置 `.T` |

### 3.3 验收规范

#### 3.3.1 迁移完成标准

满足以下全部条件方可判定迁移成功：

1. **环境检查通过**：CANN/torch/torch_npu 版本匹配
2. **推理可运行**：模型在 NPU 上无报错完成前向推理
3. **输出合理**：输出数值在合理范围内，无 NaN/Inf
4. **可重复性**：同一输入多次推理结果稳定（允许微小浮点波动）

#### 3.3.2 精度对齐标准

| 指标 | 通过标准 |
|------|---------|
| Logits 余弦相似度 | > 0.99 |
| PPL 平均相对差异 | < 15% |
| 单层输出相对误差 | < 1e-3 |
| 任务指标（F1/Acc 等） | 与基线差异 < 5% |

#### 3.3.3 性能验收标准

| 场景 | 基准 |
|------|------|
| 推理优化 | 优化后吞吐 ≥ 优化前 1.2x |
| vLLM 部署 | TPOT 延迟 ≤ 目标值 |
| 训练收敛 | Loss 曲线与 GPU 对齐 |

### 3.4 命名与文件规范

#### 3.4.1 Conda 环境命名

```
<模型名小写>-npu
```

示例：`boltz2-npu`、`deepfri-npu`、`qwen35-npu`

#### 3.4.2 工作目录结构

```
/home/workspace/
  └── <model-name>/
      ├── src/                    # 源码（含迁移修改）
      ├── model_files/            # 优化后的模型文件（如有）
      ├── output/                 # 推理/训练输出
      ├── scripts/                # 辅助脚本
      └── logs/                   # 运行日志
```

#### 3.4.3 验证报告命名

```
<模型名>_验证报告_<日期>.md
<模型名>_精度对齐_<日期>.md
<模型名>_性能基准_<日期>.json
```

### 3.5 安全与注意事项

#### 3.5.1 红线规则（不可违反）

1. **禁止在未验证 CANN 版本的情况下安装 torch_npu** — 版本不匹配会导致运行时崩溃
2. **禁止忽略 CUDA-only 算子** — 必须为每个 CUDA 算子提供 NPU fallback 或明确标注 BLOCKED
3. **禁止跳过精度验证直接上线** — 必须完成至少端到端精度对比
4. **BatchNorm eps 必须显式指定** — TF 默认 1e-3，PyTorch 默认 1e-5，不匹配会导致输出全零
5. **DataLoader num_workers 必须设 0** — NPU 上多进程 DataLoader 可能导致段错误

#### 3.5.2 常见陷阱

| 陷阱 | 现象 | 解决方案 |
|------|------|---------|
| CANN/torch_npu 版本不匹配 | `import torch_npu` 报错 | 检查 CANN 版本，安装匹配的 torch_npu |
| BatchNorm eps 不匹配 | CNN 输出全为 0 | 显式设 `eps=1e-3` |
| CuDNNLSTM 无法加载 | TF 2.x 报错 | 用 h5py 直接读 HDF5 权重 |
| device 属性缺失 | `major` 属性报错 | try/except 包裹，NPU 走 fallback |
| DataLoader 段错误 | 推理时崩溃 | `--num_workers 0` |
| torch_scatter 编译失败 | pip install 报错 | 源码编译 + 正确 CANN 环境变量 |

### 3.6 技能组合使用规范

#### 3.6.1 推荐组合

| 场景 | 推荐技能组合 | 执行顺序 |
|------|-------------|---------|
| 新模型全流程 | ai4s-basic → ai4s-precision-alignment → ai4s-perf-tuning | 迁移 → 对齐 → 调优 |
| TF 模型全流程 | tf-to-pytorch → ai4s-basic → ai4s-precision-alignment | 改写 → 迁移 → 对齐 |
| vLLM 新模型 | adapt-agent → verify-agent-plus → optimizer-agent-plus | 适配 → 验证 → 优化 |
| 量化部署 | quantify-agent → verify-agent-plus | 量化 → 验证 |
| 已有模型调优 | ai4s-profiling → ai4s-perf-tuning / ascend-optimization | 采集 → 调优 |

#### 3.6.2 禁止组合

| 禁止场景 | 原因 |
|---------|------|
| ascend-tf-community + tf-to-pytorch 同时使用 | 二者互斥，需先决定保留 TF 还是转 PyTorch |
| verify-agent + verify-agent-plus 同时使用 | verify-agent-plus 是 verify-agent 的超集，选其一即可 |
| optimizer-agent + optimizer-agent-plus 同时使用 | plus 版是增强版，选其一即可 |
| ai4s-basic + 模型专属 skill 同时使用 | 有模型专属 skill 时优先使用专属版 |

### 3.7 阶段检查点

每个工作流的关键阶段必须设置检查点，通过后方可继续：

```
阶段1: 环境就绪 ✓
  └─ 检查点: npu-smi info 正常 + import torch_npu 成功

阶段2: 代码迁移 ✓
  └─ 检查点: 无 CUDA 硬编码残留 + transfer_to_npu 已注入

阶段3: 推理跑通 ✓
  └─ 检查点: 单卡推理无报错 + 输出无 NaN/Inf

阶段4: 精度对齐 ✓（可选）
  └─ 检查点: 余弦相似度 > 0.99 + 任务指标差异 < 5%

阶段5: 性能达标 ✓（可选）
  └─ 检查点: 吞吐/延迟满足目标

阶段6: 沉淀归档 ✓
  └─ 检查点: 模型专属 skill 已生成 + 验证报告已输出
```

---

## 四、快速参考卡

### 用户输入 → 技能映射

| 用户说... | 触发技能 |
|-----------|---------|
| "把 XX 模型迁移到昇腾" | ai4s-main → 按模型分流 |
| "昇腾迁移" / "NPU 适配" | ai4s-basic |
| "审查代码" / "NPU 适配审查" | adapt-agent |
| "vLLM 适配新模型" | adapt-agent |
| "验证模型部署" | verify-agent |
| "一键验证" / "验证报告" | verify-agent-plus |
| "模型量化" / "msmodelslim" | quantify-agent |
| "精度对齐" / "loss 对比" | ai4s-precision-alignment |
| "profiling" / "性能采集" | ai4s-profiling |
| "性能调优" / "CPU 绑核" | ai4s-perf-tuning |
| "torch_npu 优化" / "融合算子" | ascend-optimization |
| "优化 vLLM" / "调优 Ascend" | optimizer-agent / optimizer-agent-plus |
| "TF 转 PyTorch" | tf-to-pytorch |
| "TF 昇腾" / "npu_device" | ascend-tf-community |
| "亲和算子" / "算子替换" | ascend-affinity-operator |
| "从历史里找" / "整理成 skill" | ascend-history-to-skill |
| "发布到 GitCode" | gitcode-publish |
| "Boltz2 迁移" | boltz2 |
| "DeepFRI 迁移" | deepfri / deepfri-tf-npu |
| "ProteinBERT 迁移" | proteinbert |

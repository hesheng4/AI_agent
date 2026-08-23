# 路由分析

## 后端路由全景 (30 模块)

| 模块 | 前缀 | 核心端点 | 前端API层 | 前端页面 |
|------|-------|---------|----------|---------|
| auth | `/auth` | login/register/me/patch/password/forgot-reset/api-config | ✅ | ✅ Login/Profile |
| billing | `/billing` | usage | ✅ | ✅ Profile内 |
| literature | `/literature` | search/read/summarize/citations/references/network/co-citation/trend/graph/analysis | ⚠️ 仅search+read | ✅ Literature |
| library | `/library` | papers/categories/tags/stats/citations/network CRUD | ✅ | ✅ Library/Network |
| data | `/data` | analyze/visualize/upload | ⚠️ 仅analyze | ✅ DataAnalysis |
| writing | `/writing` | outline/generate/polish/check/word-count/structure/terminology/evidence/detect-type/latex-export | ⚠️ 仅outline+polish+check | ✅ Writing |
| experiment | `/experiment` | design/optimize/predict/power-analysis/statistical-test | ⚠️ 仅design+powerAnalysis | ✅ Experiment |
| export | `/export` | csv/json/bibtex/ris/markdown | ❌ | ❌ |
| ascend | `/ascend` | info/vllm-health/warmup/mode | ✅ | ✅ AscendOverview |
| alignment | `/alignment` | status/run/report/thresholds/constraints | ✅ | ✅ Alignment |
| profiling | `/profiling` | status/levels/generate/run/task-status/stop/results/checklist/env-check | ✅ | ✅ Profiling |
| perf-tuning | `/perf-tuning` | status/configs/apply/launch/detect-numa/tcmalloc/verify/analyze/diagnose/suggest | ✅ | ✅ PerfTuning |
| toolchain | `/toolchain` | status/hardware/env-setup/verify/vllm-launch/vllm-diagnose/quantize/aisbench | ✅ | ✅ Toolchain |
| validator | `/validator` | status/env-check/deploy/accuracy/benchmark×3/run/models | ✅ | ✅ Validator |
| debugging | `/debugging` | status/sessions/quick-diagnose/report/red-flags | ✅ | ✅ Debugging |
| history-to-skill | `/history-to-skill` | status/variants/roots/search/generate/run/validate | ✅ | ✅ HistoryToSkill |
| adaptation | `/adaptation` | sessions CRUD + step2~10 | ✅ | ✅ Adaptation |
| **reviewer** | `/reviewer` | assess/quick-check | ❌ | ❌ |
| **response** | `/response` | draft/audit/revise | ❌ | ❌ |
| **citation** | `/citation` | add/verify/format-references | ❌ | ❌ |
| **reader** | `/reader` | read-full | ❌ | ❌ |
| **figure** | `/figure` | create-contract/apply-style/qa-check | ❌ | ❌ |
| **paper2ppt** | `/paper2ppt` | generate-ppt | ❌ | ❌ |
| **paper-to-patent** | `/paper-to-patent` | draft-patent | ❌ | ❌ |
| **stats** | `/stats` | endpoint | ❌ | ❌ |
| **cover** | `/cover` | endpoint | ❌ | ❌ |
| **methods** | `/methods` | endpoint | ❌ | ❌ |
| **submission-package** | `/submission-package` | endpoint | ❌ | ❌ |
| **polishing** | `/polishing` | endpoint | ❌ | ❌ |
| **coordinator** | `/coordinator` | capability-map/workflow-templates/route | ❌ | ❌ |

## 路由组合 — 6 条核心工作流

### 流程 1：论文写作全链路
```
literature/search → library/add → reader/read-full
  → writing/outline → writing/generate → writing/polish
  → citation/add → citation/verify → figure/create
  → export/latex
```

### 流程 2：投稿准备
```
writing/outline → cover → methods → reviewer/assess
  → response/draft → response/audit → submission-package
```

### 流程 3：论文转化
```
reader/read-full → paper2ppt/generate    (论文→PPT)
reader/read-full → paper-to-patent/draft  (论文→专利)
```

### 流程 4：文献研究
```
literature/search → literature/read → literature/summarize
  → library/add → library/citations/network → export/bibtex
```

### 流程 5：智能路由
```
coordinator/route → 自动分发到对应 agent
coordinator/capability-map → 展示系统能力
coordinator/workflow-templates → 展示可用流程模板
```

### 流程 6：昇腾 NPU 全流程
```
adaptation → alignment → profiling → perf-tuning → toolchain → validator
```

## 调用模式

| 模式 | 说明 | 示例 |
|------|------|------|
| A 串行流水线 | 前步输出→后步输入 | outline → generate |
| B 扇出并行 | 一输入多输出 | 文献搜到后同时收藏+精读+引用分析 |
| C 智能路由 | 用户意图→自动分发 | coordinator/route |
| D 有状态多步 | session_id 串联 | adaptation 10步流程 |

## 优先建议

| 优先级 | 模块 | 理由 |
|--------|------|------|
| P0 | coordinator | 智能路由=所有功能的入口 |
| P0 | reader | 精读是写作/转PPT/转专利的上游 |
| P1 | reviewer + response | 审稿+回复是投稿核心场景 |
| P1 | citation + figure | 引用+图表是论文质量关键 |
| P1 | export | 导出是所有工作的终点 |
| P2 | paper2ppt + paper-to-patent | 转化场景，非主线 |
| P2 | cover + methods + submission-package | 投稿辅助 |
| P2 | polishing | 与 writing/polish 重叠 |
| P3 | stats + data-availability | 辅助统计 |

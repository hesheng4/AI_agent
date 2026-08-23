# nature-skills 科研工作台功能缺失与差异分析

导出时间：2026-06-20

---

## 一、nature-skills 16 个 skill vs 工作台现状

| # | nature-skill | 阶段 | 工作台 agent | API 端点 | 状态 |
|---|-------------|------|-------------|---------|------|
| 1 | nature-figure | 作图 | `figure/` ✅ | `figure` ✅ | 有 |
| 2 | nature-polishing | 润色 | `polishing/` ✅ | `writing` ✅ | 有 |
| 3 | nature-writing | 写作 | `writing/` ✅ | `writing` ✅ | 有 |
| 4 | nature-reviewer | 自审 | `reviewer/` ✅ | `reviewer` ✅ | 有 |
| 5 | nature-citation | 文献检索 | `citation/` ✅ | `citation` ✅ | 有 |
| 6 | nature-data | 数据 | `data/` ✅ | `data_availability` ✅ | 有 |
| 7 | nature-reader | 阅读理解 | `reader/` ✅ | `reader` ✅ | 有 |
| 8 | nature-response | 回复审稿 | `response/` ✅ | `response_api` ✅ | 有 |
| 9 | nature-paper2ppt | 传播 | `paper2ppt/` ✅ | `paper2ppt` ✅ | 有 |
| 10 | nature-paper-to-patent | 传播 | `paper_to_patent/` ✅ | `paper_to_patent` ✅ | 有 |
| 11 | nature-academic-search | 文献检索 | `literature/` ✅ | `literature` ✅ | 有 |
| 12 | **nature-stats** | 统计 | ❌ 无 | ❌ 无 | **缺失** |
| 13 | **nature-cover** | 投稿 | ❌ 无 | ❌ 无 | **缺失** |
| 14 | **nature-methods** | 方法 | ❌ 无 | ❌ 无 | **缺失** |
| 15 | **nature-submission-package** | 投稿 | ❌ 无 | ❌ 无 | **缺失** |
| 16 | **nature-skills (路由)** | 入口 | ⚠️ `coordinator/` 极简 | ❌ 无 | **差异大** |

---

## 二、缺失清单（4 个 skill 缺失）

| 缺失 skill | 阶段 | 核心功能 | 优先级 |
|-----------|------|---------|--------|
| **nature-stats** | 统计 | 精确p值、效应量+CI、样本量定义、误差棒含义、检验选择、多重比较校正、不编造 | 高 — Results/Methods 必需 |
| **nature-cover** | 投稿 | 投稿信起草+审计、desk-reject 防御、反套路开头、期刊针对性 fit | 高 — 投稿第一步 |
| **nature-methods** | 方法 | Methods 可复现性+合规审计、材料标识符、伦理声明、禁用短语替换 | 高 — 与 writing/stats/data 互补 |
| **nature-submission-package** | 投稿 | 期刊匹配、投稿清单✓/✗/⚠、跨件一致性7条规则(C1-C7)、路由缺失项 | 中 — 依赖 cover/stats/methods 先就位 |

---

## 三、差异清单（1 个有但差距大）

| 差异项 | nature-skills 期望 | 工作台现状 | 影响 |
|-------|-------------------|-----------|------|
| **入口路由** | `nature-skills` router：意图识别→16 skill路由、4条工作流模板(从头写/投稿/修稿/转化)、能力地图 | `coordinator/planner`：关键词匹配仅覆盖 literature/data/writing/experiment 4个，无工作流模板，无能力地图 | 用户无法自然语言触发 stats/cover/methods/submission-package；无端到端流程引导 |

---

## 四、工作台额外能力（nature-skills 无对应）

| 额外 agent | 说明 |
|-----------|------|
| `experiment/` | 实验设计 — nature-skills 无对应 skill |
| `data_v2/`, `citation_v2/`, `data_agent/` | v2 版本迭代 |
| Ascend/NPU 相关 | `ascend`, `adaptation`, `alignment`, `profiling`, `perf_tuning`, `toolchain`, `history_to_skill` — 非科研论文流程 |

---

## 五、补全方案（依赖序）

1. **nature-stats agent** — 从 `nature-skills/skills/nature-stats/` 移植 SKILL.md + manifest.yaml + references/ + static/ + evals/，创建 `app/agents/stats/` + `app/api/v1/stats.py`
2. **nature-cover agent** — 同上，从 `nature-cover` 移植
3. **nature-methods agent** — 同上，从 `nature-methods` 移植
4. **nature-submission-package agent** — 同上，从 `nature-submission-package` 移植（依赖 1-3 先完成）
5. **升级 coordinator/planner** — 扩展 `identify_agents` 覆盖全部 16 skill 关键词；增加 4 条工作流模板（从头写论文/投稿/修稿/转化）；增加能力地图输出

### 风险标注

- **破坏性**：升级 planner 会改变现有路由行为 — 需确保原有 literature/data/writing/experiment 路由不受影响
- **依赖序**：submission-package 依赖 stats/cover/methods 的路由存在，否则清单路由断裂
- **非不可逆**：均为新增 agent + 扩展路由，不删不改现有 agent

---

## 六、不做项

- nature-ideation — 暂缓，诚信风险高（易滑向"AI帮你想课题"）、评测难、价值主观
- Ascend/NPU 相关 — 已超出论文流程范围，不在本次分析域

---

## 七、流程覆盖全景（补全后）

```
文献检索 ──→ 阅读理解 ──→ 写作 ──→ 统计 ──→ 方法 ──→ 作图 ──→ 数据 ──→ 自审 ──→ 投稿 ──→ 传播
    │                        │         │        │        │                  │         │
    ├─ academic-search       ├─ writing ├─ stats ├─ methods ├─ figure      ├─ cover  ├─ paper2ppt
    └─ citation              ├─ polishing                     ├─ data     ├─ sub.pkg ├─ patent
                             └─ reader                        └─ data     └─ reviewer
                                                                        └─ response

入口：nature-skills — 意图识别 → 单 skill 路由 / 流程引导 / 能力地图
```

工作流模板：
- A. 从头写论文（12 步）
- B. 投稿（5 步）
- C. 修稿（5 步）
- D. 转化（2 步）

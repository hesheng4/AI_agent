# 19 Round 19 — Q 系列历史代码质量（机械安全项 + 延期项文档化）

**执行日**: 2026-06-28
**触发**: 用户 "q" → 推进 Q1-Q6 历史代码质量
**方法**: 从 ground truth 重建 Q 清单（不引用前轮文档），区分"机械安全可修"与"需专题/协调"，只执行前者

---

## 1. 执行结果

| 项 | 数值 |
|----|------|
| 已修（机械安全） | Q residual 13 处 I001/F401 + Q5 2 处 probe import |
| 延期（附 rationale） | Q1 442 处 E501 + Q6 6 处 double-prefix |
| 自审翻案 | Q3 已闭环（R4 cover 已清 `letter_type`）、Q4 moot（R18 删 citation_v2） |
| 全回归 | 209/209 passed（1.61s） |
| ruff I001/F401（全 `app/`） | All checks passed |
| 临时脚本 | `_q_inventory.py` / `_smoke19.py` 已清理 |

---

## 2. Q 清单 ground truth（不从记忆重建）

| ID | R12 文档描述 | R19 实测 | 处理 |
|----|-------------|---------|------|
| Q1 | "~40 处 E501 in prompts.py" | **442 处 / 66 文件**（远超估计） | 延期（§4） |
| Q2 | "planner SKILL_KEYWORD_MAP 数据行 E501" | Q1 子集（planner.py 37 处） | 与 Q1 同延期 |
| Q3 | "cover `letter_type` 死输入" | **grep 0 匹配** — R4 已清 | ✅ 已闭环（R4） |
| Q4 | "citation_v2 unused static methods" | R18 已删 citation_v2 | ✅ moot（R18） |
| Q5 | "probe import 改 find_spec" | 2 处：paper2ppt `Pt`、patent `PIL` | ✅ 本轮修 |
| Q6 | "6 处 double-prefix 路由" | 确认 6 处 sub-router 双 prefix | 延期（§5） |
| Q residual | 未列入 R12 | 13 处 I001/F401 在 `app/` 非 agents 区 | ✅ 本轮修 |

---

## 3. 已修项

### 3.1 Q residual — ruff I001/F401（13 处）

`ruff --fix app/ --select I001,F401 --exclude app/agents`（R14 只清了 `app/agents/`，本轮覆盖 `app/api/`、`app/utils/` 等）：

| 文件 | 类型 | 处理 |
|------|------|------|
| `app/api/v1/debugging.py` | I001 | auto-fix |
| `app/api/v1/history_to_skill.py` | I001 | auto-fix |
| `app/api/v1/methods.py` | I001 + F401 `HTTPException` | auto-fix |
| `app/api/v1/perf_tuning.py` | I001 | auto-fix |
| `app/api/v1/polishing.py` | I001 | auto-fix |
| `app/api/v1/profiling.py` | I001 | auto-fix |
| `app/api/v1/stats.py` | I001 | auto-fix |
| `app/api/v1/submission_package.py` | I001 | auto-fix |
| `app/api/v1/toolchain.py` | I001 | auto-fix |
| `app/api/v1/validator.py` | I001 | auto-fix |
| `app/utils/latex_engine.py` | F401 `tempfile` + `ToolException` | auto-fix |

**13 fixed, 0 remaining**（ruff 输出）。

### 3.2 Q5 — probe import（2 处，非 uniform 模式）

两处 shape 不同，分别处理而非盲目套 find_spec：

**paper2ppt/agent.py:170** — `from pptx.util import Inches, Pt` 中 `Pt` 未用但 `Inches` 已用（line 173-174）。
- ❌ 套 find_spec 会破坏 `Inches` 使用
- ✅ 仅删 `Pt`，保留 `Inches`

**paper_to_patent/scripts/render_flowchart_svg.py:365** — `import PIL` 纯探测（PIL 从未使用，仅存在性检查）。
- ✅ 改 `importlib.util.find_spec("PIL") is None` — 符合 ruff 建议

**验证**: smoke test import 两个模块均 OK。

---

## 4. Q1（E501）延期 rationale

**实测**: 442 处 / 66 文件，远超 R12 "约 40 处" 估计。

**分布前 5** (占 51%):
| 文件 | 处数 |
|------|------|
| `agents/citation/scripts/nature_citation.py` | 99 |
| `agents/literature/scripts/academic_search.py` | 38 |
| `agents/coordinator/planner.py` | 37 |
| `agents/paper_to_patent/scripts/validate_patent_draft.py` | 30 |
| `agents/writing/prompts.py` | 22 |

**为何不在本轮修**:
- 主体是 `scripts/` 子目录与 `prompts.py` 的**长字符串字面量**（prompt 文本、regex、help 文本）
- 机械断行会**改变运行时字符串内容**（多换行/缩进进入字符串），破坏 prompt 语义
- 需逐文件人工审查：哪些是可断的代码行、哪些是不可断的字面量
- 442 处 / 66 文件的工作量与风险不适合压缩进单轮

**建议**: 留专题轮次，按文件分批，每批 ≤ 50 处，配合针对性测试。

---

## 5. Q6（double-prefix 路由）延期 rationale

**根因确认**: 6 个 sub-router 各自在文件内 `APIRouter(prefix="/X")`，同时 `api/v1/__init__.py:include_router(..., prefix="/X")` 又加同 prefix → 最终 `/api/v1/X/X/`。

**6 受影响 router**: cover, coordinator, stats, methods, polishing, submission_package

**为何不在本轮修**:
- 修复需删除 sub-router 内的 `prefix=` 声明（或删 `__init__.py` 的）
- **URL 会变**：`/api/v1/cover/cover/` → `/api/v1/cover/`
- 这是**对外契约变更**，前端/外部客户端正在调旧 URL
- 无 frontend 协调下 unilateral 修改 = 破坏 deployed 服务

**建议**: 与 E3 frontend 审查合并专题，前后端同步改 URL + 调用方。

---

## 6. 验证

| 检查 | 结果 |
|------|------|
| ruff I001/F401（全 `app/`） | All checks passed |
| Q5 import smoke（paper2ppt + render_flowchart_svg） | OK |
| 全回归 | 209 passed（1.61s） |
| 临时脚本 | `_q_inventory.py` / `_smoke19.py` 已删 |

---

## 7. 累计最终状态（R12-R19）

| 轮 | 闭环 | 变化 |
|----|------|------|
| R12-R18 | 见 R18 doc | 61 修复，209 测试 |
| R19 | Q residual 13 + Q5 2 + Q3/Q4 状态确认 | +15 修复，0 测试 |

**累计**: 76 处修复；209 测试；209/209 passed。

---

## 8. 遗留清单（R19 后）

| ID | 状态 |
|----|------|
| T1/T2/T3/T4 | ✅ 闭环 |
| E1/E2 | ✅ 闭环 |
| S1/S3 | ✅ 闭环 |
| S5/S6 | ✅ 预期/subsumed |
| Q3/Q4 | ✅ 闭环（R4）/ moot（R18） |
| Q5 | ✅ 本轮闭环 |
| Q residual (I001/F401) | ✅ 本轮闭环 |
| **Q1 E501（442 处）** | ⏳ 延期 — 需专题分批，字面量断行风险 |
| **Q6 double-prefix（6 处）** | ⏳ 延期 — 需 frontend 协调，URL �契约变更 |
| S2 文件上传限制 | ⏳ 独立专题 |
| S4 cache key str | ⏳ 低优先 |
| E3 frontend | ⏳ 独立专题（与 Q6 合并） |

---

## 9. 本轮价值

1. **机械安全项收敛**: I001/F401 全 `app/` 清零（R14 只清了 agents/，本轮补齐）；Q5 probe import 用差异化方式处理（非盲目套模式）。
2. **Q3/Q4 状态纠正**: 从 ground truth 确认 Q3 已在 R4 闭环、Q4 因 R18 删除而 moot，避免后续轮次重复处理。
3. **Q1/Q6 延期 rationale 明确**: 不在本轮盲推高风险变更；Q1 字面量断行风险、Q6 URL 契约变更，均需专题或跨端协调。
4. **R12 估计纠正**: R12 称 Q1 "~40 处"，实测 442 处 — 前轮估计偏差 10×，印证"从 ground truth 重建"的必要性。

**剩余项均为专题/低优先**。本轮 Q 系列机械安全部分已收敛。

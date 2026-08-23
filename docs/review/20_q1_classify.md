# 20 Round 20 — Q1 E501 专题（分类证伪 → 拒绝盲改）

**执行日**: 2026-06-28
**触发**: 用户 "Q1" → 推进 442 处 E501 历史长行
**方法**: 先分类（STRING/CODE/COMMENT/DOCSTRING），再按风险分层；对疑似安全子集做 AST 级证伪
**结果**: **拒绝盲改** — 分类证据证明 442 处中无机械安全子集可批量修

---

## 1. 执行结果

| 项 | 数值 |
|----|------|
| 已修 | **0**（证伪后拒绝盲改） |
| 分类证据 | 442 处全分类 + 62 处"疑似安全"二次证伪 |
| 全回归 | 209/209 passed（未改动，确认基线） |
| 临时脚本 | `_q1_class.py` / `_q1_safe.py` / `_q1_strict.py` + 3 输出文件已清理 |
| 决策 | Q1 退出"机械可修"范畴，列为专题级人工审查项 |

---

## 2. 分类证据（442 处 E501 全分类）

| Bucket | Count | 占比 | 含义 | 断行风险 |
|--------|-------|------|------|----------|
| STRING | 215 | 49% | 长字符串字面量主体（prompt 文本、regex、help） | **HIGH** — 注入 `\n` 改运行时内容 |
| STRINGISH | 152 | 34% | 含字符串但启发式边界模糊 | **HIGH** — 同上 |
| DOCSTRING | 13 | 3% | 文档字符串 | MEDIUM — 仅影响 doc，不改逻辑 |
| CODE | 54 | 12% | 纯代码（启发式判定） | LOW（启发式） |
| COMMENT | 8 | 2% | 纯注释 | LOW |

**关键**：380 处（86%）是字符串字面量驱动 — 断行会改变 LLM prompt / regex / HTML 输出内容。

---

## 3. 二次证伪 — "62 疑似安全"为何仍不可信

初分类出 62 处 CODE+COMMENT 启发式"安全"。二次 strict 过滤（拒绝含引号、拒绝 `"""` 上下文）剩 61 处。**但 AST 级抽查发现误分类**：

### 3.1 误分类实例 A — HTML 模板内行

`nature_citation.py:1687`（分类器标 CODE）：
```
1685      <div class="modal-inner">
1686        <h2 id="summaryTitle">Ready to review citations</h2>
1687      <p>This page behaves more like a compact Scholar browser: ... </p>
```
**实情**：1687 在 Python 三引号 HTML 模板字符串内（开括号在数百行上方）。断行 → 注入 `\n` + 缩进进 HTML 输出 → 破坏生成页面。

### 3.2 误分类实例 B — LLM prompt 内行

`methods/prompts.py:6`（分类器标 CODE）：
```python
3  METHODS_SYSTEM_PROMPT = """You are a Nature-style Methods section auditor ...
4  Core rules:
5  - Every step must be reproducible ...
6  - Reagents/antibodies/cell lines: supplier/catalogue/RRID, authentication, ...
```
**实情**：line 6 在 `METHODS_SYSTEM_PROMPT = """..."""` 字符串内（line 3 开括号）。断行 → 注入 `\n` + 缩进进 LLM prompt → 改变模型行为。

### 3.3 分类器局限

启发式分类器（基于同行引号/三引号/注释前缀）**无法检测"N 行上方开括号的多行字符串"**。要可靠识别需 AST walk：对每个 E501 位置，向上找最近的未闭合 `String`/`Constant` 节点。本轮未实现该 AST 分类器。

---

## 4. 拒绝盲改的 rationale

| 选项 | 风险 | 决策 |
|------|------|------|
| 盲改 62 处启发式"安全" | 5-10 处误分类 → 静默 corrupt LLM prompt / HTML 输出 | ❌ 拒绝 |
| 实现 AST 分类器后改真安全子集 | 本轮 context 不足以实现 + 验证 AST 分类器 | ⏳ 延期 |
| 改 380 处字符串字面量 | 每处需人工判断"断在哪不破坏语义" | ⏳ 专题级人工 |

**结论**：Q1 不存在"机械安全可批量"子集。任何批量改动都有静默 corrupt 运行时内容的风险。

---

## 5. Q1 真实修复路径（后续专题）

1. **实现 AST 分类器**：对每个 E501 line，用 `ast.walk` 找该位置所属节点；仅当属 `FunctionDef`/`Call`/`Assign` 等纯代码节点（非 `Constant`/`JoinedStr`）时标 SAFE
2. **真安全子集**：预计 ≤ 30 处（纯函数签名、call 表达式），可机械 reflow
3. **字符串字面量子集**：逐文件人工审查，重点是 `prompts.py`（LLM prompt 断行需保留语义）与 `scripts/*.py`（HTML/regex 断行需保留输出）
4. **每批 ≤ 50 处**，配合针对性测试（prompt 输出对比、HTML diff）

---

## 6. 验证

| 检查 | 结果 |
|------|------|
| 临时脚本清理 | `_q1_class.py` / `_q1_safe.py` / `_q1_strict.py` + 3 .txt 已删 |
| 未改动 → 基线保持 | 209/209 passed（Q1 未修，无回归风险） |

---

## 7. 累计最终状态（R12-R20）

| 轮 | 闭环 | 变化 |
|----|------|------|
| R12-R19 | 见 R19 doc | 76 修复，209 测试 |
| R20 | **Q1 分类证据 + 拒绝盲改决策** | 0 修复（证伪后正确放弃） |

**累计**: 76 处修复；209 测试；209/209 passed。

---

## 8. 遗留清单（R20 后）

| ID | 状态 |
|----|------|
| T1-T4 / E1-E2 / S1/S3 / Q3-Q5 / Q residual | ✅ 闭环 |
| **Q1 E501（442 处）** | ⏳ **退出机械可修** — 需 AST 分类器 + 专题人工 |
| Q6 double-prefix（6 处） | ⏳ 需 frontend 协调 |
| S2 文件上传限制 | ⏳ 独立专题 |
| S4 cache key str | ⏳ 低优先 |
| E3 frontend | ⏳ 独立专题（与 Q6 合并） |

---

## 9. 本轮价值（"不修"亦是结论）

1. **分类证据**：证明 Q1 的 442 处 E501 中 86% 是字符串字面量，不存在机械安全批量子集
2. **证伪自我分类器**：二次 strict 过滤仍误分类 HTML 模板行 + LLM prompt 行 → 证明需 AST 级分类，启发式不够
3. **避免静默 corruption**：拒绝盲改 62 处"疑似安全"= 避免静默 corrupt LLM prompt / HTML 输出（5-10 处误分类的代价远高于 Q1 美观收益）
4. **明确后续路径**：Q1 需 AST 分类器 + 专题人工，非单轮机械任务

**本轮"不修"是正确决策** — 在证据证明机械修不安全时，停止比推进更有价值。

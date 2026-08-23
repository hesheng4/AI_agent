# 14 Round 14 — T3 ruff I001/F401 auto-fix

**执行日**: 2026-06-27
**触发**: Round 13 后用户 "a" 选择 T3
**工具**: ruff 0.15.18

---

## 1. 执行结果

| 项 | 数值 |
|----|------|
| 检查范围 | `app/agents/` |
| 初始错误 | 28（20 I001 + 8 F401） |
| `--fix` 修复 | 26 |
| 残留 | 2（intentional，见 §3） |
| 受影响文件 | 18 |
| 回归测试 | 160/160 passed（1.02s） |
| 临时脚本 | `_smoke14.py` 已清理 |

---

## 2. 修复明细

### I001 unsorted-imports（20 处，全修复）

| 文件类别 | 文件 |
|----------|------|
| agent `__init__.py` | methods, polishing, stats, submission, submission_package（5） |
| agent `agent.py` | methods, stats, submission_package（3） |
| scripts | citation/nature_citation, literature/academic_search, literature/format-converter ×2, paper_to_patent/{audit_claims,init_patent_project,math_to_omml,render_flowchart_svg,render_patent_docx,validate_patent_draft}（10） |
| 其他 | manifest_router（1），literature/format-converter 内嵌 import（1） |

### F401 unused-import（8 处，6 修复 + 2 保留）

| 文件 | import | 处理 |
|------|--------|------|
| literature/format-converter.py | `sys` | 删除 |
| literature/format-converter.py | `converters.convert_from_arxiv`（try probe） | 删除 |
| manifest_router.py | `os` | 删除 |
| methods/agent.py | `METHODS_SYSTEM_PROMPT` | 删除 |
| stats/agent.py | `STATS_SYSTEM_PROMPT` | 删除 |
| submission/agent.py | `SUBMISSION_SYSTEM_PROMPT` | 删除 |
| paper2ppt/agent.py | `pptx.util.Pt`（try probe） | **保留**（§3） |
| paper_to_patent/scripts/render_flowchart_svg.py | `PIL`（try probe） | **保留**（§3） |

---

## 3. 保留的 2 个 F401（合理保留）

两处均为 **optional-dep 探测 import**，位于 `try/except ImportError` 内，目的不是使用符号而是检查包是否可导入：

```python
# paper2ppt/agent.py:170
try:
    from pptx import Presentation
    from pptx.util import Inches, Pt  # Pt 仅探测，未使用
    prs = Presentation()

# paper_to_patent/scripts/render_flowchart_svg.py:365
if args.png:
    try:
        import PIL  # 探测，未使用
    except ImportError as error:
        raise SystemExit(...)
```

ruff 建议改用 `importlib.util.find_spec`，但本轮不改动逻辑（T3 仅做 auto-fix）；列为 Round 15+ 候选优化项 Q5。

---

## 4. 验证

| 检查 | 结果 |
|------|------|
| smoke test（9 模块 import） | 全 OK |
| `pytest tests/unit/ -q` | 160 passed |
| ruff `--select I001,F401` 残留 | 2（intentional probes） |
| 临时脚本清理 | `_smoke14.py` 已删除 |

---

## 5. Round 12 遗留清单更新

| ID | 状态 |
|----|------|
| T1（temperature） | ✅ R13 闭环 |
| T2（singleton） | ✅ R13 闭环 |
| T3（ruff I001/F401） | ✅ 本轮闭环（2 probe 保留为 Q5） |
| T4（v2 agent 决策） | ⏳ **待用户裁定** |
| E1/E2（端到端测试） | ⏳ |
| S1-S6（安全审计遗留） | ⏳ |
| Q1-Q4（历史代码质量） | ⏳ |
| Q5（新增：probe import 改 find_spec） | ⏳ 低优先 |

**建议下一步**: 用户裁定 T4（v2 agent 去留）以解锁后续清理；或推进 E1/E2 端到端测试。

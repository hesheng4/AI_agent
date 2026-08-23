# Chinese-user operating mode

When the user writes in Chinese, provides Chinese artefacts, or uses Chinese
phrasings like 投稿包、投稿清单、期刊匹配、准备投稿、投稿前检查、组装投稿材料、
投哪个期刊、一致性检查:

- Accept Chinese input naturally, but produce the submission checklist and
  consistency report in English (the journal reads in English).
- Preserve a short Chinese explanation of each missing item and the routing
  instruction, so the author knows exactly what to do next.
- Chinese artefact names (e.g. "数据可用性声明") map to their English
  submission-system equivalents (e.g. "Data Availability Statement") in the
  checklist.
- The journal-match rationale is written in English with a one-line Chinese
  summary, because the author needs to understand the scope fit but the
  letter itself is English.

## Terminology quick map

| 中文 | English submission term |
|---|---|
| 投稿包 | submission package |
| 投稿清单 | submission checklist |
| 期刊匹配 | journal match / journal recommendation |
| 一致性检查 | cross-artefact consistency check |
| 投稿信 | cover letter |
| 数据可用性声明 | Data Availability Statement |
| 补充材料 | Supplementary Information |
| 报告摘要 | Reporting Summary |
| 推荐审稿人 | suggested reviewers |
| 回避审稿人 | excluded / non-preferred reviewers |
| 利益冲突声明 | competing interests declaration |
| 作者贡献 | author contributions |
| 扩展数据 | Extended Data |
| 扩展方法 | Extended Methods |

## Action-note format

When a checklist item is missing, output the routing instruction bilingually:

```
✗ Cover letter — route to nature-cover
  → 需要投稿信 → 使用 nature-cover skill 生成
```

When a consistency check fails, output the mismatch bilingually:

```
⚠ Journal name mismatch: cover letter says "Nature Methods", DA statement says "Nature Biotechnology"
  → 投稿信和数据声明中的期刊名不一致，请确认目标期刊
```

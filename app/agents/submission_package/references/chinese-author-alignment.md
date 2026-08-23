# Chinese-author alignment

Open this when the user writes in Chinese, provides Chinese submission notes,
or needs bilingual submission-package wording. Pairs with
`static/core/chinese-mode.md`.

## Terminology table (CN → submission-system EN)

| 中文 | English submission term |
|---|---|
| 投稿包 | submission package |
| 投稿清单 | submission checklist |
| 期刊匹配 | journal match / journal recommendation |
| 一致性检查 | cross-artefact consistency check |
| 投稿信 | cover letter |
| 致编辑的信 | letter to the editor |
| 数据可用性声明 | Data Availability Statement |
| 数据声明 | Data Availability Statement |
| 补充材料 | Supplementary Information |
| 补充方法 | Extended Methods / Supplementary Methods |
| 扩展数据 | Extended Data |
| 报告摘要 | Reporting Summary |
| 报告清单 | Reporting Summary |
| 推荐审稿人 | suggested reviewers |
| 回避审稿人 | excluded / non-preferred reviewers |
| 利益冲突声明 | competing interests declaration |
| 竞争利益声明 | competing interests declaration |
| 作者贡献 | author contributions |
| 伦理审批 | ethics approval |
| 知情同意 | informed consent |
| 注册号 | registration number (clinical trial) |
| 代码可用性 | code availability |
| 基准数据 | benchmark data |
| 旗舰刊 | flagship journal |
| 子刊 | sub-journal |
| 开放获取 | open access (OA) |

## Chinese-specific failure modes

Chinese authors commonly make these submission-package errors:

1. **Cover letter 期刊名与实际投稿期刊不一致** — 先投Nature被拒，改投NC但忘记更新投稿信。一致性检查 C1 专门抓这个。

2. **DA 声明用中文写** — 投稿系统要求英文。路由到 nature-data 时提醒用英文。

3. **补充材料编号与正文不一致** — 中文稿件常见"补充图S1"但正文引用"Supplementary Fig. 1"。编号风格混用。一致性检查 C2/C7 抓编号不匹配。

4. **作者中英文姓名不一致** — 稿件署名 "Zhang, Wei" 但投稿信签 "W. Zhang"。归一化规则：比较姓+名首字母。

5. **漏填 Reporting Summary** — 许多中文作者不知道 Nature 要求 Reporting Summary，尤其动物实验的 ARRIVE 项。checklist 的 journal-specific items 段会标出。

## Bilingual action-note template

When a checklist item is missing:

```
✗ [English item name] — MISSING
  → [中文说明] → 使用 [skill-name] 生成
  Input needed: [what the skill needs, in English]
```

When a consistency check fails:

```
⚠ [Check name]: [detail in English]
  → [中文说明及解决建议]
```

When the journal match suggests candidates:

```
## 1. Journal match / 期刊匹配

Based on your abstract and paper type:
根据您的摘要和论文类型：

1. **Nature Methods** — scope fit: [reason in English]
   → 与本研究的分析方法创新高度契合
2. **Nature Communications** — scope fit: [reason in English]
   → 适合扎实但非范式转换的工作
```

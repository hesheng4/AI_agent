# Chinese-author alignment

Open this when the user writes in Chinese, provides Chinese statistical notes, or needs
bilingual statistical wording. Pairs with `static/core/chinese-mode.md`.

## Terminology table (CN -> Nature-style EN)

| 中文 | English reporting term |
|---|---|
| 样本量 | sample size (n) |
| 生物学重复 | biological replicates |
| 技术重复 | technical replicates |
| 独立实验 | independent experiments |
| 配对 / 配对检验 | paired / paired test |
| 非配对 / 独立样本 | unpaired / independent-samples |
| 单尾 / 单侧 | one-sided |
| 双尾 / 双侧 | two-sided |
| 显著性 / 显著差异 | statistical significance / significant difference |
| 效应量 | effect size |
| 置信区间 | confidence interval (CI) |
| 标准差 | standard deviation (s.d.) |
| 标准误 | standard error of the mean (s.e.m.) |
| 误差棒 | error bars |
| 中位数 / 四分位距 | median / interquartile range (IQR) |
| 方差分析 | analysis of variance (ANOVA) |
| 事后检验 / 事后比较 | post hoc test / post hoc comparison |
| 多重比较校正 | multiple-comparison correction |
| 正态性 / 正态分布 | normality / normal distribution |
| 方差齐性 | homogeneity of variance |
| 秩和检验 | rank-sum test (Mann–Whitney U) |
| 卡方检验 | chi-square test |
| 风险比 / 风险比率 | hazard ratio / risk ratio |
| 比值比 | odds ratio |
| 相关系数 | correlation coefficient |
| 假阳性 / 错误发现率 | false positive / false discovery rate (FDR) |

## Common CN-to-EN statistical failure modes

- **`P<0.05` 习惯** — Chinese drafts often report only the threshold. Nature wants the exact
  value; ask the author for it rather than translating the threshold.
- **`均值±标准差` 不标注** — a ± value with no statement of whether it is s.d., s.e.m., or CI.
  Always force the choice into the legend.
- **`有显著差异` 当作结论** — "there is a significant difference" used as the finding, with no
  test, n, or effect size. Translate the intent, then flag the three missing pieces.
- **技术重复当 n** — counting technical replicates (repeated measurements of one sample) as
  the sample size. Confirm the biological replicate count separately.
- **`显著` = 重要** — "显著" colloquially means "notable/large", but in statistics it means
  "statistically significant". Make sure the author's claim of importance is backed by an
  effect size, not just a small p.
- **检验名缺失** — the test is often omitted in Chinese drafts ("经统计学分析"). Ask which test.

## Bilingual intake questions

When the Chinese input is missing the facts needed for a Nature-style statement, ask (in
Chinese) for:

1. 每组的样本量 n 是多少，n 的单位是什么（动物 / 患者 / 细胞 / 生物学重复 / 技术重复）？
2. 用的是什么统计检验？配对还是非配对？单尾还是双尾？
3. 误差棒代表标准差(s.d.)、标准误(s.e.m.) 还是置信区间(CI)？
4. 能否提供精确 p 值（而不只是 P<0.05）？
5. 有没有效应量或置信区间（如差值、倍数、风险比及其 95% CI）？
6. 是否做了多重比较？如果做了，用了什么校正方法？

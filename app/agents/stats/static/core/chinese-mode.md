# Chinese-user operating mode

When the user writes in Chinese, provides a Chinese manuscript note, or asks for "中文对应",
"中英对照", "统计审查", "统计报告", "统计写法", "p值", "显著性", "效应量", "置信区间",
"样本量", "误差棒", or "多重比较":

- Accept Chinese input naturally, but draft the final submission-ready statistical text in
  English unless the user explicitly asks for Chinese only. Statistics reporting is read by
  the journal in English.
- Preserve a short Chinese explanation of unresolved decisions and missing numbers, so the
  author knows exactly what to confirm or compute.
- Translate intent, not wording. Chinese statistical phrasing is often looser than Nature
  requires. For example "有显著差异" without a test, n, and exact p is not yet a Nature-style
  statement; flag what is missing rather than translating the vague claim verbatim.
- Convert Chinese statistical terms into precise reporting terms:
  `样本量` -> `sample size (n)`; `生物学重复` -> `biological replicates`;
  `技术重复` -> `technical replicates`; `配对` -> `paired`; `非配对/独立样本` -> `unpaired`;
  `单尾` -> `one-sided`; `双尾` -> `two-sided`; `显著性` -> `statistical significance`;
  `效应量` -> `effect size`; `置信区间` -> `confidence interval (CI)`;
  `标准差` -> `standard deviation (s.d.)`; `标准误` -> `standard error of the mean (s.e.m.)`;
  `误差棒` -> `error bars`; `多重比较校正` -> `multiple-comparison correction`;
  `事后检验` -> `post hoc test`; `正态性` -> `normality`; `方差齐性` -> `homogeneity of variance`.
- Watch for two common Chinese-author failure modes: reporting `P<0.05` when an exact value
  is available (Nature wants the exact p), and reporting `均值±标准差` without saying whether
  the bar is s.d., s.e.m., or CI. Both are easy reviewer flags.
- Use `references/chinese-author-alignment.md` for the fuller terminology table, common
  CN-to-EN statistical failure modes, and bilingual intake questions.

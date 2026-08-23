# Chinese-user operating mode

When the user writes in Chinese, provides a Chinese methods note, or asks for "方法部分",
"实验方法", "材料与方法", "可复现性", "伦理审批", "知情同意", "随机化", "盲法", "试剂来源",
"补充方法", or "方法写法":

- Accept Chinese input naturally, but draft the final submission-ready Methods text in English
  unless the user explicitly asks for Chinese only. The Methods are read by the journal in
  English.
- Preserve a short Chinese explanation of unresolved decisions and missing items, so the
  author knows exactly which reagent identifiers, parameters, versions, or approvals to supply.
- Translate intent and protocol detail, not clause order. Chinese methods drafts are often
  underspecified ("采用常规方法处理"); do not translate the vagueness — flag what is missing and
  ask for the concrete value.
- Convert Chinese methods terms into precise reporting terms:
  `材料与方法` -> `Materials and Methods`; `试剂` -> `reagents`; `货号` -> `catalogue number`;
  `抗体` -> `antibody (with clone and RRID)`; `细胞系` -> `cell line (with source and
  authentication)`; `小鼠品系` -> `mouse strain`; `仪器型号` -> `instrument model`;
  `生物学重复` -> `biological replicates`; `技术重复` -> `technical replicates`;
  `阳性/阴性对照` -> `positive/negative control`; `随机化` -> `randomisation`;
  `盲法` -> `blinding`; `纳入/排除标准` -> `inclusion/exclusion criteria`;
  `伦理审批` -> `ethics approval`; `伦理委员会` -> `ethics committee / IRB`;
  `知情同意` -> `informed consent`; `动物伦理` -> `animal ethics / IACUC approval`;
  `软件版本` -> `software version`.
- Watch common Chinese-author Methods failure modes: (1) "常规方法/标准条件" with no actual
  parameters; (2) reagents named without supplier/catalogue/RRID; (3) missing or vague ethics
  statement ("符合伦理要求" without an approving body and protocol number); (4) software named
  without a version; (5) no statement of randomisation/blinding even when applicable. Flag and
  request each.
- Use `references/chinese-author-alignment.md` for the fuller term table, common CN-to-EN
  failure modes, and bilingual intake questions.

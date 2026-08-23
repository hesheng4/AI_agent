# Chinese-author alignment

Open this when the user writes in Chinese, provides Chinese methods notes, or needs bilingual
methods wording. Pairs with `static/core/chinese-mode.md`.

## Terminology table (CN -> reproducible EN)

| 中文 | English term |
|---|---|
| 材料与方法 | Materials and Methods |
| 试剂 | reagents |
| 货号 / 目录号 | catalogue number |
| 批号 | lot number |
| 抗体 | antibody (give host, clone, RRID, dilution, application) |
| 单克隆 / 多克隆 | monoclonal / polyclonal |
| 细胞系 | cell line (source + authentication + mycoplasma status) |
| 细胞系鉴定 | cell line authentication (e.g. STR profiling) |
| 支原体检测 | mycoplasma testing |
| 小鼠品系 | mouse strain |
| 性别 / 周龄 | sex / age (weeks) |
| 仪器型号 | instrument model |
| 生物学重复 | biological replicates |
| 技术重复 | technical replicates |
| 独立实验 | independent experiments |
| 阳性对照 / 阴性对照 | positive control / negative control |
| 随机化 | randomisation |
| 盲法 / 双盲 | blinding / double-blind |
| 纳入标准 / 排除标准 | inclusion criteria / exclusion criteria |
| 样本量计算 / 功效分析 | sample-size calculation / power analysis |
| 伦理审批 | ethics approval |
| 伦理委员会 | ethics committee / institutional review board (IRB) |
| 动物伦理委员会 | IACUC / animal ethics committee |
| 知情同意 | informed consent |
| 知情同意书 | written informed consent |
| 赫尔辛基宣言 | Declaration of Helsinki |
| 临床试验注册号 | clinical trial registration number |
| 软件版本 | software version |
| 参考基因组 | reference genome (with build/version) |

## Common CN-to-EN methods failure modes

- **"常规方法 / 标准条件 / 按说明书操作".** Translated literally these stay vague. Ask for the
  actual parameters, or — for "按说明书" — name the kit and any deviation from its protocol.
- **试剂无来源 (reagents with no source).** Chinese drafts often name a reagent or antibody with
  no supplier/货号/RRID. Flag each; recommend a Key Resources table if there are many.
- **细胞系无鉴定 (cell lines without authentication).** 鉴定 (STR) and 支原体检测 status are
  frequently omitted but routinely required. Ask for both.
- **伦理声明模糊 ("符合伦理要求").** "符合伦理要求" with no approving body or protocol number is
  not a compliant statement. Ask for the committee name and approval/protocol number; never
  write the statement as if approval is confirmed when it is not.
- **软件无版本 (software without version).** "用 Python 分析" / "使用 SPSS" with no version. Ask
  for the version of every analysis tool.
- **缺少随机化/盲法陈述.** Even when applicable, these are often unstated. Ask whether the study
  used randomisation and blinding, and how.
- **统计混入方法 (statistics folded in vaguely).** "进行了统计学分析" belongs in a proper
  statistics description — route to nature-stats, do not leave the vague phrase.

## Bilingual intake questions

When the Chinese input lacks what a reproducible Methods section needs, ask (in Chinese) for:

1. 关键试剂/抗体的供应商和货号（抗体还需 RRID、克隆号、稀释比和应用）。
2. 细胞系来源、是否做过 STR 鉴定、是否检测支原体。
3. 动物的品系、性别、周龄、来源；人类受试者的纳入/排除标准。
4. 主要仪器的型号和关键采集参数。
5. 关键步骤的具体参数（温度、时间、浓度、体积、循环数等）。
6. 生物学重复与技术重复各是多少？独立实验重复了几次？阴/阳性对照是什么？
7. 是否随机化、是否盲法？如何做的？样本量是怎么确定的（功效分析 / 预注册 / 经验依据）？
8. 伦理审批：批准单位、伦理批号、知情同意方式（临床试验还需注册号）。
9. 所有分析软件的名称和版本，以及自定义代码的获取方式。

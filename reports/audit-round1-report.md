# 研究Agent平台 · 第一轮实现真实性审计报告

> 审计日期：2026-08-31
> 方法：两套尺子 + 现场实测为据
> - **尺子 A（确定性算法）**：以数值积分 / scipy 1.18.1 / 教科书值为独立基准，跑出正确数值才算"真实现"
> - **尺子 B（LLM 型 Agent）**：单列一类，判据为"是否调用确定性服务"，评级降一档
>
> 结论先行：**确定性算法层是真货，但修复前带着 7 个 P0 级静默数值/语义错误；479 个全绿测试对此零敏感度。**

---

## 一、修复清单（全部已落地）

| # | 位置 | 缺陷 | 修复 | 实测改善 |
|---|------|------|------|---------|
| P0-1 | `app/services/statistics.py:901` `_normal_cdf` | A&S 7.1.26 展开点误用 `z`，应为 `x=z/√2`（指数项却用了 `-z²/2`，两处自变量不一致） | 统一自变量为 `x` | 最大绝对误差 **3.687e-2 → 6.925e-8**（约 53 万倍），恢复设计精度 1.5e-7 量级 |
| P0-2 | `app/services/statistics.py:853` `_approx_p_value` | 用 `z=t/√(1+t²/(2df))` 的 ad-hoc 变换冒充 t 分布，p 值系统性偏小（反保守） | 改用同文件已有的 `_incomplete_beta(df/2, 0.5, df/(df+t²))` 精确解，零新增依赖 | 48 采样点误差超标 **45/48 → 0/48**；α=0.05 下显著性结论翻转 **9/56 → 0** |
| P0-3 | `app/services/power_analysis.py:501` `_normal_cdf` | P0-1 的复制粘贴同源错误 | 同 P0-1 | 3.69e-2 → 6.9e-8 |
| P0-4 | `app/services/power_analysis.py:48` `sample_size_ttest` | 独立两样本误用单样本公式 `((zα+zβ)/d)²`，样本量只给一半 | `per_unit = 1 if paired else 2`，独立两样本用 `2(zα+zβ)²/d²` | d=0.5：32/组 → 64/组（scipy 精确解 64）；**最刺眼的对照**：`experiment/tools.py:352` 的异常兜底分支一直用的是正确公式 |
| P0-5 | `app/services/power_analysis.py:361` `_calculate_power_ttest` | ncp 口径错误（单样本 `d√n` 应为两样本 `d√(n/2)`）+ 临界值用 z 忽略小自由度 t 分布更宽 | 新增 `_noncentrality_ttest` / `_t_critical`（Cornish-Fisher 三阶）/ `_degrees_of_freedom`，并向上迭代到目标功效 | 功效偏差 **+0.21 → ≤0.06**；配对 d=0.8 真实功效 0.754 → ≥0.80 |
| P0-6 | `app/services/citation_network.py:304/370` | **共引与文献耦合语义互换**：`co_citation_analysis` 遍历 `reverse_adj`（算的是耦合），`bibliographic_coupling` 遍历 `adjacency`（算的是共引） | 共引遍历 `adjacency`（施引文献的参考文献两两配对），耦合遍历 `reverse_adj`（被引文献的施引者两两配对） | 受控图解析解对照：共引 `(p3,p4)=2`、耦合 `(p1,p2)=2`，均 PASS |
| P0-7 | 同上 `bibliographic_coupling` | `reverse_adj[cited] \| adjacency[cited]` 取并集，在"既施引又被引用"的混合图上把施引者与参考文献混入同一集合 | 去掉并集，只用 `reverse_adj[cited]` | 混合图（A→C,D; B→D; C→D）下旧实现产出无意义配对 `(A,D)`，新实现无跨界对 |

### P2（已记录、测试锁定现状，未修）

| # | 位置 | 缺陷 | 影响 |
|---|------|------|------|
| P2-1 | `statistics.py` `_approx_p_value_chi2` | Wilson-Hilferty 正态近似在 p<1e-3 的极端尾部退化（最坏 df=1/x=40 差 40 倍） | **不影响** α=0.05/0.01 的显著性判定（决策区间 41 点中仅 1 点 >10%）；影响的是对外打印"p<0.0001"类极小 p 值。修复需引入正则化不完全 Gamma 函数 |

### 环境与配置修复

- `python-docx` 缺失导致 `tests/unit/test_latex_l7_omml_semantics.py` 收集失败 → **整套 pytest 无法启动**（`Interrupted: 1 error during collection`）。已安装并写入 dev 依赖
- `scipy>=1.11`、`python-docx>=1.1` 已写入 `pyproject.toml` `[tool.poetry.group.dev.dependencies]`（**仅测试用，生产保持零第三方依赖手写**）
- `app/core/toolchain.py:439` 存在 `SyntaxWarning: 'str' object is not callable`（字符串列表漏逗号）——未修，见"遗留问题"

---

## 二、测试有效性判决（本次审计最重要的元结论）

| 实验 | 结果 |
|------|------|
| 修复前跑套件 | 479 passed |
| 把 t 分布 p 值改动最多 **49%** 之后 | 仍 479 passed |
| 结论 | 存在的测试对统计引擎的数值正确性**零敏感度**——它们测的是管道（请求→handler→返回形状），不是数学 |

**佐证**：语义互换（P0-6）修复后，763 个测试中同样没有一个失败——没有任何用例锁过共引/耦合的语义。

### 新增回归防线

| 文件 | 用例数 | 锚定点 |
|------|-------|--------|
| `tests/unit/test_numerical_golden.py` | 273（9 skip） | scipy 作为独立 oracle；含反保守检验、α 边界翻转检验、scipy 非中心 t 精确样本量对照 |
| `tests/unit/test_citation_network_golden.py` | 11 | 受控引用图解析解；含**混合角色图**（唯一能暴露 P0-7 的形态）与"结果不得互换"断言 |
| 合计 | **763 passed / 9 skipped** | 修复前 479 |

---

## 三、第一轮定级结果

### 确定性算法层（尺子 A）

| 模块 | 体量 | 修复前覆盖 | 定级（修复后） |
|------|------|-----------|---------------|
| `services/statistics.py` | 987 行 | 10.4% | **真实现**（数值验证：正态/t/F 精确，卡方决策区可用） |
| `services/power_analysis.py` | 545 行 | ~30% | **真实现**（`_normal_quantile` 本就是正确的 Acklam 实现，误差 1.8e-9；修复后样本量/功效与 scipy 非中心 t 对齐） |
| `services/citation_network.py` | 916 行 | 9.2% | **真实现**（共引/耦合/指标在受控图上与解析解一致；`compute_metrics` 修复前即正确） |
| `core/cache.py` + `core/rate_limit.py` | 628 行 | 高 | **真实现**（ABC + 双后端 + Redis ZSET+Lua 滑动窗口 + 优雅降级；无数学成分，未做数值验证） |

> 注意：覆盖率最低的恰是最有价值的模块。**"测试多"和"测到了要害"是两回事。**

### Agent 层（尺子 B，17 个）

| 定级 | Agent | 判据 |
|------|-------|------|
| 混合型（prompt + 确定性服务） | `data`、`experiment`、`literature`、`writing`、`citation` | 真实调用 `services/statistics` / `power_analysis` / `citation_network` / 导出工具 |
| 纯 prompt 薄壳（12 个） | `stats`、`methods`、`cover`、`polishing`、`reviewer`、`response`、`reader`、`paper2ppt`、`paper_to_patent`、`submission_package`、`data_agent`、（`coordinator` 为调度器，特殊） | 全部逻辑为"拼 prompt → `call_llm` → 回传字符串"，无确定性服务调用；无 LLM Key 时完全不可用 |
| 特殊 | `figure` | 唯一不依赖 LLM 的 Agent（纯 matplotlib），刻意不继承 BaseAgent |

> 薄壳本身不是缺陷——`stats/agent.py` 的 prompt 工程是合格的。问题在于：这些 30~70 语句的薄壳拥有 **98-100% 测试覆盖率**，而真正干活的算法层只有 10%。覆盖率数字与风险分布**正好相反**。

### 昇腾层（9 个模块）

| 定级 | 模块 | 证据 |
|------|------|------|
| 真实现（真 I/O） | `validator`（spawn `lm-eval` 跑 gsm8k 评测）、`profiling`（`Popen` 采集）、`perf_tuning`（`rpm` 查询 + 子进程）、`debugging`、`toolchain`（生成可执行脚本） | 0% 覆盖是"需要真机"，不是"没实现" |
| 数据类框架 | `alignment` | 纯 dataclass/enum 定义对比约束，spec-as-code，无计算 |
| HTTP 客户端 | `ascend` | vLLM OpenAI 兼容客户端 + `torch_npu` 环境探测；README 宣称的"NPU 环境检测"实为 `import torch_npu` 后读 `device_count()`，**没有** `npu-smi` 子进程 |
| **半实现** | `adaptation` | 1700 行中 4 处 `# TODO`：权重加载（1040）、前向推理（1045）、vllm registry 注册（1051）、Triton 算子 NPU 兼容实现（1125）均未写 |
| 纯逻辑 | `history_to_skill` | 无 I/O，1298 行 |

### 文档与实际的偏差

| README 宣称 | 实际 |
|------------|------|
| "20+ Agent" | 17 个业务 Agent；昇腾 9 模块不在 Agent 体系内（core+api 直连） |
| "47 文件 / 479 用例" | 数字准确，但套件因缺依赖**根本无法启动** |
| 昇腾 9 模块全部 "✅" | `adaptation` 含 4 处 TODO，属半实现 |
| 目录树列出 34 个 api/v1 文件 | 实际 45 个 + 4 个子目录，文档已漂移 |

---

## 四、回答原始问题：「这个项目的真实边界在哪」

1. **最值钱的部分是真货，但曾带毒**。约 2400 行确定性算法（统计/功效/引用网络）是实打实的手写实现，修复后经独立基准验证可靠。这类"真货里的静默错误"比空壳危险得多——它会给出一个**看起来合理、实际上系统性错误**的数字（声称功效 0.84，真实 0.63），而 479 个绿测试为它背书。

2. **平台主体是 prompt 编排层**。17 个 Agent 中 12 个是薄壳，价值取决于 LLM 而非代码本身。这不是缺陷，是产品形态，但应如实标注依赖。

3. **昇腾层大部分真、一块半成品**。`adaptation` 的 4 处 TODO 意味着"模型适配"功能实际不可用，README 的 ✅ 过于乐观。

4. **测试体系的方向性错误**：覆盖率集中在无风险的薄壳，风险最高的算法层近乎裸奔。本次新增的 284 个 golden 用例是第一道真正的数值防线。

## 五、遗留问题（建议下一轮）

1. `app/core/toolchain.py:439` SyntaxWarning（漏逗号）
2. `app/core/adaptation.py` 4 处 TODO——要么补全要么在 README 标注为实验性
3. 卡方极端尾部：引入正则化不完全 Gamma（约 45 行，NR 标准算法），与已有 `_incomplete_beta` 风格一致
4. `core/alignment.py`、`core/ascend.py` 等 0% 覆盖模块补充基础用例
5. `app/agents/base.py:155` `use_tool` 对"声明了工具但无实现"只抛异常不预警——建议启动时做一次声明/实现一致性自检
6. `agents/data/tools.py:292` 等处函数内延迟 import，建议确认无循环依赖后上移
7. README 与实际目录结构的同步

---

## 附录：审计工具产物

- `reports/probe_stats.py` — 统计分布精度审计（数值积分基准）
- `reports/probe_power.py` — 功效分析审计（非中心 t 精确基准）
- `reports/probe_citation.py` — 引用网络审计（受控图解析解）
- 修改文件：`app/services/statistics.py`、`app/services/power_analysis.py`、`app/services/citation_network.py`、`pyproject.toml`
- 新增测试：`tests/unit/test_numerical_golden.py`、`tests/unit/test_citation_network_golden.py`

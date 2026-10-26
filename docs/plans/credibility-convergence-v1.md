# 可信度收敛 v1 设计契约

> 2026-09-07 grill 会话产物。逐项决策均已确认；"未问而采用的默认"一节为设计者代答默认值，可否决。
> 定位：本轮不做新功能堆砌，目标是**把"宣称"变成"实测"**，并在此地基上只做两个团队刚需扩展
> （结果持久化、分享/fork）。

---

## 0. 实测基线（2026-09-07，本机 `.venv`，Python 3.14.0）

所有数字均为当次运行输出，不是引用文档。

| 项 | 实测 | 文档宣称 | 判定 |
|---|---|---|---|
| pytest | **545 passed, 1 skipped, 22.86s**（全绿） | README 763 / 契约 776 | 宣称失实 |
| mypy `app` | **890 errors in 112 files**（checked 146） | pyproject 注 1198 | 宣称失实 |
| ruff `app` | **0 error**（2026-09-07 已清零） | 隐含"已清理" | ✅ 已达成 |
| 数据库表 | **8 张** | — | 无 artifacts / 无 share |
| 前端页面 | **27 + 9（昇腾）= 36** | `frontend-defects.md` 称"13 模块无前端" | 文档已作废 |
| NPU 环境 | torch / torch_npu / `/dev/davinci*` **全部缺失** | 昇腾 9 模块 README 全标 ✅ | 零可验证性 |
| Python 运行时 | `.venv` **3.14.0** | `pyproject` `^3.11`、mypy `3.11`、black/ruff `py311` | 已统一为 3.14 |
| 工具链实际版本 | mypy 2.1.0 / ruff 0.15.18 / black 26.5.1 / pytest 9.1.0 | 声明 `^1.7.1` / `^0.1.8` / `^23.12.0` / `^7.4.3` | 全部低一个大版本，已校正 |

**关键结论：776 这个数从来不存在。**
`git diff c6378b6 HEAD -- tests/` 显示测试**只增不减**（新增 4 个文件、修改 1 个）。
即 commit message 中的 `776 passed` / `536 passed` 与 README 的 `763 passed` 均为未经核实的手写数字。
这是本轮要根治的第一类病：**最该客观的数字是编的**。

### mypy 890 条的构成（决定还法）

| 错误码 | 数量 | 性质 | 批次 |
|---|---|---|---|
| `no-untyped-def` | 345 | 缺注解，机械 | 一 |
| `type-arg` | 111 | 容器泛型参数，机械 | 一 |
| `no-untyped-call` | 105 | 调无注解函数，随批次一自动消失 | 一 |
| `var-annotated` | 18 | 缺变量注解，机械 | 一 |
| `import-untyped` | 5 | 三方库无 stub | 一 |
| **`arg-type`** | **106** | 类型不匹配，可能真 bug | 二 |
| **`assignment`** | **83** | 可能真 bug（如 `main.py:417/422`） | 二 |
| **`attr-defined`** | **41** | 可能真 bug（属性不存在） | 二 |
| `no-any-return` / `index` / `return-value` / `operator` / `misc` / `dict-item` / `type-var` | 72 | 需判读 | 二 |

- 第一批（机械）：**584 条** | 第二批（人工 triage）：**302 条** | 其余 4 条按原始输出归类
- 目录集中：`app/api/v1` **366 条（42%）**、`agents/literature` 58、`services/library_service.py` 40、`agents/writing` 34

### 顺带澄清（给 README 平反的一条）

`app/core/adaptation.py` 的 4 处 `# TODO` **全部位于 f-string 模板字符串内部**
（紧邻的 `def register_{arch_class.lower()}_adapter()` 即为铁证）。
adaptation 是**代码生成器**，产出的骨架文件故意带 TODO 占位符供用户填充——这是设计，不是缺口。
README 现措辞（"4 处 TODO、未实现"）**低估了**该模块，需改。

---

## 1. 决策清单

| # | 决策点 | 结论 |
|---|--------|------|
| 1 | 本轮首要目标 | **可信度收敛**（不做新功能堆砌）。理由：已有 9 条宣称差距清单 + 890 类型债，在此地基上扩功能只会放大失真。 |
| 2 | 仲裁机制 | **GitHub Actions CI**。全量测试 22 秒，CI 成本≈0；无外部仲裁者，数字纪律必然烂掉（776 即前车之鉴）。远端已为 GitHub，可直接启用。 |
| 3 | mypy 口径 | **基线文件 + 增量归零**。存量落 `reports/mypy-baseline.txt`，CI 对比 merge-base 只对改动文件计数，新增必须为 0；存量随修复递减。 |
| 4 | 还债方式 | **分两类走**：批次一机械批（584 条，零风险可并行）；批次二人工 triage（302 条，可能挖真 bug）。 |
| 5 | 执行方式 | **AI 代理批量 + 人审关键**。机械劳动交代理（按目录切片），硬门禁：全量 545 不降 + mypy 不增；302 条人工审。 |
| 6 | 用户场景 | **小团队真实使用**（非毕设/作品集/SaaS）。扩展优先级据此锁定为"协作与结果沉淀"。 |
| 7 | 协作形态 | **分享链接 + fork 导入**。零侵入现有查询，避开并发写与权限模型两个深水区。 |
| 8 | fork 语义 | **全量深拷贝**：文献 + 分类/标签重建 + 笔记 + 引用关系，接收方拿到可独立演化的完整库。 |
| 9 | 排期 | **先立 CI，再双线并行**。避免"三周只还债无新功能"的枯竭期。 |
| 10 | 昇腾模块 | **诚实降级标注**。README 表格 ✅ → 标注验证状态，9 模块逐行标。本机无 NPU，不假装验证过。 |
| 11 | 结果持久化 | **进本轮，做通用 artifacts 表**。当前 8 张表无任何一张存 Agent 产出，上周的审稿回复找不回来。 |
| 12 | 缺陷处置 | **先 triage 再分流**：真缺陷 → 单独提交 + 回归测试 + 登记差距清单；误报/设计如此 → 批量处理（后者加 `type: ignore` **必须注明理由**）。 |
| 13 | 前端范围 | **只清失实文档 + 8 项 backlog 入单不排期**。UIUX P0（设计 Token 断链）已于 2026-08-31 修复并验证（21/21 对比度 PASS、5/5 验收链 PASS），无阻断级问题。 |
| 14 | Python 版本 | **统一 3.14，CI 单版本，不做 3.11+3.14 矩阵**。实测 `mypy app` 在 3.11 与 3.14 下均为 **890 条**（基线不变，切换零成本）；代价仅 ruff 由 3 条升至 7 条（+4×`UP037`，已自动修复）。 |

---

## 2. 未问而采用的默认（可否决）

### CI

- **三条 job**：`ruff`（硬门禁，须 0 error）→ `mypy`（基线 + 增量归零，仅对 diff 文件计数）→ `pytest`（须 ≥545 passed 且 0 failed）。任一红即阻断 PR。
- **依赖安装**：新增 `requirements-dev.txt`（`-r requirements.txt` + 版本对齐实测的 pytest/ruff/mypy/black + scipy/python-docx），CI 与 `make dev` 共用之，保证工具链版本一致（门禁 G9）。
- **环境变量**：CI 必须显式 `DEBUG=true`，否则 `validate_security()` 按生产基线拒绝启动（R9）。
- **本地复刻**：`make ci` 一次跑完三条门禁；`make baseline` 重生成基线，`make check-types` 做增量校验。
  （本机 Git Bash **无 `make`**，需直接调用等价命令：`ruff check app` /
  `git diff --name-only origin/master...HEAD -- 'app/**/*.py' | python scripts/gen_mypy_baseline.py --check --stdin` /
  `pytest -q --no-header`。三条已于 2026-09-07 本地实测全绿。）
- **black 不设硬门禁**（`continue-on-error`）：见风险 R7，与 ruff 的宽度语义冲突未解决前不阻断。
- **触发**：`pull_request` + `push` 到 `master`。
- **Python 版本：统一 3.14，CI 单版本**（决策 #14，2026-09-07 已落地）：
  - `pyproject`：`python = "^3.14"`、`mypy python_version = "3.14"`、`black target-version = ['py314']`、`ruff target-version = "py314"`。
  - **已验证切换零成本**：`mypy app --python-version 3.14` 与 3.11 同为 **890 条**，基线数字可直接沿用。
  - 切换代价：ruff 3 → 7 条（新增 4×`UP037` 引号注解，PEP 649 下可去引号），已 `--fix` 自动修复。
  - 工具链声明同步校正为实测版本：mypy `^2.1.0` / ruff `^0.15.18` / black `^26.5.1` / pytest `^9.1.0` / pytest-asyncio `^1.4.0` / pytest-cov `^7.1.0`。原声明普遍低一个大版本，`poetry install` 出来的工具链与本地不一致，会让 CI 结论不可复现。
- **缓存**：`actions/setup-python` 的 pip cache，按 `requirements.txt` hash 键控。

### mypy 基线

- 文件格式：`file:line:code` 排序后的纯文本，落 `reports/mypy-baseline.txt`。
- 由脚本生成（`scripts/gen_mypy_baseline.py`），**每次合并代理批次后必须重生成**，否则基线漂移会让门禁失真。
- 基线数字必须**单调不增**；上涨即 CI 红。

### 分享 / fork

- **token**：复用 `app/api/v1/auth.py:479` 的 `secrets.token_urlsafe(32)`。
- **存储**：DB 只存 `sha256(token)` 哈希，明文 token **仅在创建响应中返回一次**（对齐 refresh token 纪律）。
- **TTL**：默认 7 天，可空（永久）；提供显式撤销端点 `DELETE /api/v1/shares/{id}`。
- **访问**：接收方须登录；未登录访问分享链接 → 401 并引导登录，**不静默降级为公开**。
- **fork 一致性**：分类/标签按名字重建；引用关系按 `paper_id` 映射重连；笔记随文献拷贝；
  tag `usage_count` 与 category `paper_count` **必须复用 `LibraryService.add_*` 逐条写入**以保证计数正确
  （不得直接 bulk insert——这正是当初做 LibraryService 的意义）。
- **share_links 表设计成通用**：`(resource_type, resource_id)`，本轮只实现 `library` 与 `artifact` 两类。

### artifacts

- 新表 `agent_artifacts`：`user_id` / `agent` / `title` / `payload`(JSON) / `created_at`，含 `user_id` 索引与 `(user_id, agent, created_at)` 复合索引。
- 走 **Alembic 迁移**（`alembic revision --autogenerate`），不手工建表。
- 能力面：创建 → 列表 → 按 agent/时间筛选 → 重新导出 → 删除。**不做语义检索**（Milvus 本机未必在跑，引入新失败模式）。

### 文档校正（第 0 步，半天内完成）

- README：`763 passed` → `545 passed`（并改为指向 CI 徽章 / 最近一次运行）；`1198` → `890`。
- README 昇腾表格：9 模块 ✅ → 标注验证状态（`mock 覆盖` / `需 NPU 硬件验证`），**不留裸 ✅**。
- README `adaptation` 注脚：改为"生成的适配骨架含 4 处占位符供填充（代码生成器设计）"，去掉"未实现"的误导措辞。
- `docs/analysis/frontend-defects.md`：顶部加**作废声明**，指向现状（现已 36 页，原列 13 个"无前端"模块均已落地）。

### 明确不做

- NPU 环境采购 / 云上昇腾验证（周期不可控）
- Milvus 语义检索
- 前端测试门禁（vitest）
- 真 workspace 共享库（并发写与权限模型，风险等级不符本轮）

---

## 3. 建议实施顺序

| 步 | 内容 | 门禁 |
|---|---|---|
| 0 | 文档数字校正 + 昇腾降级标注 + 作废声明 | 人工核对 |
| 0.5 | ✅ **已完成**（2026-09-07）：Python 统一 3.14 + 工具链版本声明校正 | ruff 0 / mypy 890 / pytest 545 三项复测通过 |
| 1 | ✅ **已完成**（2026-09-07）：ruff 清零（4×`UP037` 自动修复 + 2×E501 手工缩行 + 删 `power_analysis.py:437` 死变量 `z2`） | `ruff check app` = **0** ✅ |
| 2 | ✅ **已完成**（2026-09-07）：`scripts/gen_mypy_baseline.py` + `reports/mypy-baseline.txt`（112 文件 / 890 条） | 负向测试已验证门禁会拦截（退出码 1） |
| 3 | ✅ **已完成**（2026-09-07）：`.github/workflows/ci.yml`（三 job，单版本 3.14）+ `requirements-dev.txt` + Makefile `baseline`/`check-types`/`ci` | YAML 校验通过；改动文件检测与 pytest 解析逻辑本地干跑通过 |
| 4 | **批次一**：584 条机械注解，代理按目录切片，分批合入 | 每批：pytest ≥545 且 mypy 不增；合批后重生成基线 |
| 5 | **批次二**：302 条人工 triage，按决策 #12 分流 | 真缺陷均带回归测试 |
| 6 | `agent_artifacts` 表 + 迁移 + 服务 + API（新文件为主） | e2e 全链路 |
| 7 | `share_links` + fork 深拷贝 | golden 断言一致性 |
| 8 | 前端 8 项 backlog 随手做 + 文档作废标记落地 | 构建零报错 |

**并行约定（决策 #9）**：步骤 4（代理）与步骤 6/7（人）并行。硬约束——
**新功能只准新增文件，禁止重构存量文件**，把合并冲突面压到最小。

---

## 4. 验收门禁（PASS / FAIL）

| # | 门禁 | 判据 |
|---|---|---|
| G1 | CI 三 job 全绿 | ruff / pytest / mypy 任一红即阻断 |
| G2 | ruff | `ruff check app` = **0 error** ✅ **已达成**（2026-09-07） |
| G3 | pytest | **≥545 passed，0 failed** |
| G4 | mypy 增量 | 改动文件新增错误 = **0**；基线数字**单调不增**（890 → …） |
| G5 | 文档可复现 | README 中所有数字可由脚本/CI 输出复现，**无手写数字** |
| G6 | 昇腾标注 | 9 模块均有验证状态标注，**无裸 ✅** |
| G7 | artifacts | 创建 → 列表 → 筛选 → 重新导出 → 删除 全链路 e2e 通过 |
| G8 | share/fork | 受控库 fixture：生成 → 他人打开 → fork → 接收方条目/笔记/引用数与原库**逐一相等** |
| G9 | 工具链可复现 | CI 所用 mypy/ruff/pytest 版本与 `pyproject` 声明**在同一大版本内**，静态检查结论不随工具版本漂移 |

---

## 5. 风险与缓解

| 风险 | 缓解 |
|---|---|
| R1 代理批量注解引入行为变更 | 每批 CI 全量 pytest ≥545 + mypy 不增；**禁止代理改动任何逻辑**，只加注解 |
| R2 基线漂移导致门禁失真 | 每批合并后强制重生成基线；基线单调不增写进 CI 断言 |
| R3 fork 深拷贝数据不一致 | golden 测试（受控库 fixture，断言条目/笔记/引用/tag 计数全等） |
| R4 双线并行合并冲突 | 新功能只新增文件；代理切片按目录互斥（不同批次不碰同一目录） |
| R5 Python 3.11 / 3.14 不一致 | 双版本矩阵，首次运行即暴露；不许靠忽略规则压红 |
| R6 分享链接成为越权入口 | 哈希存储 + 登录强制 + ownership 校验，安全测试对齐既有 W1/W2 纪律 |
| R8 **基线在 Windows 生成、CI 跑 Ubuntu** | mypy 结果可能因平台差异（`sys.platform` 相关 stub、可选依赖可用性）导致 Ubuntu 上的错误数与 Windows 基线不一致，产生假回归。**首次 CI 运行即可验证**：若 typecheck job 红且报大量文件上涨，二选一——① 在 Ubuntu 上重新生成基线并提交；② 把 typecheck job 的 `runs-on` 改为 `windows-latest` 与开发环境对齐。**不许用 `--ignore-missing-imports` 之类开关把红压成绿。** |
| R9 **CI 缺 `.env` 会直接启动失败** | `.env` 未被 git 跟踪（正确），但 `Settings.validate_security()` 在非 DEBUG 下强制要求 SECRET_KEY / CORS_ORIGINS / 有效 Fernet 密钥。CI 已显式设 `DEBUG=true`（与本地一致）。若将来需要跑生产模式路径的测试，需用 GitHub Secrets 注入真实密钥。 |
| R7 **black 与 ruff 对中文行宽判定不一致** | black 按**字符数**（中文记 1），ruff E501 按**显示宽度**（中文记 2），同一行 black 认为 82 未超、ruff 认为 89 已超 → 两者会在 CI 内互相打架。当前仅 2 行触发，已手工缩短绕过。**治本方案待定**：改用 `ruff format` 统一宽度语义，或为 E501 单独放宽 `pycodestyle.max-line-length`。`app/agents/*/prompts.py` 已豁免 E501，但业务代码里的中文注释/desc 仍会持续触发。 |

---

## 6. 执行进度（2026-10-26 追记）

> 详细数据与缺陷明细见 [reports/optimization-round2-report.md](../../reports/optimization-round2-report.md)。

| 步骤 | 状态 |
|---|---|
| 4 批次一（按目录切片） | 全部完成：切片 1（agents 198→41）/ 2（api A 205→86）/ 3（api B 167→8）/ 4（core 159→21）/ 5（337→62）；**全量 890 → 58（-93.5%）** |
| 4.5 清零冲刺 | 同日继续 triage 至 **mypy strict 全清零（0 错/152 文件）**；新增 /health Redis await 真缺陷修复与 export/billing HTTP 冒烟 |
| 5 批次二 triage | 12 项真缺陷修复（B1–B12）+ 7 项安全加固（S1–S6、S10），均带回归测试；另有 User 模型 Mapped[] 转换清偿 52+ 条 Column 连带错误 |
| 6 agent_artifacts | ✅ 表+迁移 e8a4f2c6b9d1+服务+API+e2e；G7 全链路通过；orchestrate 支持 save_artifact opt-in；前端「结果存档」页 |
| 7 share_links + fork | ✅ 表+服务+API+e2e；G8 黄金计数全等；前端「分享与 Fork」页 |
| 8 前端 | 结果存档/分享两页 + coordinator save_artifact 开关 + refresh single-flight + isTokenExpired + PWA 不缓存 API + 残留文件清理；tsc 与 build 零报错 |

门禁终态：G2 ruff=0 ✅ / G3 pytest **575 passed** 全绿（unit+integration+e2e 同进程）/ G4 基线 890 → **0** 已重生成并通过 --check ✅ / G7 ✅ / G8 ✅ / G5 README 数字已同步实测 ✅。

# 研究Agent平台 全面体检报告

- **日期**：2026-08-23
- **对象**：`D:\AI_agent`（research-agent-platform，FastAPI 后端 + React 前端 + 昇腾 NPU 子系统）
- **范围**：后端与部署 / 前端 / 昇腾子系统 / 根目录遗留物（四域全覆盖）
- **方法**：静态深读 + 实跑工具链（ruff / mypy / pytest / tsc / vite build）+ 漏洞实证（PoC）
- **风险等级**：🔴 P0 = 立即处理；🟠 P1 = 一周内；🟡 P2 = 一个月内；⚪ P3 = 观察项

---

## 0. 执行摘要

**一句话结论：业务代码质量高于平均水平（ruff 全绿、前端 `: any` 为零、329 测试全过），但工程底座有致命缺口——没有版本控制、存在一个已实证的任意文件读取漏洞、三组路由完全裸奔；「manifest 驱动架构」「Alembic 迁移」「mypy strict」三项均为纸面承诺，实际未生效。**

体检打分（10 分制）：

| 维度 | 得分 | 一句话理由 |
|---|---|---|
| 代码卫生 | 7.5 | ruff 零告警、TODO 密度极低、前端 any/console 为零 |
| 类型安全 | 3 | mypy strict 声明了但 **1198 个错误**（126/161 文件） |
| 测试 | 5.5 | 329 个单元测试全过且快，但 e2e/performance 是空目录、昇腾 9600 行仅 6 个测试 |
| 架构一致性 | 5 | 分层清晰但 services↔agents 循环、core 混入 8600 行 NPU 工具、三套实例化模式并存 |
| 安全 | 3 | 一个实证漏洞 + 三组无鉴权路由 + 部署链多处泄密 |
| 可部署性 | 4 | 主 Dockerfile 可用；**昇腾镜像因缺 alembic 启动即崩** |
| 版本控制 | 0 | **不是 git 仓库** |

**Top 10 问题（跨域汇总，详证据见各章）**：

| # | 等级 | 问题 | 位置 | 证据强度 |
|---|---|---|---|---|
| 1 | 🔴 | SPA 兜底路由任意文件读取（路径穿越），实测 `GET /../../.env` 返回 200 + 文件内容 | `app/main.py:342-346` | **PoC 实证** |
| 2 | 🔴 | ascend / adaptation / alignment 三组路由零鉴权；`PUT /ascend/mode` 可被任何人切换全局 LLM 模式 | `app/api/v1/ascend.py:131` 等 | 逐文件核对 |
| 3 | 🔴 | 整个项目不在版本控制下（无 .git） | 项目根 | `git status` 失败 |
| 4 | 🔴 | `.dockerignore` 不排除 `.env*`，而 `Dockerfile.ascend` 是 `COPY . .` → 密钥烘焙进镜像 | `.dockerignore` / `Dockerfile.ascend:36` | 配置核对 |
| 5 | 🔴 | `requirements.ascend.txt` 缺 `alembic`，昇腾容器启动即 ImportError | `requirements.ascend.txt` / `app/main.py:34` | 依赖链推断 |
| 6 | 🟠 | Coordinator 路由表与注册表脱节：figure 必抛「未知Agent」、data_agent 不可达、工作流第 8 步必崩 | `planner.py:41-45,194` / `figure/agent.py:265` | 代码逻辑链 |
| 7 | 🟠 | `PATCH /auth/me` 绕过 SSRF 校验写入内网 base_url，用户级客户端将向其发请求（带 api_key） | `app/api/v1/auth.py:377-382` | 代码对照 |
| 8 | 🟠 | 限流中间件写好了但从未接线（仅登录/忘记密码两处）；Redis 故障默认放行 | `app/core/rate_limit.py:268` / `config.py:42` | 全局 grep |
| 9 | 🟠 | Alembic 仅 1 个 baseline 且与 models 漂移（3 个唯一约束缺失），启动默认走 create_all 双轨建表 | `migrations/versions/` / `app/main.py:110-128` | 迁移对照 |
| 10 | 🟡 | 前端 160 行 Tailwind 设计系统是死配置（被空壳 `.js` 抢先加载），`text-copper` 等 500+ 处类名无样式输出 | `frontend/tailwind.config.js` vs `.ts` | 构建产物 CSS 比对 |

---

## 1. 验证方法与工具链实测结果

全部命令在项目 venv（Python 3.14.0）下实际执行：

| 工具 | 命令 | 结果 |
|---|---|---|
| ruff 0.15.18 | `ruff check app tests` | ✅ **All checks passed**（exit 0） |
| mypy 2.1.0 | `mypy app`（strict） | ❌ **1198 errors in 126/161 files** |
| pytest 9.1.0 | `pytest -q` | ✅ **329 passed in 2.80s**（1 个 starlette 弃用警告） |
| tsc 5.6 | `tsc -b`（frontend） | ✅ exit 0 |
| vite 5.4 | `npm run build` | ✅ 5.07s，PWA 预缓存 41 个文件 766 KiB |
| 漏洞 PoC | 原始 socket 请求 `/..%2F..%2F.env` | ❌ **HTTP 200，返回 .env 真实内容**（见 §3.1） |

**mypy 错误分类**（前 12 类）：`no-untyped-def` 417、`no-untyped-call` 222、`type-arg` 133、`arg-type` 107、`assignment` 88、`attr-defined` 58、`no-any-return` 40、`var-annotated` 28、`import-not-found` 26、`index` 21。约 65% 是「缺类型标注」债，35%（arg-type/assignment/attr-defined/index ≈ 274 个）是真实类型不匹配，其中 `import-not-found` 26 个值得单独排查（疑缺 stubs 或坏 import）。

**测试分布**：`tests/unit`（含 `unit/agents`）308 个 + `tests/integration` 21 个 = 329；`tests/e2e/`、`tests/performance/` 为**空目录**，`tests/alignment/` 只有数据 fixture 无测试文件。全部 2.8 秒跑完说明重度 mock、无真实外部依赖——单元纪律好，但没有防线拦截「环境级」回归（如鉴权透传测试只覆盖 research 域，ascend 域无覆盖）。

---

## 2. 架构健康度

### 2.1 规模与分层

后端 `app/` 161 个 Python 文件、约 43,200 行：api 35 个路由模块 7,576 行（224 端点，按 research/library/platform/ascend 四域聚合于 `app/api/v1/__init__.py:1-21`）、agents 15,723 行（14 个业务 agent + base/registry/manifest_router）、core 11,432 行（21 个模块）、services 5,310 行（10 个模块）、utils 2,087 行。数据层：SQLAlchemy 2 async，默认 SQLite（`research_agent.db`），8 张表，users.api_key 用 Fernet `EncryptedString` 透明加解密（`app/models/types.py:44-88`，无密钥时退化明文并告警）。

依赖方向总体成立（api→agents/services→models），但有四处明确破环：

1. **services ↔ agents 循环**：`app/services/review_loop.py:20-21` import ReviewerAgent/WritingAgent；反向 `app/agents/citation/agent.py:10`、`app/agents/data/tools.py:292` import app.services.*。
2. **core ↔ utils / core ↔ models 双向**：`utils/logger.py:6`→core.tracing 而 core/events.py:21→utils.logger；`core/billing.py:4`↔`models/`。
3. **core 沦为杂物箱**：21 个 core 文件里 7 个（adaptation 1700 行、perf_tuning 1474、history_to_skill 1298、debugging 1163、validator 1114、toolchain 981、profiling 886，合计约 8,600 行）是昇腾 NPU 运维工具，与 cache/database/security 等基础设施同层。好在这 8 个模块**零 `app.*` 依赖**（torch/npu import 全在生成脚本的模板字符串里），可以整体搬走。
4. **运行期代码生成失控**：`POST /api/v1/agents/confirm` 直接把 LLM 生成的 .py 写进 `app/agents/`、`app/api/v1/` 并改 `__init__.py`（`app/core/agent_generator.py:179-200`，用相对路径 `Path("app/agents")` 依赖 CWD）——在没有版本控制的前提下尤其危险。

### 2.2 Agent 体系

- **注册**（E1 插件化）：`registry.py:26-70` 扫描 agents/ 子目录，import `agent.py`，注册 BaseAgent 非抽象子类；coordinator 懒加载实例并缓存（`coordinator/agent.py:24-42`）。
- **调度**：planner 纯关键词子串匹配路由（16 条 `SKILL_KEYWORD_MAP`，`planner.py:5-91`，兜底把整个 request `str()` 全文扫描 :301-306）；`_group_by_level` Kahn 式分层 + 循环依赖检测（:190-195）；`asyncio.gather` 层内并行；`_inject_upstream`（agent.py:135-171）把上游成功结果塞进 `request["upstream_results"]` 再按 3 条硬编码特例分拣（literature→writing/data、experiment→data）。
- **事件**：进程内 TaskEventBus（`core/events.py:26-73`），每 task_id 一组 asyncio.Queue，maxsize 256 满则丢弃。

Coordinator 本体（agent.py 289 行）实现质量不错：异常容忍（partial_failure 聚合）、span 追踪、事件推送齐全。小瑕疵：`_execute_plan_parallel` 里 `completed` 变量（:93,:109,:131）只写不读是死代码；agent 间数据契约硬编码在协调器里，新 agent 无法声明自己的输入。

### 2.3 五大架构薄弱点

1. **路由表与注册表脱节（功能性 bug，不只是设计问题）**
   - `FigureAgent` 不继承 BaseAgent（`app/agents/figure/agent.py:265-266` 注释明言），registry 只收 BaseAgent 子类 → "figure" 不在注册表；但 planner 关键词表/能力地图/工作流都含 figure（`planner.py:41-45,131-134,193`）。任何含「作图/图表」关键词的任务在 `get_agent` 抛「未知Agent: figure」。
   - `data_agent`（DataAvailabilityAgent）不在 16 条关键词表里，「数据可用性」全部路由到 data；而工作流 `write_from_scratch` 第 8 步 `{"agent":"data","task":"statement"}`（`planner.py:194`）在 DataAgent（只支持 analyze/visualize/upload/summary）上必抛「未知任务类型: 'statement'」。
   - **修法**：FigureAgent 改继承 BaseAgent（或 registry 增加非 BaseAgent 白名单）；关键词表补 data_agent 条目；工作流第 8 步 agent 改为 data_agent。加一条「每个 keyword 命中的 agent 必须在 registry 中」的启动期一致性断言测试。
2. **skills 三份拷贝 + ManifestRouter 死代码**：`app/skills/nature-*`（12 目录，零代码引用）、根 `nature-skills/skills/`、`app/agents/<agent>/{SKILL.md,manifest.yaml,static/}` 三处并存且内容已漂移；`app/agents/manifest_router.py`（109 行）零消费者；`registry.py:8` 文档宣称需要 manifest.yaml，实际 `_scan_agents` 只认 agent.py。真实路由协议是硬编码关键词匹配。**修法**：定一份权威来源（建议 agents/ 内那份），删 `app/skills/` 与根 `nature-skills/`（后者是第三方 git clone，移出主目录），删 manifest_router.py 或真正接线。
3. **Alembic 单 baseline + create_all 双轨**（详见 Top10 #9）。**修法**：补一个迁移把 3 个唯一约束（`models/library.py:21,52,70` 的 `uq_user_paper`/`uq_user_category_name`/`uq_user_tag_name`）带上；`MIGRATION_ON_STARTUP` 生产置 true、去掉迁移失败 create_all 兜底（改为启动失败）。
4. **层约定失效**（services↔agents、core 杂物箱、运行期写代码，见 2.1）。**修法**：ascend 工具包整体迁到 `app/ascend/` 或独立包；`agent_generator` 的写盘目标移到白名单目录并要求 git 存在（当前无 git，写错即永久覆盖）。
5. **近名模块职责冲突 + 三套实例化模式**：data（数据分析）/data_agent（数据可用性声明）/stats（统计文字审计）/services/statistics（统计计算）四者命名互相踩踏；`descriptive_statistics` 与 `correlation_analysis` 在 `agents/data/tools.py:100-172` 和 `services/statistics.py:705` 各实现一遍；参考文献格式化两套（`agents/writing/tools.py:1069` vs `services/reference.py:188`）。agent 获取三套并存：lru_cache 工厂（12 处）vs 模块级实例（`api/v1/stats.py:13` 等 4 处）vs 每请求 new（`api/v1/reviewer.py:78` 等），后两套使「避免重复实例化 LLM 客户端」的设计落空。**修法**：统一走 registry/lru_cache 工厂；重命名 data_agent→data_availability；删重复实现留一处。

### 2.4 死代码清单（app 内）

| 项 | 规模 | 证据 |
|---|---|---|
| `app/agents/manifest_router.py` | 109 行 | 全库零消费者 |
| `app/utils/latex_engine.py` | 346 行 | 生产零引用（仅单测引用；实际走 latex_export.py） |
| `app/services/chart.py` | 705 行 | 唯一引用是 services/__init__ re-export；图表实际由 FigureTools 实现 |
| `app/skills/` 整目录 | 12 目录 | 零 Python 引用 |
| `BaseAgent._validate_tools` | base.py:49 | 零调用——工具声明错误只能运行期暴露 |
| 根目录 `main.py` | 8 行 | Hello-World 脚手架，与 app/main.py 冲突 |

另有行为不一致：`literature/agent.py:353-439` 直调 `self.tools_handler._tool_*` 私有方法，绕过 base 的 `use_tool` 分发，工具抽象形同虚设。

---

## 3. 安全与配置审计

### 3.1 🔴 任意文件读取（已实证）

`app/main.py:328-346` 的 SPA 兜底路由把用户路径直接拼接：

```python
file_path = FRONTEND_DIR / full_path
if full_path and file_path.is_file():
    return FileResponse(str(file_path))
```

`StaticFiles` 自带穿越防护，但这里绕过了它。实测（本机起服务，原始 socket 发送）：

```
GET /..%2F..%2F.env  →  HTTP/1.1 200 OK  + .env 全文
GET /%2e%2e/%2e%2e/.env  →  HTTP/1.1 200 OK  + .env 全文
```

当前 `.env` 的 OPENAI_API_KEY 恰为空所以未泄真实密钥，但该漏洞可读**进程可读的任意文件**（源码、日志、数据库、`/etc/passwd` 类目标在 Linux 部署下同样成立）。nginx 在前也未必挡（`..%2F` 编码代理常直接透传）。

**修法（3 行）**：

```python
file_path = (FRONTEND_DIR / full_path).resolve()
if full_path and file_path.is_file() and file_path.is_relative_to(FRONTEND_DIR.resolve()):
    return FileResponse(str(file_path))
```

并加一条 `GET /..%2f..%2f.env 必须 404/200-index.html` 的回归测试。

### 3.2 🔴 三组路由零鉴权

- `app/api/v1/ascend.py` 4 端点全裸奔：`PUT /ascend/mode`（:131-161）**任何人可切换全局 LLM_MODE 并清空缓存**（成本/可用性攻击）；`POST /ascend/warmup`（:94）未认证触发真实推理；`GET /ascend/info` 泄露内网 base_url、模型名、CANN/torch 版本。
- `app/api/v1/adaptation.py` 17 端点全裸奔（:139-402），接受任意本地路径 `model_path` 等；路径校验只有 `_validate_path_safety`（`core/profiling.py:34-44`）——仅挡 shell 元字符，不挡绝对路径与 `..`。
- `app/api/v1/alignment.py` 5 端点全裸奔（:41-185）。

对照组：debugging/perf_tuning/history_to_skill/profiling/toolchain/validator 六个路由都正确使用了 `APIRouter(dependencies=[Depends(get_current_user)])`。**修法**：照抄该模式给三个文件补上；更稳妥的做法是在 `app/api/v1/__init__.py:17` 聚合层加默认鉴权 + 显式豁免名单（login/register/refresh/health 等），把 E1 透传测试扩展到 ascend 域。

### 3.3 🔴 部署链路泄密面

- `.dockerignore` 无 `.env` 条目 + `Dockerfile.ascend:36` `COPY . .` → **两个 env 文件烘焙进镜像**。修法：`.dockerignore` 加 `.env*`。
- `docker-compose.yml:19` `SECRET_KEY=${SECRET_KEY:-change-this-in-production}` —— 25 字符弱默认值**恰好绕过** `config.py:161-166` 的前缀/长度校验（校验只查 `"your-secret-key"` 前缀）。修法：删默认值，缺失即启动失败；校验增加常见弱值黑名单。
- `.gitignore:36` 只有 `.env`，不匹配 `.env.ascend`（含 SECRET_KEY）。修法：改 `.env*`。
- 端口直接映射宿主：postgres `postgres:postgres` 弱口令（:60-65）、redis 无密码 6379（:80-81）、milvus 19530、vLLM 8001/8002 无认证（ascend compose :17-18,:52-53）。修法：绑定 127.0.0.1 或走内部网络不映射。
- `k8s/` 目录是空的——无任何清单。
- `.env.ascend:78` `CORS_ORIGINS=["*"]` + `DEBUG=false`，与 `allow_credentials=True`（main.py:216）组合是高危；且会撞 `config.py:179-182` 的启动校验（要么起不来，要么诱导删校验）。修法：显式列出域名。

### 3.4 🟠 SSRF 绕过

正规入口 `PUT /auth/api-config`（auth.py:541）和 `POST /test-api-config`（:573）都过 `_validate_api_base_url`（:34-99，拒私网/环回/169.254.169.254），但 `PATCH /auth/me`（:377-382）可直接写 `api_base_url` 不过校验；写入后 `utils/llm.py:54-75,319-321` 在实际调用时**不做任何地址校验**。修法：PATCH /me 对 api_base_url 复用同一校验函数。

### 3.5 🟠 限流与 WebSocket

- 双后端限流实现本身正确（内存滑窗 `rate_limit.py:43-106`、Redis ZSET+Lua :112-195），但 `check_rate_limit_middleware`（:268-289）**零引用**——全 app 只有登录（auth.py:126）和忘记密码（:456）两处限流，所有 LLM 生成端点裸奔，套餐限流表 RATE_LIMITS（:255-260）形同虚设。`RATE_LIMIT_FALLBACK` 默认 `allow`（config.py:42），Redis 故障全放行。修法：中间件接入全局（豁免静态/健康检查），fallback 评估改 deny。
- WebSocket（`api/v1/ws.py:22`）：JWT 走 URL query（会进代理/访问日志）；:41 `event_bus.subscribe(task_id)` 不校验任务归属——任意已登录用户可订阅任意任务事件流。修法：token 改首条消息认证；订阅前查任务 user_id。

### 3.6 🟡 其余安全观察

- 密钥现状：`.env`/`.env.ascend` 中 **OPENAI_API_KEY 均为空、无真实第三方密钥**；SECRET_KEY 是弱开发值；`.env:1` DEBUG=true（docs 开、500 回显异常详情）——**当前状态不可用于生产**。
- nginx：无安全头（XFO/XCTO/CSP/HSTS），HTTPS 块被注释（nginx.conf:75-85），`client_max_body_size 50M`（:28）与应用层 2MB（main.py:272-289）不一致，`/api/` 代理缺 WebSocket Upgrade 头（:53-66）。
- `logs/app.log`（1.8MB）无 JWT/密钥，但含**真实用户邮箱 PII**（38 次）；debug_sessions/ 无凭据。修法：日志脱敏 + 清理。
- 加分项：JWT 双 token 防互换（security.py:71-118）、bcrypt+SHA256 预哈希防 72 字节截断（:11-33）、登录 IP 限流+账号锁定（auth.py:121-168）、`validate_security()` 启动校验（config.py:159-190）、请求体 413 中间件、SQL 注入面干净（唯一 raw SQL 是常量 `SELECT 1`）。

---

## 4. 代码质量

### 4.1 后端

- **类型债**：pyproject 声明 `strict = true` 但 1198 错误。建议改「strict-lite」起步：先修 `import-not-found`（26 个，可能有真坏 import）和 `arg-type/assignment`（195 个，真类型错），`no-untyped-def` 按新代码先行、存量渐进。CI 里跑 mypy 但只对新文件 strict（`--strict` per-module 或 `mypy --untyped-calls-exclude`）。
- **入口小瑕疵**：main.py:58/69 重复 import AscendNPUManager；main.py:414/419 health 字典类型不一致（mypy 实报）。
- **TODO 密度极低**：全 app 仅 6 处真实标记，其中 `core/adaptation.py:1040-1125` 4 个 TODO 说明 1700 行模块是半成品（权重加载/前向推理/vllm 注册/Triton 算子未实现）。
- **测试**：329 全过但结构失衡（§1）；建议：ascend 域补鉴权透传用例；把空 e2e/ 目录要么填最小冒烟（起 app→/health→登录→一个 agent 调用）要么删掉目录。

### 4.2 前端

- **基础卫生优秀**：`: any` = 0（仅 2 处 `as any` 集中在一个组件）、console.log = 0、36 页面全部 React.lazy 分包、token 存 sessionStorage+内存双存并自动迁移旧 localStorage、401 自动 refresh 重试（api.ts:159-171）、71 个手写 interface 与后端抽查对齐。
- **Tailwind 设计系统死配置（🟡）**：Tailwind 3.4 按固定顺序找配置，空壳 `tailwind.config.js` 抢在 160 行的 `.ts` 前加载（`node_modules/tailwindcss/lib/util/resolveConfigPath.js:24-31`）。实证：今日构建的 `dist/assets/*.css` 中无 `#2563EB`（.ts 主色）、`.font-serif` 是默认栈而非 Noto Serif SC、不存在 `.text-copper{}`；而 src 里 `text-copper` 用了 164 次、`font-serif/bg-ink-dark` 310 次——**全是无样式输出的幽灵类**，真实视觉全靠 index.css 的 CSS 变量（暖金 #C9A961）撑着，且两套主题色互相矛盾（.ts 的蓝 vs index.css 的金）。修法：删 `tailwind.config.js`，并决策到底用哪套色板。
- **vite.config.js 抢先于 .ts**：Vite 的 DEFAULT_CONFIG_FILES 把 `.js` 排前（`node_modules/vite/dist/node/constants.js`），dev 时编辑 `.ts` 不生效。根因：`tsconfig.node.json` 有 `composite: true` 却没 `noEmit: true`，`tsc -b` 把 .ts 编译输出到根目录（连带产出 vite.config.d.ts 和两个 tsbuildinfo）。修法：加 noEmit、删生成物。
- **PWA 图标全 404**：`public/` 0 个文件，manifest 引 3 个 PNG + favicon.svg 全部不存在（vite.config.ts:70-72）。
- **遗留 Alpine.js 一代前端整链未删（~420KB 僵尸）**：`index_legacy.html`（296KB）+ `js/app.js`（108KB，含 11 处 console + localStorage 明文 token）+ `css/` + 根目录游离 `pages/Response.tsx`（与 src 内版本分叉：296 vs 210 行，App.tsx:39 实际用 src 版）+ 0 字节垃圾文件 `'`。
- **react-query 名存实用**：全局 QueryClient 配置了（App.tsx:10-19），但只有 `hooks/useLibrary.ts` 一个文件用 useQuery；其余 26 页手写 useState/useEffect，`ascend/Validator.tsx` 单文件 42 处 useState/useEffect。巨型组件 8 个 500+ 行（最大 Adaptation.tsx 747）。
- **死依赖**：`@capacitor/cli+core`（^8.4.0）在 dependencies 且 src 零 import、无 capacitor.config——全家桶白拖进 node_modules。
- **71 手写 interface vs 后端 193 个 pydantic BaseModel**：无 codegen，人肉维持漂移。建议引入 openapi-typescript 从 /openapi.json 生成。

---

## 5. 昇腾 NPU 子系统

### 5.1 一致性核对

六份配置（Dockerfile.ascend / compose.ascend / .env.ascend / ASCEND_README / config.py / ascend-skills-workflow.md）的模型名、端口、LLM_MODE **基本对齐**（Qwen2.5-72B-Instruct TP=4、bge-large-zh-v1.5、8001/8002），仅 CANN 版本文档间小分歧（≥8.0 vs ≥8.2）。

### 5.2 实际问题（按严重度）

1. 🔴 **requirements.ascend.txt 缺 alembic（也缺 email-validator、python-dotenv）**：`app/main.py:34` 启动无条件 `from alembic import command` → 容器启动即 ImportError。修法：补齐三个包，或与主 requirements.txt 合并出一份 base+ascend 分层依赖。
2. 🟠 **`asyncio` 被当 PyPI 包安装**（requirements.ascend.txt:15）：PyPI 上的 asyncio 是停滞 dummy 包，可能遮蔽标准库。删。
3. 🟠 **vLLM 模型注册名不匹配风险**：compose `vllm serve /models/Qwen2.5-72B-Instruct` 未加 `--served-model-name`，vLLM 按路径名注册，客户端请求 `Qwen/Qwen2.5-72B-Instruct` 对不上；embedding 同理。修法：serve 命令加 `--served-model-name`。
4. 🟡 Dockerfile.ascend 注释要求基础镜像含 CANN，实际 FROM python:3.10-slim 且不装 torch_npu——对 ascend_api（纯 HTTP）够用，ascend_local embedding 在该容器必挂。
5. 🟡 vllm 容器 healthcheck 依赖 curl（镜像不一定带）；两份 requirements 已漂移。

### 5.3 架构健康度

架构层面是全项目**最干净**的子系统：9 个路由在 `ascend_domain/__init__.py` 单点聚合（一行即可整体摘除）；8 个 core 模块零 app 依赖（torch/npu import 全在生成的脚本模板字符串内，模块本体是命令生成器+会话编排器）；CLI（scripts/）与 API 双入口；docs/ 有 7 份 quick_reference。工程层面带病：**约 9,600 行只有 6 个单测**（toolchain/validator 命令转义 3 个 + history_to_skill 路径 3 个），adaptation/perf_tuning/profiling/debugging/ascend 客户端零测试；3/9 路由裸奔（§3.2）。

**结论：修复 §5.2 前不建议按现有 Dockerfile.ascend 部署。**

---

## 6. 文档与遗留物处置

**真相澄清**：`_notes_part1/2/3.py` + `_apply_notes.py` 是往**外部技能库** `C:\Users\yangy\.atomcode\skills` 的 152 个 SKILL.md 插入中文备注的一次性补丁，**已应用完毕**（实测 152/152 含「备注:」行），与本项目无关，可删。

### 处置清单

| 动作 | 路径 | 说明 |
|---|---|---|
| **删除** | `_notes_part1/2/3.py`、`_apply_notes.py`、`_tmp_*`、`_skills_*`、`skill_meta.tsv` | 外部技能库操作的一次性产物 |
| **删除** | `nul`、`.e501.txt`、根 `main.py`、根 `__pycache__/` | 误建文件 / lint 输出 / 脚手架 |
| **删除** | `debug_sessions/`、`.pwtest/`、`.arts/`、`.atomcode/`（21MB）、`.codeartsdoer/` | 调试外部工具的产物、AI 工具缓存 |
| **归档后删** | `skills_dedupe_report.md` → `.atomcode` 或 docs/history | 外部库去重记录（228→152） |
| **归档后删** | `pw_*.md`（6 份）→ docs/references/ | 外部项目 awesome-llm-paper-wiki 的平铺拷贝，内链已断 |
| **归档后删** | `.workbuddy/memory/` → docs/history | ruff 2176→506 修复史，有历史价值 |
| **移出/归档** | `nature-skills/`（内含嵌套 .git）、`design-reference/` | 第三方 git clone、设计手册，勿入库 |
| **并入 docs/** | `.docs/`（route-analysis.md、frontend-defects.md、optimization-plan.md） | **与本项目直接相关的分析文档**，藏在隐藏目录里 |
| **保留本地勿入库** | `research_agent.db`、`logs/`、`.idea/`、`uploads/`、`reports/` | 运行时数据/日志/IDE；reports/ 被 alignment 路由读写 |
| 按需 | `.claude/` | Claude Code 权限白名单，在用则留 |
| **前端侧同步删** | `index_legacy.html`、`js/`、`css/`、根 `pages/Response.tsx`、`'` 垃圾文件、dist/、*.tsbuildinfo、vite.config.{js,d.ts}、tailwind.config.js、vite*.log | 见 §4.2 |

**文档体系本身**：README.md（30KB）与实际功能基本相符但含大量 ✅ 宣传性内容；`ascend-skills-workflow.md`（22KB）与 ASCEND_README.md 有内容重叠；建议 README 瘦身为快速上手 + 指向 docs/。

---

## 7. 修复路线图

### P0（立即，半天内）

1. `app/main.py:342` 路径穿越：resolve + is_relative_to 三行修复 + 回归测试。
2. ascend/adaptation/alignment 三路由补 `dependencies=[Depends(get_current_user)]`。
3. `.dockerignore` 加 `.env*`；`.gitignore` 改 `.env*`；`.env.ascend` 修 CORS 通配。
4. requirements.ascend.txt 补 alembic/email-validator/python-dotenv，删 asyncio 行。
5. **`git init` + 提交基线**（先做 §6 清理再提交，避免 21MB 缓存进历史）。

### P1（一周内）

6. PATCH /auth/me 补 SSRF 校验；限流中间件接线 + fallback 策略评估。
7. Coordinator 三处路由脱节修复（figure/data_agent/statement）+ 一致性断言测试。
8. compose 删 SECRET_KEY 弱默认；数据库/Redis/Milvus/vLLM 端口收回内网。
9. Alembic 补唯一约束迁移；生产 MIGRATION_ON_STARTUP=true、去 create_all 兜底。
10. vLLM serve 加 --served-model-name；删 tailwind.config.js / vite.config.js（tsconfig.node.json 加 noEmit）。

### P2（一个月内）

11. 遗留物清理（§6 全表）+ git 基线后的 .gitignore 完善（debug_sessions、.pwtest、pw_* 等）。
12. 死代码删除：chart.py、latex_engine.py、manifest_router.py、app/skills/、BaseAgent._validate_tools 接线或删。
13. mypy 渐进：先修 import-not-found 与 arg-type/assignment；新文件强制 strict。
14. 前端：PWA 图标补齐、Alpine 遗留链删除、react-query 推广到高频页面、openapi-typescript 生成 types.ts。
15. 昇腾子系统补测试（adaption/profiling/debugging 优先）；ascend 域鉴权透传测试。
16. nginx 安全头 + HTTPS + body 大小对齐；日志 PII 脱敏。

### P3（观察）

- agent_generator 运行期写 .py 的长期去留（建议改为生成到 sandbox 目录 + 人工审阅 + git 提交）。
- EncryptedString 无密钥退化明文的行为是否可接受。
- 三套 agent 实例化模式收敛。

---

*报告由 ZCode 生成；四路并行探索 + 工具链实测 + 漏洞 PoC 全部证据可在对话记录中复核。*

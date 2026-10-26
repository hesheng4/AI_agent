# 优化与扩展第二轮报告（credibility-convergence 执行轮）

> 2026-10-26。本轮在 credibility-convergence-v1 契约框架内执行：批次一类型债清偿 +
> 批次二人工 triage（真缺陷修复）+ 契约步骤 6/7 扩展（agent_artifacts、share/fork）。
> 所有数字均为当次运行输出，不是引用文档。

---

## 0. 实测基线（本轮开始时）

| 项 | 实测 | 判定 |
|---|---|---|
| pytest | **545 passed, 1 skipped, 28.28s** | 与契约 G3 一致 |
| ruff `app` | **0 error** | G2 保持 |
| mypy `app` | **890 errors in 112 files (checked 146)** | 与基线一致，批次一开始 |
| 前端 tsc | 通过（改动前基线） | — |

---

## 1. 全面分析发现（两个并行分析代理 + 人工复核）

### 1.1 测试覆盖（前端/测试代理）

- **17 个 API 路由模块零 HTTP 层测试**（literature/library/writing/experiment/export/data/agents/ws 等，共 100+ 端点），零覆盖恰好集中在「LLM 生成 + 文件上传/导出」高危面。
- `tests/integration/api/` 是空目录；`tests/alignment/` 只有夹具数据，名不副实。
- agent 单测统一 mock `call_llm` 恒返回成功字符串，**LLM 失败/解析损坏路径无单测**（本轮 LLM 异常穿透缺陷即源于此类盲区）。
- 正面：两个 golden 测试（数值/引用网络）断言质量教科书级；e2e 真实 ASGI + 临时 sqlite 零 mock。

### 1.2 安全与健壮性（后端代理 + 人工复核）

| # | 发现 | 级别 | 状态 |
|---|---|---|---|
| S1 | `ws.py` 认证后不校验 task_id 归属 → 任何登录用户可订阅任意任务事件（跨用户进度泄露 IDOR） | P1 | ✅ 已修（event_bus 归属登记 + 4003） |
| S2 | `main.py` body 限制只查 Content-Length，chunked 传输完整绕过 2MB 上限 | P1 | ✅ 已修（411） |
| S3 | billing 配额无强制力：`check_quota` 从未接入生成端点，超套餐仍可无限调用 | P1 | ✅ 已修（research 域依赖接入） |
| S4 | `agents.py`（LLM 代码生成）挂 platform 域绕过套餐限流 | P1 | ✅ 已修（显式挂 enforce_api_rate_limit） |
| S5 | 缓存/限流后端拼写错误静默回退 memory，多实例下限流分裂 | P1 | ✅ 已修（config 白名单校验 fail-fast） |
| S6 | `X-Request-ID` 客户端可控字符串直接进日志（注入面） | P2 | ✅ 已修（截断+白名单） |
| S7 | `RATE_LIMIT_FALLBACK` 默认 allow，Redis 故障时限流失效 | P1（待议） | ⏸ 保留默认但已加白名单校验 |
| S8 | DEBUG 下用户 API Key 明文落库（EncryptedString 仅警告） | P2 | ⏸ 开发期已知权衡 |
| S9 | `/health` 无鉴权暴露拓扑 + 实时探测可被放大 | P2 | ⏸ 后续批次 |
| S10 | PWA 把 `/api/v1/*` 认证 GET 响应落盘缓存（共享机器隐私泄露面） | P2 | ✅ 已修（NetworkOnly） |

### 1.3 功能性缺陷（批次二 triage 实锤）

| # | 缺陷 | 影响 | 状态 |
|---|---|---|---|
| B1 | `LibraryService._adjust_usage` 首次使用标签自动建行 `usage_count=0`，首个引用文献永远少计 1 | 标签计数系统性失真（fork 黄金测试暴露） | ✅ 已修+回归 |
| B2 | `BaseAgent.call_llm/call_llm_stream` 把 `LLMTimeoutException/LLMRateLimitException` 重包成通用 `AgentException` → `classify_failure` 永远判 unknown → **E6 自动重试对 LLM 超时/限流永久失明** | workflow-error-recovery 的 transient 语义被破坏 | ✅ 已修+回归 |
| B3 | `use_tool` 无单工具超时，外部工具挂起时直连 agent 调用无限阻塞 | P1 | ✅ 已修（AGENT_TOOL_TIMEOUT=300s） |
| B4 | `llm.py` 用户客户端缓存满时无锁整体 clear 且不 close → httpx 连接池泄漏 | P1 | ✅ 已修（LRU 逐出+异步关闭） |
| B5 | 前端 `api.ts` 并发 401 各自触发 refresh，token 轮换竞态可致意外登出 | P1 | ✅ 已修（single-flight） |
| B6 | 前端 `isTokenExpired` 对无 exp 的 token 返回 false（视为永不过期） | P2 | ✅ 已修 |
| B7 | 注册流程不创建 UserAccount → `check_quota` 对全部存量用户返回 "not found" | 配额失效的根因之一 | ✅ 已修（依赖层懒创建） |
| B8 | `toolchain.py:439` `"# 验证 NPU 可见性\n"("python -c ...")` 字符串被当函数调用 → **运行到 `get_vllm_install_guide` 必抛 TypeError**（切片 4 代理发现） | 昇腾安装指南功能整体不可用 | ✅ 已修+回归 |
| B9 | `profiling.py stop_profiling` 无平台守卫：`os.getpgid/os.killpg/SIGKILL` 是 POSIX-only，Windows 下 AttributeError 且未被捕获 | Windows 终止采集任务必崩 | ✅ 已修（nt 分支 terminate/kill） |
| B10 | `core/runs.py find_run_any_user` 跨用户读取入口留存，全仓无调用方 | 越权读取隐患 | ✅ 已移除+注释 |
| B11 | `models/library.py` `Column(JSON, default=[])` 共享可变默认对象，就地 mutate 跨行串数据 | P2 | ✅ 已修（default=list） |
| B12 | e2e 全量运行 40+ 次登录触发 IP 级登录限流（20/分钟），排后用例 429 | 测试套件顺序依赖 | ✅ 已修（conftest autouse 重置限流器） |

### 1.4 架构与质量债（记录，后续批次）

- 17 个零覆盖路由模块（见 1.1）——建议按域补 HTTP 层冒烟。
- `nature_citation.py` 2265 行 / `adaptation.py` 1700 行等巨型文件待拆分。
- `Column(JSON, default=[])` 共享可变默认对象（`models/library.py:27/36`）——就地 mutate 会跨行串数据，应 `default=list`。
- `core/runs.py:258` `find_run_any_user` 越权读取入口留存（注释称 API 不得使用）。
- `cached()` 装饰器全仓无调用方，key 不含用户身份，属带风险死代码。
- react-query 全局配置但 0 页面使用，全部手写 useState 状态机。
- 前端零测试零 lint。

---

## 2. 本轮优化实施数果

### 2.1 批次一类型债清偿

| 切片 | 范围 | 起始 → 最终 | 执行方 | 状态 |
|---|---|---|---|---|
| 1 | app/agents/** | **198 → 41**（5 个目标错误码清零） | 代理 | ✅ |
| 2 | app/api/deps + api/v1 A 组 24 文件 | **205 → 86**（余为 Column 类型，待 Mapped 转换） | 主代理自做 | ✅ |
| 3 | api/v1 B 组 11 文件 | **167 → 8** | 代理 | ✅ |
| 4 | app/core/** | **159 → 21**（余为 POSIX-only API/Any 边界） | 代理 | ✅ |
| 5 | services/models/utils/main | **337 → 62**（切片内） | 代理 | ✅ |

- 门禁：每切片 pytest 全绿 + mypy 单调不增，ruff 保持 0。
- 切片 4 附带发现：`toolchain.py` 安装指南字符串误当函数调用（运行时必崩，见 B8）、
  `profiling.py build_profiler_kwargs` 声明返回 dict 实返二元组（已纠正注解）。

### 2.2 批次二真缺陷修复（上表 B1–B12、S1–S6、S10）

**User 模型 Mapped[] 转换**（批次二最大单项）：user/billing/library/artifacts/shares 五个
模型文件由 legacy Column 迁移为 SQLAlchemy 2.0 `Mapped[]`/`mapped_column`（列定义等价），
一次性清偿 52+ 条 Column 连带错误，并让 5 处**属性访问错误暴露为真问题**（复用 `result`
变量被 mypy 按首次绑定定型——已用独立变量名修复；`Result.rowcount` 按 `CursorResult` cast）。

每项修复均带回归测试：

- `tests/unit/test_agent_llm_exception_passthrough.py`（B2，4 用例）
- `tests/unit/test_event_bus_ownership.py`（S1，5 用例）
- `tests/unit/test_security_s2_body_limit.py` 补 chunked→411（S2，2 用例）
- `tests/e2e/test_billing_quota_enforcement.py`（S3/B7，2 用例）
- fork 黄金测试（B1 的计数回归锁定）

### 2.3 扩展（契约步骤 6/7，全部新文件 + 2 处最小接线）

**agent_artifacts 结果持久化**（G7 门禁达成）：
- 表 `agent_artifacts`（payload JSON + `(user_id, agent, created_at)` 复合索引）
- `app/services/artifact_service.py`（CRUD，严格 user_id 隔离）
- `app/api/v1/artifacts.py`（创建→列表→按 agent 筛选→重新导出→删除）
- Alembic 迁移 `e8a4f2c6b9d1`；e2e 全链路 3 用例

**share_links + fork 深拷贝**（G8 门禁达成）：
- 表 `share_links`（通用 `(resource_type, resource_id)`；sha256 token 哈希，明文只返回一次；TTL 7 天可空；显式撤销）
- `app/services/share_service.py`：fork 按契约决策 #8——分类/标签按名字重建、文献逐条 `add_paper`（计数同步内建）、笔记随文献、引用按 paper_id 映射重连
- 期间修掉 SQLAlchemy async 经典坑：commit 后 ORM 属性过期触发同步 IO（MissingGreenlet）——fork 前先捕获标量
- e2e 黄金断言：fork 后接收方文献/分类/标签/笔记/引用/usage_count/paper_count 与原库**逐一相等**，且 fork 可独立演化

### 2.4 门禁状态（最终实测 2026-10-26）

| 门禁 | 状态 |
|---|---|
| ruff `app` | **0** ✅ |
| pytest | **567 passed, 1 skipped**（基线 545 + 新增 22 用例；unit+integration+e2e 同进程全绿） |
| mypy | **890 → 58**（-93.5%），基线已重生成，`--check` 门禁通过（单调不增） |
| G7 artifacts | ✅ e2e 全链路（创建→列表→筛选→重新导出→删除→隔离→401） |
| G8 share/fork | ✅ 黄金计数全等（文献/分类/标签/笔记/引用/usage_count/paper_count 逐一相等） |
| G4 | ✅ 基线 890 → 58 单调不增 |
| G5 | ✅ README/pyproject 数字更新为当次实测 |

**测试污染修复**（批次二附带）：`test_audit_all_singleton_factories_idempotent` 的
`factory.cache_clear()` 会清掉路由模块 import 期捕获的协调器单例 → HTTP e2e 打桩全部
落空（假失败根因）。已移除 cache_clear，并把两个 HTTP e2e 测试改为对
`app.api.v1.coordinator._agent` 打桩；conftest 增加 autouse 限流器重置夹具。

---

## 3. 剩余建议（按优先级）

1. **完成切片 3/4/5**（mypy → ~300），随后做 User 模型 `Mapped[]` 转换清偿剩余 Column 类错误（预计 -80 条）。
2. **17 个零覆盖路由补 HTTP 冒烟**：优先 literature/library/writing/export/data（LLM 域 + 文件路径）。
3. **Rate limit fallback 决策**：多实例生产建议 `RATE_LIMIT_FALLBACK=deny` + 告警。
4. **巨型文件拆分**：library_service 已是 6 子服务门面，拆包成本最低。
5. **前端**：react-query 落地或移除配置；vitest 引入；`@capacitor` 死依赖移除；PWA 不缓存认证 GET。
6. **`Column(JSON, default=[])` → `default=list`**（一行级修复，防跨行串数据）。
7. 删除 `find_run_any_user` 或加调用方断言。

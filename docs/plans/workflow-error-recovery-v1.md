# 工作流错误恢复 v1 设计契约

> 2026-09-05 grill 会话产物。逐项决策均已确认；"未问而采用的默认"一节为设计者代答默认值，可否决。
> 背景：c6378b6 已落地模板编排 fail-fast 失败语义（停止执行的另一半）；本设计补齐恢复的另一半——失败之后发生什么。

## v2 落地记录（2026-09-05）

在 v1 全量落地（checkpoint + 手动 resume + 步级超时 + 分类器）之后，按
决策 #6/#7 预留的演进方向补齐两项：

1. **瞬态失败自动重试（opt-in）**：`AGENT_STEP_MAX_RETRIES`（默认 0）+
   `AGENT_STEP_RETRY_DELAY`（默认 5s）。仅 `transient` 类失败重试
   （限流/超时/步级超时），permanent/unknown 直抛；仅 checkpointed run
   （模板/自定义 DAG 路径）生效，ad-hoc 路径零变化。中间失败尝试即时
   落盘（`attempts` 累加 + 步骤条目 `attempt_errors` 证据链），重试期间
   崩溃留下的记录依然可 triage。默认 0 的理由：LLM 客户端请求级已有
   429/超时退避重试，步级仍瞬态失败多为持续故障窗口，且 fail-fast 是
   c6378b6 刚确立的显式语义——行为变更应 opt-in 而非静默。
2. **中断遗留 running 记录接管**：`RUN_STALE_AFTER`（默认 3600s，<=0 关闭）。
   resume 守卫允许接管超过该秒数无活动的 running 记录（进程崩溃孤儿，
   其中途步骤在记录里仍是 pending，compute_resume_sets 天然覆盖）；
   活跃 running（近期有步进）仍 409 防双跑。

明确推迟：run 记录迁 PostgreSQL（多 worker 部署出现前无收益；JSON 结构
即迁移契约）。

## 范围

仅覆盖两条编排路径：**模板驱动编排**（WORKFLOW_TEMPLATES）与**自定义 DAG 编排**（E5，经 `workflow_to_execution_plan` 编译）。
非模板 ad-hoc 多 Agent 路径保持 partial_failure 原语义，零改动（与全库零回归纪律一致）。

## 决策清单

| # | 决策点 | 结论 |
|---|--------|------|
| 1 | 恢复原语（根决策） | **checkpoint + 手动 resume**。失败即终止并落盘证据，由人判断后显式恢复。v1 无自动重试（LLM 调用昂贵且非确定；符合"停止执行线 + 保全证据"调试纪律）。 |
| 2 | 记录内容 | 每步存**全量结果载荷** + status + 失败错误证据 + 起止时间戳；run 级另存 plan 快照与冻结的原始请求。resume 注入已完成载荷作为上游上下文，只重执行失败步及其下游，不重复任何 LLM 工作。 |
| 3 | 存储介质 | `data/runs/` 下**每 run 一个 JSON 文件**，每次步进原子重写（tmp + `os.replace`，沿用 workflows 存储的 W5 模式）。无 alembic 迁移；代码注释已预留同一升级路径（生产可换 PostgreSQL JSONB）。单节点假设与 workflows 存储一致。 |
| 4 | 计划漂移 | run 记录存执行计划的**签名**（对有序 (agent, task) 序列取 sha256）。resume 时用当前模板/工作流重算签名，不匹配返回 **409**（"计划已变更，请发起新 run"）。拒绝混合两代计划的产出。 |
| 5 | Resume 契约 | 专用端点：`POST /api/v1/coordinator/runs/{run_id}/resume`、`GET /runs`（按用户过滤）、`GET /runs/{run_id}`。ownership 校验（记录含 user_id，复用 workflow 归属检查模式）；进程内守卫做 failed→running 状态迁移，并发二次 resume 返回 409。响应沿用 OrchestrateResponse 形状 + run_id。 |
| 6 | 失败分类 | **hint-only 分类器**：纯函数将异常类型/编码映射为 transient \| permanent \| unknown（LLM_RATE_LIMIT / LLM_TIMEOUT → transient；VALIDATION_ERROR → permanent；其余 unknown）。仅写入失败步记录并作为 triage 提示（"疑似瞬时故障，resume 大概率成功"），v1 不挂任何行为。未来自动重试接入同一信号。 |
| 7 | 步骤超时 | 每步用 `asyncio.wait_for` 包裹，`Settings.AGENT_STEP_TIMEOUT` 默认 **600s**。超时合成为 TimeoutError → 分类 transient → 正常 checkpoint 落盘。这是堵住"工作流永久卡死、无从恢复"唯一路径的前置条件。 |
| 8 | 调试子系统链接 | **可选链接，不自动建会话**：debug session 创建接受可选 run_id（CLI：`scripts/debug.py session create --from-run ID`；API 加字段），Phase-1 read-error 可从 run 记录注入。两子系统保持独立可测。 |
| 9 | 交付面 | 后端全契约 + **最小前端**：失败 run 展示失败步骤与错误 + Resume 按钮；runs 列表视图。不做时间线可视化/实时步进流（事件总线已有）。 |
| 10 | 保留策略 | **cap-on-write**：每次写 run 记录后裁剪该用户超出上限（Settings 字段，默认 50）的最旧记录。确定性、无调度器、刚创建的 run 永不被裁。 |
| 11 | 失败分类挂靠 | 依赖既有异常层级（`app/utils/exceptions.py`），无需新增异常类。 |

## 未问而采用的默认（可否决）

- **请求冻结**：resume 回放记录中冻结的原始请求；改输入 = 发起新 run（与决策 #4 同理，拒绝新旧代际混合）。
- **at-least-once 执行**：失败步重执行可能重复其崩溃前的部分副作用（如已写出的文件）；v1 不做 saga/回滚，文档明示该取舍。
- **run 状态机**：`running → succeeded | failed`；resume 仅允许 `failed → running`。
- **签名细节**：sha256 over 有序 (agent, task) 对列表；模板与自定义 DAG 同一算法。
- **LLM 客户端现状不动**：`app/utils/llm.py` 已有请求级重试（超时/429/5xx 退避重试），本设计只做步级超时，不重复该层。

## 测试矩阵

- **unit**：签名函数稳定性（同计划同签名）；分类器全映射表；run store CRUD + 原子写 + cap-on-write 裁剪；resume 规划（跳过已完成层、上游上下文注入正确）。
- **unit（coordinator 挂钩）**：fail-fast 失败步写入 run 记录；步级超时合成为 transient 失败并落盘。
- **integration/e2e**：3 步计划第 2 步注入失败 → orchestrate 返回 failed + run_id；resume 后仅执行 2–3 步（断言第 1 步 agent 未被再次调用）；计划变更后 resume → 409；并发二次 resume → 409；对 succeeded run resume → 409。
- **security**：用户 A 不能 resume 用户 B 的 run（对齐 W1/W2 纪律）。
- **regression**：非模板路径 partial_failure 语义不变；全量套件不低于 776 passed 基线。

## 建议实施顺序

1. run store（`data/runs/` + 原子写 + cap-on-write）+ 单测
2. coordinator 挂钩：执行期间逐级写记录，失败终止时落盘
3. 步级超时（`AGENT_STEP_TIMEOUT`）
4. hint-only 分类器
5. resume 执行路径（注入已完成结果、从失败层继续）+ 签名校验 + 并发守卫
6. runs API 三端点 + ownership
7. `scripts/debug.py --from-run` 链接
8. 最小前端（失败详情 + Resume 按钮 + runs 列表）
9. e2e + 回归验证（776 基线不降）

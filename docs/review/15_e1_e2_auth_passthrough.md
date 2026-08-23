# 15 Round 15 — E1/E2 端到端测试（鉴权 + coordinator 透传）

**执行日**: 2026-06-27
**触发**: Round 14 后用户 "go" → 按 Round 12 §6 优先级推进 B（E1/E2）
**范围**: API endpoint 鉴权回归 + coordinator `_user_api_*` 透传验证（CO6 闭环）

---

## 1. 执行结果

| 项 | 数值 |
|----|------|
| 新增测试文件 | `tests/integration/test_e1_e2_auth_passthrough.py` |
| 新增测试 | 21（18 E1 参数化 + 3 E2） |
| 回归 | 181/181 passed（160 unit + 21 integration，1.03s） |
| 临时脚本 | `_routes.py` 及 4 个 discovery 输出文件已清理 |

---

## 2. E1 — Endpoint 鉴权回归

**目标**: 验证受保护端点在无 token / 无效 token 时返回 401，不会因 200/422 泄露未授权访问。

**覆盖端点**（9 个，跨 6 个 router）:

| Method | Path（实际，含双重 prefix） |
|--------|------------------------------|
| POST | `/api/v1/coordinator/coordinator/route` |
| POST | `/api/v1/cover/cover/` |
| POST | `/api/v1/citation/add` |
| POST | `/api/v1/methods/methods/` |
| POST | `/api/v1/polishing/polishing/` |
| POST | `/api/v1/stats/stats/` |
| POST | `/api/v1/submission-package/submission-package/` |
| GET | `/api/v1/coordinator/coordinator/capability-map` |
| GET | `/api/v1/coordinator/coordinator/workflow-templates` |

**参数化**: 9 端点 × 2 场景（无 Authorization / Bearer 无效 token）= 18 测试，全过。

---

## 3. E2 — Coordinator `_user_api_*` 透传（CO6 闭环）

**目标**: 锁定 Round 12 §4 遗留的 CO6（coordinator 向子 agent 透传 `_user_api_*` 未端到端验证）。

**3 个测试**:

| 测试 | 路径 | 结果 |
|------|------|------|
| `test_e2_process_simple_forwards_user_api` | `process_simple`（单 agent，/route 端点用） | ✓ spy 收到 3 个 `_user_api_*` 字段 |
| `test_e2_process_parallel_forwards_user_api` | `process`（并行 plan，decompose_task） | ✓ 所有 spy 收到 3 个字段未失真 |
| `test_e2_process_simple_no_user_api_keys` | 缺省场景 | ✓ 无 KeyError，键缺省或 None |

**机制验证**:
- `decompose_task` (planner.py:146) — `"request": request` 同引用，`_user_api_*` 流入所有 subtask
- `_inject_upstream` (agent.py:139) — `dict(task.get("request") or {})` 复制保留 `_user_api_*`
- `_execute_single_task` (agent.py:209) — `agent.process(task["request"])` 透传

**结论**: CO6 闭环确认 ✓ — 凭据从 API 端点经 coordinator 双路径（单/并行）正确抵达子 agent `process()`。

---

## 4. 副产物发现

### 4.1 双重 prefix 路由（latent，未修）

OpenAPI schema 显示 6 个 agent 端点路径被双重 prefix：
- `/api/v1/cover/cover/`、`/api/v1/stats/stats/`、`/api/v1/methods/methods/` 等
- 原因：`api_router` 已带 `/api/v1` prefix，子 router 又各自带同名 prefix

**未修**: 功能正常（测试已验证鉴权），仅 URL 美观问题。列为 Q6 候选。

### 4.2 路由 introspection 脚本经验

`api_router.routes` 含 31 个 `_IncludedRouter` 包装对象，浅遍历看不到路径；需用 `app.openapi()["paths"]` 才能拿到完整路由表。后续若再做路由审计，直接用 OpenAPI schema。

---

## 5. 验证

| 检查 | 结果 |
|------|------|
| E1（18 参数化测试） | 全 18 passed |
| E2（3 透传测试） | 全 3 passed |
| 全回归 | 181 passed（1.03s） |
| 临时文件清理 | `_routes.py` + 4 输出文件已删 |

---

## 6. Round 12 遗留清单更新

| ID | 状态 |
|----|------|
| T1 temperature | ✅ R13 闭环 |
| T2 singleton | ✅ R13 闭环 |
| T3 ruff I001/F401 | ✅ R14 闭环 |
| E1 endpoint 鉴权测试 | ✅ 本轮闭环 |
| E2 coordinator 透传测试（CO6） | ✅ 本轮闭环 |
| T4 v2 agent 决策 | ⏳ **仍待用户裁定** |
| E3 frontend 审查 | ⏳ |
| S1-S6 安全审计遗留 | ⏳ |
| Q1-Q5 历史代码质量 | ⏳ |
| Q6（新增：双重 prefix） | ⏳ 低优先 |

---

## 7. 建议下一步

剩余高价值项已基本闭环。**T4 v2 agent 决策**是唯一阻塞后续清理的项 —— 需用户明确裁定：

- **citation_v2** — 删除 / 标注 experimental / 保留？
- **data_v2** — 删除 / 标注 experimental / 保留？
- **submission vs submission_package** — 合并 / 明确职责边界？

裁定后可一轮清理完毕。其余项（E3 frontend、S1-S6 安全、Q1-Q6 历史质量）均为低优先或需另开专题。

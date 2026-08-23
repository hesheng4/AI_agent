# 21 Round 21 — E3 frontend 审查 + Q6 double-prefix 同步修复

**执行日**: 2026-06-28
**触发**: 用户 "E3+q6" → 合并 frontend 审查与 double-prefix URL 契约变更
**方法**: 前后端 + 测试三方同步修改；用 E1 鉴权回归 + tsc 双重验证 URL 契约

---

## 1. 执行结果

| 项 | 数值 |
|----|------|
| 修改后端 | 6 sub-router 删 `prefix=`（cover/coordinator/methods/polishing/stats/submission_package） |
| 修改前端 | `frontend/src/api.ts` 6 处 URL 折叠（`/cover/cover/` → `/cover/` 等） |
| 修改测试 | `tests/integration/test_e1_e2_auth_passthrough.py` 9 端点元组同步 |
| E3 frontend 审查范围 | `src/api.ts` API 调用层（Q6 主体） |
| 全回归（后端） | 209/209 passed（1.64s） |
| tsc --noEmit（前端） | 零错误零警告 |
| 临时脚本 | 无（本轮无 inventory 脚本） |

---

## 2. Q6 根因与修复

**根因**: 6 个 sub-router 各自在文件内 `APIRouter(prefix="/X")`，同时 `api/v1/__init__.py:include_router(..., prefix="/X")` 又加同 prefix → 最终 `/api/v1/X/X/`。

**修复策略**: 删除 sub-router 内的 `prefix=`，保留 `__init__.py` 的 include_router prefix（后者是 URL 契约的单一来源）。

**6 受影响 router**:

| Router | 旧 URL | 新 URL |
|--------|--------|--------|
| cover | `/api/v1/cover/cover/` | `/api/v1/cover/` |
| coordinator | `/api/v1/coordinator/coordinator/route` 等 | `/api/v1/coordinator/route` 等 |
| methods | `/api/v1/methods/methods/` | `/api/v1/methods/` |
| polishing | `/api/v1/polishing/polishing/` | `/api/v1/polishing/` |
| stats | `/api/v1/stats/stats/` | `/api/v1/stats/` |
| submission_package | `/api/v1/submission-package/submission-package/` | `/api/v1/submission-package/` |

---

## 3. 三方同步修改（避免破坏 deployed 服务）

| 层 | 文件 | 改动 |
|----|------|------|
| 后端 | 6 × `app/api/v1/*.py` | `APIRouter(prefix="/X", ...)` → `APIRouter(...)` |
| 前端 | `frontend/src/api.ts` | 6 处 `*Api` 对象内 URL 折叠 |
| 测试 | `tests/integration/test_e1_e2_auth_passthrough.py` | `_AUTHED_ENDPOINTS` 9 元组同步 + 注释更新 |

**为何三方同步**: R19 文档已记录"Q6 是对外契约变更，无 frontend 协调下 unilateral 修改 = 破坏 deployed 服务"。本轮 E3+Q6 合并即兑现该协调 — 前后端 + 测试同改，URL 契约迁移 atomic。

---

## 4. E3 frontend 审查范围声明

本轮 E3 **仅覆盖 `src/api.ts` API 调用层**（Q6 主体所在）。完整 E3 frontend 审查应包括：

- `src/pages/*.tsx` 18 页面组件（业务逻辑、状态管理、错误处理）
- `src/components/*.tsx` 12 UI 组件（无障碍、性能、复用性）
- `src/auth.tsx`（token 管理、登录流）
- `src/types.ts`（与后端 schema 一致性）
- `tailwind.config.*` / `vite.config.*`（构建配置）

**本轮未覆盖的部分**列为 E3-续专题（见 §8 遗留）。本轮 E3 的价值是兑现 Q6 的跨端协调，而非 frontend 全审。

---

## 5. 验证

| 检查 | 方法 | 结果 |
|------|------|------|
| 后端 URL 契约 | E1 鉴权回归（9 端点 × 2 场景） | 18/18 passed — 新 URL 返回 401（非 404），证明路由解析正确 |
| 后端无回归 | 全回归 `pytest tests/unit/ tests/integration/` | 209 passed（1.64s） |
| R17 AST 证伪套件 | `test_audit_rigor.py` | 24 passed — 累积声明在 URL 契约变更后仍成立 |
| 前端类型检查 | `npx tsc --noEmit` | 零错误零警告 |
| doubled-URL 残留 | grep 全仓 | 仅 `docs/review/*.md` 历史文档（正确，不改历史） |

---

## 6. 累计最终状态（R12-R21）

| 轮 | 闭环 | 变化 |
|----|------|------|
| R12-R20 | 见 R20 doc | 76 修复，209 测试 |
| R21 | **Q6 double-prefix 同步修复（6 后端 + 6 前端 + 9 测试）** | +21 改动，0 测试新增 |

**累计**: 76 处代码修复 + 21 处 URL 契约迁移；209 测试；209/209 passed。

---

## 7. 遗留清单（R21 后）

| ID | 状态 |
|----|------|
| T1-T4 / E1-E2 / S1/S3 / Q3-Q5 / Q residual / Q6 | ✅ 闭环 |
| **E3 frontend 完整审查** | ⏳ 本轮仅覆盖 api.ts；18 页面 + 12 组件 + auth + types 未审 |
| Q1 E501（442 处） | ⏳ 退出机械可修 — 需 AST 分类器 + 专题人工 |
| S2 文件上传限制 | ⏳ 独立专题 |
| S4 cache key str | ⏳ 低优先 |

---

## 8. 本轮价值

1. **Q6 闭环**: 6 个 double-prefix URL 通过前后端 + 测试三方同步修改 atomic 迁移，无 deployed 服务破坏
2. **E1 回归兑现价值**: R15 投资的 E1 鉴权回归在本轮 URL 契约变更时立即捕获验证 — 18 测试确认新 URL 返回 401（非 404），证明路由解析正确而非假通过
3. **tsc 零错误**: 前端 URL 折叠未引入类型错误，API 调用层契约一致
4. **E3 范围诚实声明**: 本轮 E3 仅覆盖 api.ts（Q6 主体），不假装完成了 frontend 全审 — 18 页面 + 12 组件仍为专题

**Q6 已闭环**。剩余 E3-续、Q1、S2、S4 均为专题级或低优先。

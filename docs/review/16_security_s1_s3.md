# 16 Round 16 — S1/S3 安全审计遗留（JWT refresh + 密码复杂度）

**执行日**: 2026-06-27
**触发**: Round 15 后用户 "go" → 按 T4 → S → Q 顺序，T4 阻塞于用户裁定，推进 S
**范围**: S1/M2 JWT refresh token + S3/M4 密码复杂度

---

## 1. 执行结果

| 项 | 数值 |
|----|------|
| 修改文件 | 3（`config.py`, `core/security.py`, `api/v1/auth.py`） |
| 新增测试 | 18（`tests/unit/test_security_s1_s3.py`） |
| 全回归 | 199/199 passed（1.04s） |
| ruff（改动文件） | clean |
| 临时脚本 | `_smoke16.py` 已清理 |
| 过程中捕获 bug | 1（`create_access_token` 漏 import，测试即捕获） |

---

## 2. S1 — JWT refresh token（M2 闭环）

**前**: 仅 access token（30 分钟 exp），无 refresh机制 → 用户每 30 分钟需重新登录。

**后**:
- `config.py`: 新增 `REFRESH_TOKEN_EXPIRE_DAYS: int = 7`
- `core/security.py`: 新增 `create_refresh_token` / `decode_refresh_token`，与 access token 共用 SECRET_KEY 但通过 `type` 声明（`access`/`refresh`）严格区分
- `decode_access_token` 增强：拒绝 `type != "access"` 的令牌（防 refresh 被用作 access）
- `decode_refresh_token` 严格：拒绝 `type != "refresh"`
- `api/v1/auth.py`:
  - `TokenResponse` 新增 `refresh_token` 字段
  - `/login` 同时签发 access + refresh
  - 新增 `POST /auth/refresh` 端点：以 refresh 换新 access + 新 refresh；校验用户仍存在且 `is_active`

**验证**:
- 6 单元测试（type 声明、双向拒绝、garbage 拒绝）
- 2 集成测试（`/refresh` 正常换取 + access token 被拒）
- 1 集成测试（garbage token 被拒）

---

## 3. S3 — 密码复杂度（M4 闭环）

**前**: 仅 `min_length=8` 长度校验，无复杂度 → `"password"`、`"12345678"` 等弱口令可通过。

**后**:
- `core/security.py`: 新增 `validate_password_complexity(pw)` — 要求四类字符（小写/大写/数字/特殊）中至少出现 2 类
- `api/v1/auth.py`: 3 处调用 — `register`、`change_password`、`reset_password`，不达标返 400 + 中文提示

**验证**:
- 5 弱口令参数化测试（`password`/`12345678`/`abcdefgh`/`ABCDEFGH`/空串）均拒
- 4 强口令参数化测试（`Abcdef12`/`Passw0rd`/`Abcdef!2`/`aA1!`）均通过
- 1 非字符串测试（None）拒绝

---

## 4. 过程中捕获的 bug

`api/v1/auth.py` `/refresh` 端点首版引用 `create_access_token` 但未在 import 列表 — `NameError`。**集成测试 `test_s1_refresh_endpoint_issues_new_tokens` 即时捕获**（500 NameError），补 import 后通过。印证 E1/E2 端到端测试的价值。

---

## 5. S2/S4/S5/S6 状态（未修，已分析）

| ID | 状态 | 说明 |
|----|------|------|
| S2/M3 文件上传大小限制 | ⏳ 未修 | 无 `UploadFile` size 检查；需独立轮次（涉及多站点） |
| S4/P2 cache key object str | ⏳ 未修 | `str()` on custom objects → cache miss（非正确性 bug）；低优先 |
| S5/P5 ENTERPRISE 配额 | ✅ 已分析为预期 | `record_usage` 始终记录用量；ENTERPRISE 仅跳过配额门，用量仍累积供分析 — 设计如此 |
| S6/P7 token expiry 区分 | ✅ 由 S1 subsumed | access token 有 `exp`；引入 refresh 后两类 token 各自独立 exp，S6 自动满足 |

---

## 6. 验证

| 检查 | 结果 |
|------|------|
| S1/S3 单元测试 | 18/18 passed |
| 全回归 | 199 passed（1.04s） |
| ruff（改动 3 文件 I001/F401） | All checks passed |
| 临时脚本 | `_smoke16.py` 已删 |

---

## 7. Round 12 遗留清单更新

| ID | 状态 |
|----|------|
| T1/T2/T3 | ✅ R13-R14 闭环 |
| E1/E2 | ✅ R15 闭环 |
| S1/M2 JWT refresh | ✅ 本轮闭环 |
| S3/M4 密码复杂度 | ✅ 本轮闭环 |
| S5/P5 ENTERPRISE 配额 | ✅ 分析为预期行为 |
| S6/P7 token expiry | ✅ 由 S1 subsumed |
| T4 v2 agent 决策 | ⏳ **仍待用户裁定** |
| S2/M3 文件上传限制 | ⏳ 待独立轮次 |
| S4/P2 cache key str | ⏳ 低优先 |
| E3 frontend 审查 | ⏳ |
| Q1-Q6 历史代码质量 | ⏳ |

---

## 8. 建议下一步

剩余项均为 **T4 阻塞** 或 **低优先/独立专题**：

- **T4** v2 agent 去留 — 需用户明确意见（citation_v2 / data_v2 / submission vs submission_package）
- **S2** 文件上传限制 — 独立轮次（多 UploadFile 站点）
- **E3** frontend 审查 — 独立专题
- **Q1-Q6** 历史代码质量 — 低优先，可批 `ruff --fix` + 手工拆行

**本轮工作已收敛至 T4 阻塞点**。建议用户裁定 T4 以解锁后续清理，或明确选择停止/转专题。

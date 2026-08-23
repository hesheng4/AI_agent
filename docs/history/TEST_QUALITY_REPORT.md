# 测试质量与代码质量分析报告

> 分析时间：2026-06-19  
> 分析范围：测试覆盖率、代码质量工具、CI 配置

---

## 一、测试覆盖率分析

### 总体情况

| 指标 | 数值 |
|------|------|
| 测试用例总数 | 71 |
| 总体覆盖率 | **33%** |
| 测试文件数 | 约 8 个 |

**结论**：覆盖率偏低（目标应 ≥ 70%），大部分核心模块未覆盖。

---

### 零覆盖或低覆盖模块（按优先级排序）

#### P0 - 安全核心模块（必须测试）

| 模块 | 覆盖率 | 行数 | 风险 |
|------|--------|------|------|
| `app/core/security.py` | **38%** | 32行 | 密码哈希、JWT 生成若出错，全站认证失效 |
| `app/core/redis_client.py` | **0%** | 26行 | Redis 连接失败会导致缓存/限流失效 |
| `app/utils/llm.py` | **23%** | 133行 | LLM 调用失败会阻断核心功能 |

#### P1 - 复杂业务模块（建议测试）

| 模块 | 覆盖率 | 行数 |
|------|--------|------|
| `app/services/auth.py` | **36%** | 33行 |
| `app/core/database.py` | **43%** | 23行 |
| `app/core/rate_limit.py` | **51%** | 120行 |
| `app/core/cache.py` | **49%** | 182行 |
| `app/core/debugging.py` | **36%** | 444行 |

#### P2 - 工具/辅助模块（可选测试）

| 模块 | 覆盖率 | 行数 |
|------|--------|------|
| `app/services/statistics.py` | **10%** | 483行 |
| `app/services/reference.py` | **12%** | 317行 |
| `app/services/chart.py` | **15%** | 418行 |
| `app/core/alignment.py` | **0%** | 165行 |
| `app/core/ascend.py` | **0%** | 215行 |

---

### 空测试目录

以下目录存在但无测试文件，应补充或删除：

```
tests/e2e/              → 空（建议补充登录 E2E 测试）
tests/integration/      → 存在但 api/ 子目录为空
tests/performance/      → 空（可选）
```

---

## 二、测试优先级清单

### 第一批（安全核心）

1. `test_security.py` — 覆盖 `app/core/security.py`
   - `get_password_hash()` / `verify_password()`
   - `create_access_token()` / `decode_access_token()`
   - 边界：空密码、超长密码、错误密钥

2. `test_auth_service.py` — 覆盖 `app/services/auth.py`
   - `authenticate_user()` — 正确密码、错误密码、禁用用户
   - `create_user()` — 重复用户名、重复邮箱
   - `create_token()` — Token 内容正确性

3. `test_redis_client.py` — 覆盖 `app/core/redis_client.py`
   - `init_redis()` / `get_redis_client()` / `close_redis()`
   - 连接失败时的降级行为

---

### 第二批（API 层）

4. `test_api_v1_auth.py` — 覆盖 `app/api/v1/auth.py`
   - POST `/auth/login` — 成功/失败
   - POST `/auth/register` — 成功/重复
   - GET `/auth/me` — 有效 Token/无效 Token

5. `test_api_v1_library.py` — 覆盖文献库 API
   - CRUD 操作鉴权检查

---

### 第三批（复杂业务）

6. `test_citation_network.py` — 覆盖 `app/services/citation_network.py`
7. `test_library_service.py` — 覆盖 `app/services/library_service.py`
8. `test_chart_service.py` — 覆盖 `app/services/chart.py`

---

## 三、代码质量工具分析

### Ruff — 未安装

**现状**：`requirements.txt` 中将 `ruff` 注释在开发依赖中（第44行），当前环境中未安装。

**建议**：
```bash
pip install ruff
```

然后在 `pyproject.toml` 中配置：
```toml
[tool.ruff]
line-length = 120
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]
ignore = ["E501"]  # 允许长行，或设置更高限制
```

---

### MyPy — 未安装

**现状**：`requirements.txt` 第45行注释了 `mypy>=1.7.1`，未安装。

**建议**：
```bash
pip install mypy
```
然后逐步添加类型注解，从 `app/core/security.py` 和 `app/services/auth.py` 开始。

---

### pytest-cov — 已安装

**现状**：覆盖率测试可以运行，当前总体 33%。

**建议**：在 `pyproject.toml` 中设置覆盖率阈值：
```toml
[tool.coverage.report]
fail_under = 70
```

---

## 四、CI/CD 配置检查

### GitHub Actions — 未找到

**现状**：`.github/workflows/` 目录不存在。

**建议**：创建 `.github/workflows/ci.yml`：
```yaml
name: CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt && pip install pytest pytest-asyncio pytest-cov ruff mypy
      - run: ruff check app/
      - run: mypy app/
      - run: pytest --cov=app --cov-report=term-missing --cov-fail-under=70
```

---

## 五、总结与建议

| 项目 | 现状 | 目标 |
|------|------|------|
| 测试覆盖率 | 33% | ≥ 70% |
| 测试用例数 | 71 | ~200 |
| Ruff | 未安装 | 每次提交检查 |
| MyPy | 未安装 | 逐步启用 |
| CI | 未配置 | GitHub Actions |

**下一步行动**：
1. 补充 `test_security.py` 和 `test_auth_service.py`（P0）
2. 安装并配置 `ruff`（P1）
3. 创建 `.github/workflows/ci.yml`（P1）
4. 逐步提升覆盖率至 70%（持续）

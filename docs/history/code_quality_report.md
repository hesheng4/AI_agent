# 代码质量审查与修复报告

**日期**: 2026-06-19

---

## 一、代码风格工具修复

### 1. Ruff (`ruff check --fix`)
- **修复前**: 1438 个错误
- **修复后**: 443 个错误（自动修复 233 个，Black 修复部分行长度）
- **剩余分布**:
  | 错误类型 | 数量 | 说明 |
  |---------|------|------|
  | E501 行过长 | 330 | 超过 88 字符限制，多为中文字符串/URL |
  | N806 函数内非小写变量 | 77 | 如 Q1, IQR 等统计缩写 |
  | N816 全局作用域混合大小写 | 14 | |
  | F401 未使用导入 | 7 | |
  | F841 未使用变量 | 4 | |
  | 其他 | 11 | |

### 2. Black 格式化
- **格式化文件**: 103 个文件
- **未变更**: 127 个文件

### 3. Mypy 类型检查
- **发现约 400+ 个类型错误**，主要类别:
  - `no-untyped-def`: 函数缺少返回类型注解（最大类别）
  - `type-arg`: 泛型类型缺少类型参数
  - `assignment`: 类型不兼容赋值
  - `no-any-return`: 返回 Any 类型
  - `no-implicit-optional`: 隐式 Optional 默认值

---

## 二、测试审查发现的问题与修复

### 已修复的问题

| 文件 | 问题 | 修复 |
|------|------|------|
| `conftest.py:10-15` | `event_loop` fixture 使用已弃用的 session 级作用域 | 移除该 fixture（`asyncio_mode="auto"` 已在 pyproject.toml 中配置） |
| `conftest.py:32-47` | `sample_paper` fixture 从未被使用 | 移除死代码 |
| `test_billing.py:22` | `assert cost == 0.11` 浮点数精确相等比较 | 改用 `pytest.approx(0.11, rel=1e-9)` |
| `test_cache.py:41,76` | `time.sleep(1.1)` 导致测试不稳定 | 改用 `unittest.mock.patch("app.core.cache.datetime")` 模拟时间 |
| `test_billing.py` | 缺少边界测试 | 新增 `test_calculate_cost_zero` 和 `test_calculate_cost_large_numbers` |
| `test_cache.py` | 缺少覆盖写入测试 | 新增 `test_cache_overwrite` |

### 测试质量评估

| 文件 | 问题类型 | 严重程度 |
|------|---------|---------|
| `test_data.py:42` | `assert result["status"] == "success"` mock 使断言恒为真 | 中 |
| `test_experiment.py:186-198` | `assert result["sample_size_per_group"] > 50` 硬编码魔数 | 低 |
| `test_writing.py:85` | 引号格式化断言过于宽松 | 低 |
| `test_literature.py:86-87` | mock side_effect 假设固定 LLM 调用次数 | 中 |
| 所有 agent 测试 | call_llm mock 返回值与断言的 dict 结构不匹配 | 中 |

---

## 三、测试覆盖缺口分析

### 当前覆盖率
- **有测试的模块**: ~7 个
- **无测试的模块**: ~70 个
- **总体覆盖率**: ~9%

### 优先级：CRITICAL（核心逻辑，零测试，高 ROI）

| 模块 | 行数 | 说明 |
|------|------|------|
| `app/services/citation_network.py` | 909 | PageRank、共引分析、聚类算法 |
| `app/services/statistics.py` | 987 | 回归、ANOVA、生存分析 |
| `app/services/power_analysis.py` | 545 | 样本量计算、功效曲线 |
| `app/core/security.py` | 57 | 密码哈希、JWT（安全关键） |
| `app/services/reference.py` | 486 | 7 种引用格式生成 |
| `app/services/library_service.py` | 1036 | 跨 6 个子服务的状态同步 |

### 优先级：HIGH（大量逻辑，零测试）

| 模块 | 行数 | 说明 |
|------|------|------|
| `app/core/adaptation.py` | 1600+ | 10 步状态机、模型分析 |
| `app/core/debugging.py` | 1164 | 4 阶段调试框架 |
| `app/core/perf_tuning.py` | 1464 | 渐进式调优、瓶颈诊断 |
| `app/core/validator.py` | 1108 | 验证流水线 |
| `app/core/toolchain.py` | 954 | 硬件检测、脚本生成 |
| `app/core/profiling.py` | 863 | NPU Profiling |
| `app/core/history_to_skill.py` | 1265 | 历史搜索、技能生成 |

### 优先级：MEDIUM（工具和基础设施）

| 模块 | 说明 |
|------|------|
| `app/utils/latex_export.py` | LaTeX 导出格式正确性 |
| `app/utils/export.py` | CSV/JSON/MD 导出 |
| `app/utils/llm.py` | 重试逻辑、客户端缓存 |
| `app/utils/embedding.py` | Embedding 客户端 |
| `app/services/chart.py` | 13 种图表类型 |

### 无测试的 Agent 模块

- `app/agents/coordinator/agent.py` — 协调器
- `app/agents/coordinator/planner.py` — 任务分解
- `app/agents/response/agent.py` — 审稿回复
- `app/agents/reviewer/agent.py` — 模拟审稿
- `app/agents/citation/agent.py` — 引用代理
- `app/agents/data_agent/agent.py` — 数据可用性
- `app/agents/base.py` — 基础代理

### API 端点（全部 21 个文件零测试）

所有 `app/api/v1/*.py` 仅 `test_auth.py` 有 1 个健康检查测试，其余端点（注册、登录、文献检索、写作、实验、数据等）均无测试。

---

## 四、改进建议

1. **高 ROI 测试优先**: 先为 `statistics.py`、`citation_network.py`、`power_analysis.py` 编写单元测试（纯函数，易测试）
2. **安全关键测试**: `security.py` 的密码哈希和 JWT 验证
3. **API 集成测试**: 为关键端点（auth、literature、writing）添加集成测试
4. **消除 Flaky Tests**: 所有 `time.sleep` 替换为时间模拟
5. **Mypy 类型注解**: 逐步为 `app/core/` 和 `app/services/` 添加类型注解
6. **Ruff E501**: 考虑对中文字符串使用 `# noqa: E501` 或调整 `line-length`

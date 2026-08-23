# Data 系列审查报告(第 5 轮)

**审查日期**: 2026-06-27
**审查范围**: `app/agents/data/`、`app/agents/data_agent/`、`app/api/v1/data_availability.py`
**不在本轮**: `app/agents/data_v2/`(363 行,未暴露路由,留总审查与 data_agent 一并判定)
**基线测试**: data/ 11 → 11;data_agent/ 0 → 11;全量回归 123 → 134 passed

---

## 一、三目录关系判定(关键)

| 目录 | 类名 | API 路由 | 测试 | 用途 |
|------|------|---------|------|------|
| `data/` | `DataAgent` | ✓ `api/v1/data.py` 3 端点 | ✓ 11 | 数据**分析**(analyze/visualize/upload/summary) |
| `data_agent/` | `DataAgent`(旧)→`DataAvailabilityAgent`(本轮改) | ✓ `api/v1/data_availability.py` 3 端点 | ✓ 11(本轮补) | 数据**可用性声明**(generate/audit/select) |
| `data_v2/` | `DataAvailabilityAgent` | ✗ 未暴露 | ✗ 0 | 数据可用性**8 步工作流**(更完整版) |

**判定**:三目录功能**完全不同**,非 v1/v2 弃用关系:
- `data/` = 数据分析(独立功能)
- `data_agent/` 与 `data_v2/` 才是同类(数据可用性),`data_v2` 是 `data_agent` 的未完成重构(8 步 vs 3 task),未暴露路由

`data_v2` 留总审查与 data_agent 一并判定弃用关系(同 citation_v2 模式)。

---

## 二、已修复问题

### D7 — data_agent 类名与 data/ 冲突(中危,correctness)

**文件**: `app/agents/data_agent/agent.py:13`(旧)

**问题**: 旧类名 `DataAgent` 与 `data/agent.py` 的 `DataAgent` 同名——两个不同功能类同名,`data_availability.py` 不得不 `import as NatureDataAgent` 规避。命名冲突是设计缺陷。

**修复**: 改名为 `DataAvailabilityAgent`(与 data_v2 一致,消除冲突);API 改用单例工厂 `get_data_availability_agent()`,删除 `as NatureDataAgent` 规避写法。

**回归测试**: `test_class_name_is_data_availability_agent`。

### D1/D8 — LLM 高温调用(中危,correctness)

**文件**: `data/agent.py:135,158`、`data_agent/agent.py:63,80,101`(旧)

**问题**: 两 agent 共 5 处 call_llm 不传 temperature,默认 0.7。数据分析解释/可用性声明属半确定性,高温可能产生不稳定结论。

**修复**: 两 agent 各加 `_DETERMINISTIC_TEMPERATURE = 0.0`,5 处显式传参。

**回归测试**: `test_generate_statement_uses_low_temperature` 等 3 个。

### D3 — analyze 的 else 分支无类型校验(低危,correctness)

**文件**: `data/agent.py:70-75`(旧)

**问题**: `if isinstance(data, str)` 调 load_data,`elif list`/`else` 都 `pd.DataFrame(data)`——else 分支无类型校验,传非 list/dict 对象由 pandas 抛晦涩错误。

**修复**: else 改为 `isinstance(data, (list, dict))`,否则抛 `ValidationException` 明确提示类型。

### D4 — visualize/upload/get_summary 死分支(低危,correctness)

**文件**: `data/agent.py:152-155,179-182,200-203`(旧)

**问题**: 三处 `if isinstance(data, list): pd.DataFrame(data) else: pd.DataFrame(data)`——两分支完全相同,dead 分支。

**修复**: 提取为静态方法 `_to_dataframe(data)`,统一校验 list/dict 后转 DataFrame,消除重复。

### D6 — process 空值错误不友好(低危,correctness)

**文件**: `data/agent.py:48-60`(旧)

**问题**: `task=None` 走 else 抛"未知任务类型: None",错误信息不友好。

**修复**: dict 分派 + 错误信息改为 `未知任务类型: {task!r}，支持: analyze/visualize/upload/summary`。

### D9 — task_handlers 每次重建(低危,性能)

**修复**: 缓存到 `__init__` 的 `self._task_handlers`。

### D10 — data_agent 无单例工厂(低危,reliability)

**文件**: `app/agents/data_agent/__init__.py`

**修复**: 加 `@lru_cache` 单例 `get_data_availability_agent()`;API 3 端点改用单例(原每次请求 `NatureDataAgent()` 实例化)。

**回归测试**: `test_singleton_factory_returns_same_instance`、`test_singleton_is_data_availability_agent`。

### D2 — data/ 分派风格不统一(低危,correctness)

**修复**: if/elif 链改为 dict 分派,与 citation/cover 风格对齐。

---

## 三、识别但本轮不改的问题(留总审查)

| # | 文件 | 问题 | 不改原因 |
|---|------|------|---------|
| D5 | `data/tools.py` | DataTools 实现了 6 声明工具,**无 latent 风险**(已验证) | 已验证无需改 |
| D11 | `data_v2/agent.py` | 363 行 8 步工作流,未暴露路由,无测试 | 与 data_agent 弃用关系一并判定 |
| D12 | `data_v2/__init__.py` | 无单例工厂 | 同 D11 |
| — | `data_agent/prompts.py` | 3 个 E501 历史遗留 | 本轮未动 prompts.py |

---

## 四、验证记录

```
pytest tests/unit/agents/test_data.py tests/unit/agents/test_data_agent.py
→ 22 passed in 0.17s (data 11 + data_agent 11)

pytest tests/unit/ -q
→ 134 passed in 0.75s (含第 1-4 轮 67 + 第 5 轮 11 + 原有 56)

ruff check app/agents/data/agent.py app/agents/data_agent/ app/api/v1/data_availability.py tests/unit/agents/test_data_agent.py
→ All checks passed!

python -c "from app.agents.data_agent import get_data_availability_agent; ..."
→ OK no name clash; routes: ['/generate-statement', '/audit-statement', '/select-repository']
```

**未验证范围(如实标注)**:
- 真实 LLM 调用:测试全 mock
- API 端点鉴权:留总审查
- data_v2 弃用关系:留总审查与 data_agent 一并判定

---

## 五、改动文件清单

| 文件 | 改动 |
|------|------|
| `app/agents/data/agent.py` | D1 低温、D3 类型校验、D4 死分支提取、D6 错误友好、D2 dict 分派 |
| `app/agents/data_agent/agent.py` | D7 改名 DataAvailabilityAgent、D8 低温、D9 缓存 |
| `app/agents/data_agent/__init__.py` | D10 单例工厂 |
| `app/api/v1/data_availability.py` | D7 改用单例、删 as 规避写法 |
| `tests/unit/agents/test_data_agent.py` | 新建,11 个测试覆盖分派/空值/低温/单例/类名 |

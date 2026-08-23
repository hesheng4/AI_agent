# Writing Agent 审查报告(第 7 轮)

**审查日期**: 2026-06-27
**审查范围**: `app/agents/writing/{agent.py,__init__.py}`、`app/api/v1/writing.py`
**基线测试**: 14 → 21(新 7);全量回归 153 → 160 passed

---

## 一、已修复问题

### W1 — 用户级 API 配置经实例属性(高危,security/并发)

**文件**: `app/agents/writing/agent.py:47-49`(旧)

**问题**: `process` 把 `_user_api_*` 存实例属性(同 K5 模式)。单例下并发污染→用户 A 用 B 的 API key。

**修复**: 删实例属性赋值,6 处 call_llm 改从 `request.get("_user_api_*")` 取。

**回归测试**: `test_process_does_not_set_instance_attrs_for_user_api`、`test_concurrent_requests_do_not_cross_contaminate`。

### W2/W3 — handlers 重建 + 空值错误(低危)

**修复**: task_handlers 缓存 `__init__`;task 空值友好错误含支持列表。

### W4 — 无单例(中危)

**修复**: 加 `get_writing_agent()` 单例;API 6 处 `WritingAgent()` 改单例。

### W5 — LLM 高温(中危)

**修复**: 6 处 call_llm 加 `temperature=self._DETERMINISTIC_TEMPERATURE`(0.0)。

**回归测试**: `test_polish_uses_low_temperature`、`test_create_outline_uses_low_temperature`。

---

## 二、留总审查

| # | 问题 | 原因 |
|---|------|------|
| — | `api/v1/writing.py:35` E501 历史遗留 | _require_api_key 函数未动 |
| — | `polish` handler `request.get("paper_type")` 取值未赋变量(L155) | 历史遗留死语句,留总审查 |

---

## 三、验证

```
pytest tests/unit/agents/test_writing.py tests/unit/agents/test_writing_agent.py
→ 21 passed

pytest tests/unit/ -q
→ 160 passed

ruff check (我改的文件)
→ All checks passed!

烟测: OK writing singleton + no instance attr
```

**未验证**: 真实 LLM 调用(测试全 mock);API 端点鉴权(留总审查)。

---

## 四、改动文件

| 文件 | 改动 |
|------|------|
| `app/agents/writing/agent.py` | W1 去实例属性、W2 缓存、W3 友好错误、W5 低温 |
| `app/agents/writing/__init__.py` | W4 单例 |
| `app/api/v1/writing.py` | 6 处用单例 |
| `tests/unit/agents/test_writing_agent.py` | 新建,7 个测试覆盖 W1/W3/W5/W4 |

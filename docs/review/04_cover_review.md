# Cover Agent 审查报告(第 4 轮)

**审查日期**: 2026-06-27
**审查范围**: `app/agents/cover/{agent.py,__init__.py,prompts.py}`、`app/api/v1/cover.py`
**基线测试**: 0 → 修复后 13 passed;全量回归 123 passed

---

## 一、已修复问题

### K5 — 用户级 API 配置经实例属性传递(高危,security/并发)

**文件**: `app/agents/cover/agent.py:30-34`(旧)

**问题**: 旧版 `process` 把 `_user_api_key` 等存到 `self._user_api_*` 实例属性,handler 再读 self。API 用模块级 `_agent = CoverAgent()` 伪单例,**并发请求互相覆盖实例属性 → 用户 A 的请求可能用用户 B 的 API key**。高危数据泄露/计费错乱。

**修复**: 删除实例属性赋值,handler 直接从 `request.get("_user_api_*")` 取并传给 `call_llm`。request dict 是每请求独立的,无并发污染。

**回归测试**:
- `test_process_does_not_set_instance_attrs_for_user_api` 验证 process 后实例上无 `_user_api_*` 残留
- `test_concurrent_requests_do_not_cross_contaminate` 验证两次连续请求各自用自己的 key

### K3 — CoverRequest 缺 draft 必需字段(高危,correctness)

**文件**: `app/api/v1/cover.py:12-16`(旧)

**问题**: 旧 `CoverRequest` 仅 4 字段(task/content/letter_type/journal),但 agent 的 draft 需要 title/abstract/key_result/significance,presubmission 需要 title/abstract。**API model 缺多个必需字段 → draft 的结构化输入路径完全失败**,前端只能塞进 content。

**修复**: CoverRequest 补全 title/abstract/key_result/significance/content 五字段,各字段 description 标明用于哪个 task。

### K1 — API task 描述与实现不一致(中危,correctness)

**文件**: `app/api/v1/cover.py:13`(旧)

**问题**: 旧 description `draft|audit|shorten`,但 agent 只实现 `draft/audit/presubmission`——"shorten" 不存在,"presubmission" 未在 description。前端误传 shorten → agent 抛"未知任务类型",错误信息与 API 文档不符。

**修复**: description 改为 `draft|audit|presubmission`,与 agent 实现一致。

### K6 — 空 task 未回退默认(低危,correctness)

**文件**: `app/agents/cover/agent.py:31`(旧)

**问题**: `task = request.get("task", "draft")` 当 task 为空字符串 `""` 时 .get 返回 ""(非默认),handlers.get("") → None → 抛"未知任务类型"。空字符串未处理。

**修复**: `task = request.get("task") or "draft"`——空字符串/None/缺失均回退 draft。

**回归测试**: `test_empty_task_falls_back_to_draft`、`test_missing_task_falls_back_to_draft`。

### K8 — LLM 高温调用(中危,correctness)

**文件**: `app/agents/cover/agent.py:64,81,101`(旧)

**问题**: 3 处 call_llm 不传 temperature,默认 0.7。cover draft 半确定性,高温可能破坏 prompts 要求的 "fenced code block" 格式。

**修复**: 引入 `_DETERMINISTIC_TEMPERATURE = 0.0`,3 处显式传参。

**回归测试**: `test_draft_uses_low_temperature`、`test_audit_uses_low_temperature`。

### K10 — draft/presubmission 空输入未校验(低危,correctness)

**文件**: `app/agents/cover/agent.py:46-70,89-107`(旧)

**问题**: draft 的空 title/abstract 直通 LLM 浪费 token;audit 已有 content 校验但 draft/presubmission 无。

**修复**: draft/presubmission 加 `if not (title.strip() or abstract.strip())` 校验,至少需其一。audit 补 content 空校验。

**回归测试**: `test_draft_validates_required_fields`、`test_audit_validates_content`、`test_presubmission_validates_required_fields`。

### K7 — handlers 每次重建(低危,性能)

**修复**: 缓存到 `__init__` 的 `self._handlers`。

### 单例工厂(对齐 citation 风格)

**文件**: `app/agents/cover/__init__.py`

**修复**: 加 `@lru_cache` 单例 `get_cover_agent()`;API 改用单例而非模块级直接实例化。

**回归测试**: `test_singleton_factory_returns_same_instance`、`test_singleton_is_cover_agent`。

---

## 二、识别但本轮不改的问题(留总审查)

| # | 文件:行 | 维度 | 问题 | 不改原因 |
|---|---------|------|------|---------|
| K2 | `api/v1/cover.py:15` | correctness | `letter_type` 字段 agent 不读,死输入 | 需决定实现 letter_type 功能或删字段,留总审查 |
| K4 | `api/v1/cover.py:23` | correctness | `model_dump()` 传 letter_type 给 agent,agent 不读 | 同 K2,一并决定 |
| K9 | `api/v1/cover.py:10` | reliability | 模块级 `_agent` 导入时实例化,有副作用 | 已改用单例工厂,但 `_agent` 仍在模块级赋值;留总审查统一改为路由内 get_cover_agent() |
| — | `prompts.py:7,9` | style | 2 个 E501 中文字符串行过长 | 历史遗留,本轮 prompts.py 未动 |

---

## 三、验证记录

```
pytest tests/unit/agents/test_cover.py
→ 13 passed in 0.13s

pytest tests/unit/ -q
→ 123 passed in 0.67s (含第 1-3 轮 54 + 第 4 轮 13 + 原有 56)

ruff check app/agents/cover/agent.py app/agents/cover/__init__.py app/api/v1/cover.py tests/unit/agents/test_cover.py
→ All checks passed!

python -c "from app.agents.cover import get_cover_agent; from app.api.v1.cover import router"
→ OK cover singleton + import
→ routes: ['/cover/']
```

**未验证范围(如实标注)**:
- 真实 LLM 调用:测试全 mock call_llm
- API 端点鉴权:本轮未跑端点级测试(需 DB+用户),留总审查
- K5 并发安全:测试用串行两请求模拟,未做真实并发压测,留集成测试

---

## 四、改动文件清单

| 文件 | 改动 |
|------|------|
| `app/agents/cover/agent.py` | K5 去实例属性、K6 空 task 回退、K7 handlers 缓存、K8 低温、K10 空值校验、清未用 import |
| `app/agents/cover/__init__.py` | 单例工厂 get_cover_agent |
| `app/api/v1/cover.py` | K1 task 描述、K3 补全 CoverRequest 字段、用单例、import 排序 |
| `tests/unit/agents/test_cover.py` | 新建,13 个测试覆盖分派/空 task/空值/低温/K5 并发/单例 |

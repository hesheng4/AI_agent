# Coordinator Agent 审查报告(第 6 轮)

**审查日期**: 2026-06-27
**审查范围**: `app/agents/coordinator/{agent.py,planner.py,__init__.py}`、`app/api/v1/coordinator.py`
**基线测试**: 0 → 19 passed;全量回归 134 → 153 passed

---

## 一、已修复问题

### CO1/CO7 — 子 agent 全预建 + 无单例(中危,performance/reliability)

**文件**: `app/agents/coordinator/agent.py:31-51`(旧)

**问题**: 旧版 `__init__` 立即实例化全部 16 个子 agent(每个含 LLMClient),即便单 agent 请求也全建,浪费内存与初始化时间;且 import 时硬依赖 16 个模块,任一失败致 coordinator 整体不可用。无单例工厂。

**修复**: 改懒加载——`_AGENT_CLASSES` 仅存类引用(module_path, class_name),`get_agent(name)` 首次调用时 `importlib.import_module` + 实例化并缓存。`__init__` 后 `_agent_instances` 为空。加 `get_coordinator_agent()` 单例。

**回归测试**: `test_lazy_loading_no_instances_at_init`、`test_get_agent_lazy_loads`、`test_get_agent_caches`、`test_singleton_*`。

### CO3 — process_simple 重复路由表(低危,correctness)

**文件**: `app/agents/coordinator/agent.py:245-277`(旧)

**问题**: `process_simple` 本地建 30 项 `agent_map`,与 planner 的 `SKILL_KEYWORD_MAP` 重复维护,易不一致。

**修复**: 删本地 agent_map,直接用 `planner.identify_agents(request)` 路由。

### CO5 — planner 可变默认参数(低危,correctness)

**文件**: `app/agents/coordinator/planner.py:108`(旧)

**问题**: `agents: dict = None` 经典反模式。

**修复**: 改 `agents: dict[str, Any] | None = None`。

---

## 二、识别但本轮不改的问题(留总审查)

| # | 问题 | 不改原因 |
|---|------|---------|
| CO2 | import 时硬依赖 16 个子 agent 模块 | 懒加载已缓解(改为首次调用才 import);彻底改需动 16 个子 agent,留总审查 |
| CO4 | 兜底取 `agents_needed[0]` 不一定最匹配 | 意图识别精度需重设计路由算法,留总审查 |
| CO6 | `_user_api_*` 是否透传给子 agent | 需确认 16 个子 agent 是否支持,留总审查 |
| — | `planner.py` 大量 E501(数据行中文字符串) | 历史遗留,本轮未动数据行,留总审查 |

---

## 三、验证记录

```
pytest tests/unit/agents/test_coordinator.py
→ 19 passed in 0.11s

pytest tests/unit/ -q
→ 153 passed in 0.77s (含第 1-5 轮 78 + 第 6 轮 19 + 原有 56)

ruff check app/agents/coordinator/agent.py app/agents/coordinator/__init__.py app/api/v1/coordinator.py tests/unit/agents/test_coordinator.py
→ All checks passed!

python -c "from app.agents.coordinator import get_coordinator_agent; ..."
→ OK coordinator singleton + lazy; routes: ['/coordinator/capability-map', '/coordinator/workflow-templates', '/coordinator/route']
```

**未验证范围(如实标注)**:
- 真实 16 子 agent 协调:测试 mock 子 agent,未验真实并行执行
- planner.py 历史 E501:留总审查

---

## 四、改动文件清单

| 文件 | 改动 |
|------|------|
| `app/agents/coordinator/agent.py` | CO1 懒加载、CO3 删重复路由表、用 get_agent |
| `app/agents/coordinator/planner.py` | CO5 可变默认参数、import 排序 |
| `app/agents/coordinator/__init__.py` | CO7 单例工厂 |
| `app/api/v1/coordinator.py` | 用单例 |
| `tests/unit/agents/test_coordinator.py` | 新建,19 个测试覆盖路由/分解/依赖/循环/懒加载/单例/整合 |

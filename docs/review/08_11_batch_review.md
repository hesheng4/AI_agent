# B 方案合并审查报告(第 8-11 轮合并)

**审查日期**: 2026-06-27
**审查范围**: methods/polishing/stats/submission/submission_package 5 个 agent
**策略**: B 方案——只修 3 个已验证的系统性问题(W1 并发污染/低温/单例),其余留总审查
**全量回归**: 160 passed(无破坏)

---

## 一、批量修复(5 个 agent)

### W1 — 用户级 API 配置经实例属性(高危,security/并发)

**文件**: methods/polishing/stats/submission/submission_package 的 agent.py

**问题**: 5 个 agent 的 `process` 把 `_user_api_*` 存实例属性(同 K5/W1 模式)。单例下并发污染→用户 A 用 B 的 API key。

**修复**: 用批量脚本删 process 的 3 行实例属性赋值;call_llm 改 `request.get("_user_api_*")`。
**关键修后 bug**: 批量脚本漏改 submission/submission_package 的 6 处单行 `user_api_model=self._user_api_model`,已用 search_replace 补修。最终 `self._user_api` 全仓 0 残留。

### 低温缺失

**修复**: call_llm 加 `temperature=0.0`(确定性任务)。

### 单例缺失

**修复**: 5 个 `__init__.py` 加 `@lru_cache` 单例工厂 `get_<name>_agent()`。

---

## 二、验证

- `self._user_api` 全仓 0 残留 ✓
- 5 个 agent import + 单例 + 无实例属性烟测 ✓
- 全量回归 160 passed ✓
- ruff: 我改的文件有 I001 import 排序 + 历史 E501(留总审查统一清)

---

## 三、留总审查(第 12 轮)

- ruff I001 import 排序(5 个 __init__.py)
- ruff F401 未用 import(METHODS_SYSTEM_PROMPT/STATS_SYSTEM_PROMPT/SUBMISSION_SYSTEM_PROMPT)
- 大量历史 E501(中文字符串/prompts)
- experiment/literature/reviewer 等低温缺失(本轮未触及)
- 各 agent 死语句/设计缺陷
- citation_v2/data_v2 弃用关系判定
- API 端点鉴权集成测试

---

## 四、改动文件

| 文件 | 改动 |
|------|------|
| 5 个 agent.py | W1 去实例属性 + 低温 |
| 5 个 __init__.py | 单例工厂 |

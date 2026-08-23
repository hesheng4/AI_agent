# Citation Agent 审查报告(第 2 轮)

**审查日期**: 2026-06-27
**审查范围**: `app/agents/citation/{agent.py,prompts.py,__init__.py}`、`app/api/v1/citation.py`
**不在本轮**: `app/agents/citation/scripts/nature_citation.py`(2011 行独立 CLI,从 Crossref 检索,与 agent.py 是两条独立路径,留总审查)
**基线测试**: 0 → 修复后 10 passed;全量回归 96 passed

---

## 一、已修复问题

### C1 — verify_citations 不校验空引用(低危,correctness)

**文件**: `app/agents/citation/agent.py:84-107`

**问题**: `verify_citations` 取 `references = request.get("references", [])` 后不校验空,传空 list 会走 LLM 验证流程浪费 token 且返回无意义结果。

**修复**: 空引用列表直接返回 `{"verification": "未提供参考文献，跳过验证", "total_references": 0}`,不触发 LLM。

**回归测试**: `test_verify_citations_empty_references_skips_llm` 验证 mock_llm.assert_not_called()。

### C2 — add_citations 最终整合截断原文(中危,correctness)

**文件**: `app/agents/citation/agent.py:69-74`

**问题**: 前 3 步基于 `content[:6000]` 识别论断与引用,但第 4 步整合用 `content[:4000]` 重新截断。**>4000 字符的原文在最终整合时被截断**,引用编号与论断错位/丢失。

**修复**: 最终整合用完整 `content`(不再 `[:4000]`),注释说明前 3 步已识别完论断。

**回归测试**: `test_add_citations_final_prompt_uses_full_content` 用 5000 字符原文验证最终 prompt 含完整 5000 个 "X"。

### C4 — API 默认 style 与 agent 不一致(中危,correctness)

**文件**: `app/api/v1/citation.py:30-36`

**问题**: `FormatReferencesRequest.style` 默认 `apa`,注释说"nature 不在支持列表中",但 `agent.py` 默认 `nature`、`prompts.py` 通篇 Nature 格式。API 默认与 agent 默认不一致,且注释暗示存在 `CITATION_STYLES` 校验列表但代码里没有。

**修复**: API 默认改为 `nature`,与 agent 默认与 prompts 对齐;删除误导注释;description 补上 nature。

**回归测试**: `test_format_references_default_style_is_nature` 验证 agent 不传 style 时返回 `style=="nature"`。

### C5 — 三端点实例化方式不统一(低危,reliability)

**文件**: `app/api/v1/citation.py:78,104,127`

**问题**: `add`/`verify` 用 `CitationAgent()` 直接实例化,`format` 用 `get_citation_agent()` 单例。前两个每次请求新建 LLM 客户端(浪费),且 `__init__.py` 已提供单例工厂。

**修复**: 三端点统一用 `get_citation_agent()`;清理未用的 `CitationAgent` 导入。

### C6 — 确定性任务用高温(中危,correctness)

**文件**: `app/agents/citation/agent.py:53,57,66,74,105,125`

**问题**: 6 处 LLM 调用全用默认 `temperature=0.7`,但 citation 是确定性任务(同一文本应生成稳定引用)。`prompts.py` 也要求 JSON 输出,高温会破坏 JSON 结构。

**修复**: 引入类常量 `_DETERMINISTIC_TEMPERATURE = 0.0`,6 处调用均显式传 `temperature=self._DETERMINISTIC_TEMPERATURE`。

**回归测试**: `test_add_citations_uses_low_temperature`(验证 4 次调用每次 temperature==0.0)、`test_format_references_uses_low_temperature`。

### C7 — task_handlers 每次重建(低危,性能)

**文件**: `app/agents/citation/agent.py:31-41`

**问题**: `process` 每次调用都重建 `task_handlers` dict。

**修复**: 在 `__init__` 缓存为 `self._task_handlers`。

---

## 二、识别但本轮不改的问题(留总审查)

| # | 文件:行 | 维度 | 问题 | 不改原因 |
|---|---------|------|------|---------|
| C3 | `agent.py:78-82` | correctness | `add_citations` 返回 `segments`/`claims`/`citations` 三个中间 LLM 文本,这些是给 LLM 看的中间产物(prompt 要求 JSON 但 LLM 实际返回可能含解释文本),直接当字段返回给客户端语义混乱 | 改需动 API 响应模型,属公共接口,留总审查 |

---

## 三、不在本轮范围(留总审查)

- `scripts/nature_citation.py`(2011 行独立 CLI,从 Crossref 检索引用,与 agent.py LLM 流程是两条独立路径)
- citation 与 `citation_v2` 的关系判定(留第 3 轮审 citation_v2 时一并判定)

---

## 四、验证记录

```
pytest tests/unit/agents/test_citation.py
→ 10 passed in 0.16s

pytest tests/unit/ -q
→ 96 passed in 0.61s  (含第 1 轮 30 + 第 2 轮 10 + 原有其他)

ruff check app/agents/citation/agent.py app/api/v1/citation.py tests/unit/agents/test_citation.py
→ All checks passed!

python -c "from app.agents.citation import get_citation_agent; from app.api.v1.citation import router"
→ OK citation imports + singleton
→ routes: ['/add', '/verify', '/format']
```

**未验证范围(如实标注)**:
- 真实 LLM 调用:测试全 mock call_llm,未验实际 LLM 返回质量,留集成测试
- API 端点鉴权:本轮未跑端点级测试(需 DB + 用户),`test_security_boundaries.py` 仅覆盖高风险路由不含 citation,留总审查补端点测试

---

## 五、改动文件清单

| 文件 | 改动 |
|------|------|
| `app/agents/citation/agent.py` | C1 空引用跳过、C2 不截断原文、C6 低温、C7 task_handlers 缓存 |
| `app/api/v1/citation.py` | C4 默认 nature、C5 三端点统一单例、清理未用导入 |
| `tests/unit/agents/test_citation.py` | 新建,10 个测试覆盖分派/空值/C1/C4/C6/C2 回归 |

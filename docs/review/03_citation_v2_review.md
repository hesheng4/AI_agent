# Citation_v2 Agent 审查报告(第 3 轮)

**审查日期**: 2026-06-27
**审查范围**: `app/agents/citation_v2/{agent.py,__init__.py}`
**不在本轮**: 无 API 路由(citation_v2 未暴露为端点)、与 citation v1 关系判定
**基线测试**: 0 → 修复后 14 passed;全量回归 110 passed

---

## 一、已修复问题

### V1 — _evaluate_support 死代码(中危,correctness)

**文件**: `app/agents/citation_v2/agent.py:166-189`

**问题**: 旧版先赋 `support_level = "moderate"` 再立即覆写 `= "weak"`,moderate 是死值,显示逻辑残留/未完成重构。

**修复**: 重写为清晰分支——`needs_citation and references` → `weak`(附 note),否则 `metadata-only`。删除死赋值。

**回归测试**: `test_evaluate_support_no_moderate` 验证产出中无 moderate。

### V2 — 支撑等级词汇不统一(中危,correctness)

**文件**: `app/agents/citation_v2/agent.py:41,176-188,248`

**问题**: `SUPPORT_LEVELS` 定义 5 级(strong/partial/background/contradictory/metadata-only),但 `_evaluate_support` 用 weak(不在集合),`generate_html_browser` color map 用 5 级不含 weak → 三处词汇不一致,weak 是孤儿值。

**修复**: `SUPPORT_LEVELS` 加入 `weak`;`generate_html_browser` color map 补 `weak: yellow`;注释说明 weak 语义。

**回归测试**: `test_support_levels_vocabulary_complete`、`test_evaluate_support_only_uses_vocabulary`。

### V7 — _search_references 高温调用(中危,correctness)

**文件**: `app/agents/citation_v2/agent.py:163`

**问题**: `call_llm(prompt)` 不传 temperature,默认 0.7。citation 是确定性任务,同 C6。

**修复**: 引入 `_DETERMINISTIC_TEMPERATURE = 0.0`,显式传参。

**回归测试**: `test_search_references_uses_low_temperature`。

### V8 — 中文句末切分失效(中危,correctness)

**文件**: `app/agents/citation_v2/agent.py:100`

**问题**: `re.split(r"(?<=[.。！？])\s+", para)` 要求标点后有空格才切分,中文句末标点几乎无后续空格 → 整段不切分,长段落超 300 字逻辑失效。

**修复**: `\s+` 改 `\s*` 允许零宽匹配;补 `!?` 覆盖英文标点;过滤空句。

**回归测试**: `test_segment_chinese_long_para_split` 用 20 句中文长段落验证切分 > 1 段。

### V10 — 无单例工厂(低危,reliability)

**文件**: `app/agents/citation_v2/__init__.py`

**问题**: 与 citation v1 风格不一致,无 `get_citation_v2_agent()` 单例。

**修复**: 加 `@lru_cache` 单例工厂。

**回归测试**: `test_singleton_factory_returns_same_instance`、`test_singleton_is_citation_v2_agent`。

### V5 顺手清理 — to_enw/generate_html_browser lint(低危,reliability)

**文件**: `app/agents/citation_v2/agent.py:225-253`

**问题**: 两个静态方法有 8 个 E701(单行多语句)+ 2 个 E501 + 1 个 F541(无占位符 f-string)。虽是 V5 待判定死代码,但本轮顺手清理 lint 避免污染 ruff 基线。

**修复**: 拆分单行 if、color map 提取为局部变量、长 HTML 拆行。**未删除方法本身**(是否删除留总审查与 v1/v2 关系一并判定)。

---

## 二、识别但本轮不改的问题(留总审查)

| # | 文件:行 | 维度 | 问题 | 不改原因 |
|---|---------|------|------|---------|
| V3 | `agent.py:47-59` | correctness | 声明 7 tools 但无 `_tool_*` 方法,若 `_validate_tools` 被调用会 TypeError | 已查 `_validate_tools` 全局无调用,latent 风险;加注释说明 tools 仅声明能力清单。彻底改需动 BaseAgent,留总审查 |
| V4 | `agent.py:191-197` | correctness | `_export` 是 stub,note 明写"待 LLM 生成具体条目" | stub 功能,留总审查决定是否补全 |
| V5 | `agent.py:225-279` | correctness | `to_enw`/`generate_html_browser` 未被 process 任何步骤调用,死代码或待用功能 | 与 v1/v2 关系一并判定 |
| V6 | `agent.py:16` | correctness | 模块级 `logger` 与 BaseAgent 的 `self.logger` 重复 | 不影响功能,留总审查统一清理 |
| V9 | `agent.py:134-164` | correctness | `_search_references` 返回单元素 list,`_evaluate_support` 无法做 claim×reference 匹配,数据流断裂 | 根因是 v2 整体设计未完成,改需重设计数据结构,超出单模块修复范畴 |
| V11 | 无 API 路由 | completeness | citation_v2 完全未暴露为端点 | 与 v1/v2 关系一并判定 |

---

## 三、关键决策点:citation vs citation_v2 关系(留总审查与你确认)

| 维度 | citation(v1) | citation_v2 |
|------|------|------|
| API 路由 | ✓ 3 端点 | ✗ 未暴露 |
| 单例工厂 | ✓ | ✓(本轮补) |
| 测试 | ✓ 10 | ✓ 14(本轮补) |
| LLM 调用 | 4 次,全流程 | 1 次,仅搜索 |
| Export | LLM 生成 | stub(V4) |
| 工具校验 | 不声明 tools | 声明 7 但无实现(V3 latent) |
| 代码成熟度 | 完整 | 多 stub/死代码(V1/V4/V5/V9) |

**判定**: citation_v2 是**未完成的重构原型**。v1 是现行版,v2 是 7 步重构的未竟尝试,多处 stub/死代码且无路由暴露。

**建议(留总审查与你确认)**: 二选一——
- (A) 补全 v2(实现 V4 export、V9 数据流、暴露路由)后替换 v1
- (B) 删除 v2,保留 v1

**本轮不判定不删除**,仅修复 v2 现有 bug 使其至少可运行可测试。

---

## 四、验证记录

```
pytest tests/unit/agents/test_citation_v2.py
→ 14 passed in 0.14s

pytest tests/unit/ -q
→ 110 passed in 0.59s (含第 1 轮 30 + 第 2 轮 10 + 第 3 轮 14 + 原有 56)

ruff check app/agents/citation_v2/ tests/unit/agents/test_citation_v2.py
→ All checks passed!

python -c "from app.agents.citation_v2 import get_citation_v2_agent"
→ OK citation_v2 singleton + import
```

**未验证范围(如实标注)**:
- 真实 LLM 调用:测试全 mock call_llm
- v2 未暴露为端点:无端点级测试可言
- V3 latent 风险:`_validate_tools` 当前无调用,未来若 BaseAgent 改为自动校验会触发

---

## 五、改动文件清单

| 文件 | 改动 |
|------|------|
| `app/agents/citation_v2/agent.py` | V1 死代码、V2 词汇统一、V7 低温、V8 中文切分、V5 lint 清理 |
| `app/agents/citation_v2/__init__.py` | V10 单例工厂 |
| `tests/unit/agents/test_citation_v2.py` | 新建,14 个测试覆盖空值/分段/中文/解析/词汇/死代码/低温/单例/端到端 |

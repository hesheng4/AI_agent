"""差距 #1 回归：coordinator LLM 兜底路由（关键词表零命中时）

关键词命中路径保持确定性（零成本、零延迟、P1-7 锁定）；仅零命中时
由 LLM 从能力清单中选择（temperature=0，命中 LLM 结果缓存）。
覆盖：
1. _llm_route 解析/防御分支（有效名 / 未知名剔除 / 无 JSON / 非法 JSON / 调用失败）；
2. process_simple 兜底接线（零命中 → 单 Agent 取第一个；兜底空 → 抛「未知任务类型」）；
3. process 兜底接线（零命中 → 全编排执行）；
4. 关键词命中路径不触发 LLM 兜底；
5. 「报告」关键词已修剪 —「请给一份报告」不再误路由 paper2ppt。
所有 LLM 调用均 mock，不发真实网络请求。
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.coordinator import CoordinatorAgent
from app.agents.coordinator.planner import TaskPlanner
from app.utils.exceptions import AgentException


class _SpyAgent:
    """记录收到的请求，替代真实子 Agent。"""

    def __init__(self):
        self.received = None

    async def process(self, request):
        self.received = dict(request)
        return {"spy_received": True}


@pytest.fixture
def coordinator():
    return CoordinatorAgent()


# ─────────────────────────────────────────────
# _llm_route：解析与防御分支
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_llm_route_returns_valid_names(coordinator):
    with patch.object(
        coordinator, "call_llm", new=AsyncMock(return_value='{"agents": ["reader"]}')
    ):
        assert await coordinator._llm_route({"task": "翻译这段"}) == ["reader"]


@pytest.mark.asyncio
async def test_llm_route_strips_unknown_names(coordinator):
    """未知名剔除不中断流程；JSON 前后的杂讯文本被忽略。"""
    with patch.object(
        coordinator,
        "call_llm",
        new=AsyncMock(return_value='Sure {"agents": ["reader", "bogus_agent"]}'),
    ):
        assert await coordinator._llm_route({"task": "t"}) == ["reader"]


@pytest.mark.asyncio
async def test_llm_route_no_braces_returns_empty(coordinator):
    """返回无 JSON 花括号 → 回退零命中行为。"""
    with patch.object(coordinator, "call_llm", new=AsyncMock(return_value="无法判断")):
        assert await coordinator._llm_route({"task": "t"}) == []


@pytest.mark.asyncio
async def test_llm_route_invalid_json_returns_empty(coordinator):
    with patch.object(coordinator, "call_llm", new=AsyncMock(return_value="{not json}")):
        assert await coordinator._llm_route({"task": "t"}) == []


@pytest.mark.asyncio
async def test_llm_route_call_failure_returns_empty(coordinator):
    """兜底失败不得让主流程崩溃 — 一律返回空，维持修复前行为。"""
    with patch.object(
        coordinator,
        "call_llm",
        new=AsyncMock(side_effect=AgentException("boom", "coordinator")),
    ):
        assert await coordinator._llm_route({"task": "t"}) == []
    with patch.object(coordinator, "call_llm", new=AsyncMock(side_effect=RuntimeError("net"))):
        assert await coordinator._llm_route({"task": "t"}) == []


# ─────────────────────────────────────────────
# 兜底接线
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_process_simple_zero_hit_uses_llm_fallback(coordinator):
    """零命中 → LLM 选出名字 → 单 Agent 分派取第一个。"""
    spy = _SpyAgent()
    coordinator._agent_instances["cover"] = spy
    with patch.object(
        coordinator, "_llm_route", new=AsyncMock(return_value=["cover"])
    ) as mock_route:
        await coordinator.process_simple({"task": "完全不匹配的请求 zzz"})
    mock_route.assert_awaited_once()
    assert spy.received is not None


@pytest.mark.asyncio
async def test_process_simple_zero_hit_llm_empty_raises(coordinator):
    """零命中 + LLM 兜底返回空 → 维持修复前「未知任务类型」。"""
    with patch.object(coordinator, "_llm_route", new=AsyncMock(return_value=[])):
        with pytest.raises(AgentException, match="未知任务类型"):
            await coordinator.process_simple({"task": "完全不匹配的请求 zzz"})


@pytest.mark.asyncio
async def test_process_simple_keyword_hit_skips_llm(coordinator):
    """关键词命中走确定性路径，不触发 LLM 兜底（零成本）。"""
    spy = _SpyAgent()
    coordinator._agent_instances["cover"] = spy
    with patch.object(coordinator, "_llm_route", new=AsyncMock()) as mock_route:
        await coordinator.process_simple({"task": "投稿信起草"})
    mock_route.assert_not_awaited()
    assert spy.received is not None


@pytest.mark.asyncio
async def test_process_zero_hit_uses_llm_fallback(coordinator):
    """process() 零命中 → LLM 选出 reader → 全编排执行。"""
    spy = _SpyAgent()
    coordinator._agent_instances["reader"] = spy
    with patch.object(coordinator, "_llm_route", new=AsyncMock(return_value=["reader"])):
        result = await coordinator.process(
            {"task": "完全不匹配的请求 zzz", "_task_id": "t-llm-fallback"}
        )
    assert result["status"] == "success"
    assert result["agents_used"] == ["reader"]
    assert spy.received is not None


@pytest.mark.asyncio
async def test_process_keyword_hit_skips_llm(coordinator):
    spy = _SpyAgent()
    coordinator._agent_instances["reader"] = spy
    with patch.object(coordinator, "_llm_route", new=AsyncMock()) as mock_route:
        await coordinator.process({"task": "帮我阅读这篇论文", "_task_id": "t-kw-hit"})
    mock_route.assert_not_awaited()
    assert spy.received is not None


# ─────────────────────────────────────────────
# 关键词修剪：「报告」
# ─────────────────────────────────────────────


def test_report_keyword_trimmed_from_paper2ppt():
    """差距 #1：「请给一份报告」曾因「报告」关键词误路由 paper2ppt；
    修剪后零命中（交由 LLM 兜底判定），具体 PPT 表述仍命中。"""
    planner = TaskPlanner(agents={})
    assert planner.identify_agents({"task": "请给一份报告"}) == []
    assert "paper2ppt" in planner.identify_agents({"task": "转化成PPT演讲"})

"""回归：WS 任务事件订阅归属校验（credibility-convergence 批次二）

历史缺陷：ws.py 认证后不校验 task_id 归属，任何持有效 JWT 的用户
可订阅任意 task_id 的事件总线 → 跨用户任务进度泄露（IDOR）。

修复：协调器 process() 登记任务 owner；ws 订阅前 check_access。
未登记 owner 的任务（旧路径兼容）仍放行。
"""


import pytest

from app.core.events import TaskEventBus


@pytest.mark.asyncio
async def test_registered_owner_can_subscribe():
    bus = TaskEventBus()
    bus.register_owner("t1", "user-a")
    assert bus.check_access("t1", "user-a") is True


@pytest.mark.asyncio
async def test_other_user_denied_on_registered_task():
    bus = TaskEventBus()
    bus.register_owner("t1", "user-a")
    assert bus.check_access("t1", "user-b") is False


@pytest.mark.asyncio
async def test_unregistered_task_allows_any_authenticated_user():
    """未登记任务放行（旧行为兼容：历史运行中任务无 owner 记录）"""
    bus = TaskEventBus()
    assert bus.check_access("unknown-task", "anyone") is True


@pytest.mark.asyncio
async def test_owner_registration_fifo_cap():
    """归属表 FIFO 上限：超限时逐出最旧条目，防无限增长"""
    bus = TaskEventBus()
    bus._owner_cap = 3
    for i in range(5):
        bus.register_owner(f"t{i}", "user-a")
    # 最旧被逐出（变为未登记 → check_access 放行），最新保留
    assert "t0" not in bus._task_owners
    assert "t4" in bus._task_owners
    assert bus.check_access("t4", "user-a") is True
    assert len(bus._task_owners) == 3


@pytest.mark.asyncio
async def test_events_still_flow_after_registration():
    """归属登记不影响既有发布/订阅语义"""
    bus = TaskEventBus()
    bus.register_owner("t1", "user-a")
    q = bus.subscribe("t1")
    await bus.publish("t1", {"type": "progress", "pct": 50})
    event = q.get_nowait()
    assert event["type"] == "progress"
    bus.unsubscribe("t1", q)
    assert "t1" not in bus._subscribers

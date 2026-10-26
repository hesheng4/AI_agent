"""E4: 任务事件总线 — 进程内 pub/sub，连接 Agent 执行与 WebSocket 推送

用法:
  from app.core.events import event_bus
  # 发布事件
  await event_bus.publish(
      "task_abc", {"type": "progress", "agent": "writing", "pct": 50}
  )
  # 订阅事件（WebSocket 端点用）
  async for event in event_bus.subscribe("task_abc"):
      await websocket.send_json(event)
"""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from typing import Any

from app.utils.logger import get_logger

logger = get_logger("core.events")


class TaskEventBus:
    """进程内异步事件总线

    每个 task_id 对应一个 asyncio.Queue，订阅者消费后自动清理。
    支持多订阅者（fan-out），每个订阅者独立队列。
    """

    def __init__(self, maxsize: int = 256):
        self._subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(
            list
        )
        self._maxsize = maxsize
        # task_id → 发起用户（WS 订阅归属校验用）。FIFO 上限防无限增长。
        self._task_owners: dict[str, str] = {}
        self._owner_cap = 10000

    def register_owner(self, task_id: str, user_id: str) -> None:
        """登记任务归属（协调器在 process 开始时调用）"""
        if (
            len(self._task_owners) >= self._owner_cap
            and task_id not in self._task_owners
        ):
            oldest = next(iter(self._task_owners))
            self._task_owners.pop(oldest, None)
        self._task_owners[task_id] = user_id

    def check_access(self, task_id: str, user_id: str) -> bool:
        """订阅归属校验：已登记 owner 时仅 owner 可订阅。

        未登记的任务（历史运行中的旧任务/无 _user_id 的路径）放行，
        与旧行为兼容；新任务均由协调器登记。
        """
        owner = self._task_owners.get(task_id)
        return owner is None or owner == user_id

    async def publish(self, task_id: str, event: dict[str, Any]) -> None:
        """向 task_id 的所有订阅者推送事件"""
        queues = self._subscribers.get(task_id, [])
        if not queues:
            return
        dead: list[asyncio.Queue[dict[str, Any]]] = []
        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(f"事件队列满，丢弃事件: task={task_id}")
                dead.append(q)
        # 清理满队列的订阅者
        for q in dead:
            queues.remove(q)

    def subscribe(self, task_id: str) -> asyncio.Queue[dict[str, Any]]:
        """订阅 task_id 的事件，返回 Queue 供消费者迭代"""
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=self._maxsize)
        self._subscribers[task_id].append(q)
        return q

    def unsubscribe(
        self, task_id: str, q: asyncio.Queue[dict[str, Any]]
    ) -> None:
        """取消订阅并清理"""
        queues = self._subscribers.get(task_id, [])
        if q in queues:
            queues.remove(q)
        if not queues:
            self._subscribers.pop(task_id, None)

    @staticmethod
    def new_task_id() -> str:
        """生成唯一任务 ID"""
        return uuid.uuid4().hex[:16]


# 全局单例
event_bus = TaskEventBus()

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

    async def publish(self, task_id: str, event: dict[str, Any]) -> None:
        """向 task_id 的所有订阅者推送事件"""
        queues = self._subscribers.get(task_id, [])
        if not queues:
            return
        dead: list[asyncio.Queue] = []
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

    def unsubscribe(self, task_id: str, q: asyncio.Queue) -> None:
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

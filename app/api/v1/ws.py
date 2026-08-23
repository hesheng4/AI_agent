"""E4: WebSocket 端点 — 实时推送 Agent 执行进度

连接: ws://host:8000/api/v1/ws/tasks/{task_id}?token=<jwt>
消息格式: {"type": "progress"|"agent_start"|"agent_done"|"result"|"error", ...}
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.events import event_bus
from app.core.security import decode_access_token
from app.utils.logger import get_logger

logger = get_logger("api.ws")
router = APIRouter()


@router.websocket("/tasks/{task_id}")
async def task_ws(websocket: WebSocket, task_id: str, token: str = Query(default="")):
    """任务进度 WebSocket

    前端连接后实时接收 Agent 执行进度事件，直到任务完成或连接断开。
    """
    # 认证：验证 JWT
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return
    try:
        payload = decode_access_token(token)
        if not payload or not payload.get("sub"):
            await websocket.close(code=4001, reason="Invalid token")
            return
    except Exception:
        await websocket.close(code=4001, reason="Token verification failed")
        return

    await websocket.accept()
    queue = event_bus.subscribe(task_id)
    logger.info(f"WS 已连接: task={task_id}, user={payload.get('sub')}")

    try:
        # 双任务：1) 从事件队列推送到 WS  2) 监听 WS 关闭
        async def send_events():
            while True:
                event = await queue.get()
                try:
                    await websocket.send_json(event)
                except Exception:
                    break

        async def recv_keepalive():
            """接收客户端消息（ping/pong 或关闭检测）"""
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                pass

        await asyncio.gather(send_events(), recv_keepalive(), return_exceptions=True)
    finally:
        event_bus.unsubscribe(task_id, queue)
        logger.info(f"WS 已断开: task={task_id}")

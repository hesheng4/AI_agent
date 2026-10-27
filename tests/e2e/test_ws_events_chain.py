"""E2E：WebSocket 任务事件通道（E4）+ 归属校验（credibility-convergence 批次二）

覆盖三个语义：
1. 未认证/坏 token → 4001 拒绝
2. 有效 JWT + 未登记任务 → 可订阅（旧行为兼容）
3. 已登记归属的任务 → owner 可订阅、他人 4003（S1 IDOR 修复的 HTTP 层回归）
"""

import uuid

import pytest
from starlette.testclient import TestClient

pytestmark = pytest.mark.e2e

_PASSWORD = "Passw0rd!e2e"


def _sync_client():
    """WS 需要同步 TestClient（httpx AsyncClient 不支持 websocket）"""
    from app.main import app

    return TestClient(app)


def _unique_creds() -> tuple[str, str]:
    token = uuid.uuid4().hex
    return f"ws_{token[:12]}@example.com", f"u_{token[:10]}"


async def _register_and_get_token(client, email: str, username: str) -> str:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": _PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": _PASSWORD}
    )
    return resp.json()["access_token"]


def test_ws_rejects_missing_and_bad_token():
    client = _sync_client()
    with pytest.raises(Exception):
        # 无 token → 服务端 close(4001)，websockets 连接报异常
        with client.websocket_connect("/api/v1/ws/tasks/t-xyz"):
            pass
    with pytest.raises(Exception):
        with client.websocket_connect("/api/v1/ws/tasks/t-xyz?token=bad.token.here"):
            pass


def test_ws_allows_valid_token_unregistered_task():
    """未登记归属的任务放行（旧行为兼容：进程内直发的任务无 owner 记录）"""
    client = _sync_client()
    # 造一个合法 JWT（不依赖 HTTP 注册——WS 只解 token 不查库）
    from app.core.security import create_access_token

    token = create_access_token(data={"sub": "ws-user-1", "email": "ws1@t.c"})
    with client.websocket_connect(
        f"/api/v1/ws/tasks/unregistered-{uuid.uuid4().hex[:8]}?token={token}"
    ) as ws:
        # 连接建立即通过（accept 被调用）；不发消息直接收关闭或挂起超时
        # ——这里只验证 accept 成功，主动关闭由上下文退出完成
        assert ws is not None


def test_ws_owner_can_subscribe_but_others_denied():
    """归属登记后：owner 可订阅，他人 4003（S1 IDOR HTTP 层回归）"""
    from app.core.events import event_bus
    from app.core.security import create_access_token

    client = _sync_client()
    task_id = f"owned-{uuid.uuid4().hex[:8]}"
    event_bus.register_owner(task_id, "user-owner")

    owner_token = create_access_token(data={"sub": "user-owner", "email": "o@t.c"})
    other_token = create_access_token(data={"sub": "user-other", "email": "x@t.c"})

    # owner 正常连接
    with client.websocket_connect(
        f"/api/v1/ws/tasks/{task_id}?token={owner_token}"
    ) as ws:
        assert ws is not None

    # 他人连接 → 服务端 close(4003)
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            f"/api/v1/ws/tasks/{task_id}?token={other_token}"
        ) as ws:
            ws.receive_text()
    assert exc_info.value.code == 4003


def test_ws_receives_published_events():
    """端到端：连接后收到 event_bus 发布的进度事件"""
    import asyncio

    from app.core.events import event_bus
    from app.core.security import create_access_token

    client = _sync_client()
    task_id = f"evt-{uuid.uuid4().hex[:8]}"
    event_bus.register_owner(task_id, "ws-user-evt")
    token = create_access_token(data={"sub": "ws-user-evt", "email": "e@t.c"})

    with client.websocket_connect(
        f"/api/v1/ws/tasks/{task_id}?token={token}"
    ) as ws:
        # 连接建立后从另一协程发布事件（TestClient 的 websocket_connect
        # 内部跑事件循环，publish 经 anyio from_thread 送入）
        async def _publish():
            await event_bus.publish(
                task_id, {"type": "progress", "agent": "writer", "pct": 50}
            )

        asyncio.run(_publish())
        event = ws.receive_json()
        assert event["type"] == "progress"
        assert event["pct"] == 50

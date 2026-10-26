"""E2E 全链路：Agent 产出物持久化（credibility-convergence v1 门禁 G7）

真实 ASGI 进程内请求（非 mock）：创建 → 列表 → 按 agent 筛选 →
重新导出（payload 透传）→ 删除，外加 user_id 隔离（他人不可见/不可删）
与未认证 401。使用 db_isolated_client（临时 sqlite）。
"""

import uuid

import pytest

pytestmark = pytest.mark.e2e

_PASSWORD = "Passw0rd!e2e"


def _unique_creds() -> tuple[str, str]:
    token = uuid.uuid4().hex
    return f"art_{token[:12]}@example.com", f"u_{token[:10]}"


async def _register_and_login(client) -> dict[str, str]:
    """注册并登录，返回 {Authorization: Bearer <token>} 头"""
    email, username = _unique_creds()
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": _PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": _PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _payload() -> dict:
    return {"review_result": "ok", "score": 4.2, "axes": {"novelty": 4}}


@pytest.mark.asyncio
async def test_artifact_full_chain(db_isolated_client):
    """G7: 创建 → 列表 → 筛选 → 重新导出 → 删除 全链路"""
    headers = await _register_and_login(db_isolated_client)

    # 创建两条不同 agent 的产出物
    resp = await db_isolated_client.post(
        "/api/v1/artifacts/",
        headers=headers,
        json={"agent": "reviewer", "title": "审稿报告 v1", "payload": _payload()},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["agent"] == "reviewer"
    assert body["payload"]["score"] == 4.2
    assert body["id"]
    artifact_id = body["id"]

    resp = await db_isolated_client.post(
        "/api/v1/artifacts/",
        headers=headers,
        json={"agent": "writing", "title": "大纲 v1", "payload": {"outline": []}},
    )
    assert resp.status_code == 200, resp.text

    # 列表（倒序，两条）
    resp = await db_isolated_client.get("/api/v1/artifacts/", headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2

    # 按 agent 筛选
    resp = await db_isolated_client.get(
        "/api/v1/artifacts/", headers=headers, params={"agent": "reviewer"}
    )
    items = resp.json()
    assert len(items) == 1
    assert items[0]["agent"] == "reviewer"

    # 重新导出：单条读取 payload 与创建时一致
    resp = await db_isolated_client.get(
        f"/api/v1/artifacts/{artifact_id}", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["payload"] == _payload()

    # 删除 → 再读取 404 → 列表归一
    resp = await db_isolated_client.delete(
        f"/api/v1/artifacts/{artifact_id}", headers=headers
    )
    assert resp.status_code == 200, resp.text
    resp = await db_isolated_client.get(
        f"/api/v1/artifacts/{artifact_id}", headers=headers
    )
    assert resp.status_code == 404
    resp = await db_isolated_client.get(
        "/api/v1/artifacts/", headers=headers, params={"agent": "reviewer"}
    )
    assert resp.json() == []


@pytest.mark.asyncio
async def test_artifact_user_isolation(db_isolated_client):
    """user_id 隔离：B 看不到也删不掉 A 的产出物"""
    headers_a = await _register_and_login(db_isolated_client)
    headers_b = await _register_and_login(db_isolated_client)

    resp = await db_isolated_client.post(
        "/api/v1/artifacts/",
        headers=headers_a,
        json={"agent": "reviewer", "title": "A 的报告", "payload": {"x": 1}},
    )
    artifact_id = resp.json()["id"]

    resp = await db_isolated_client.get("/api/v1/artifacts/", headers=headers_b)
    assert resp.status_code == 200
    assert resp.json() == []

    resp = await db_isolated_client.get(
        f"/api/v1/artifacts/{artifact_id}", headers=headers_b
    )
    assert resp.status_code == 404

    resp = await db_isolated_client.delete(
        f"/api/v1/artifacts/{artifact_id}", headers=headers_b
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_artifact_requires_auth(db_isolated_client):
    resp = await db_isolated_client.get("/api/v1/artifacts/")
    assert resp.status_code == 401
    resp = await db_isolated_client.post("/api/v1/artifacts/", json={})
    assert resp.status_code == 401

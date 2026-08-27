"""E2E 全链路：注册 → 登录 → JWT 访问 → 失效/错误令牌 401

真实 ASGI 进程内请求（非 mock）：注册建用户 → 登录换令牌对 →
access token 访问 /me → refresh 换新令牌 → 过期/错误/类型混用令牌 401。
使用 db_isolated_client（临时 sqlite），不污染开发数据库。
与 tests/integration/test_e1_e2_auth_passthrough.py 的分工：
E1 锁「无 token 一律 401」，本文件锁「认证全链路行为正确」。
"""

import uuid
from datetime import timedelta

import pytest

from app.core.security import create_access_token

pytestmark = pytest.mark.e2e

_PASSWORD = "Passw0rd!e2e"  # ≥8 字符，含 4 类字符


def _unique_creds() -> tuple[str, str]:
    token = uuid.uuid4().hex
    return f"e2e_{token[:12]}@example.com", f"u_{token[:10]}"


async def _register(client, email: str, username: str, password: str = _PASSWORD):
    return await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": password},
    )


async def _login(client, email: str, password: str = _PASSWORD):
    return await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )


# ─────────────────────────────────────────────
# 注册
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_returns_user(db_isolated_client):
    email, username = _unique_creds()
    resp = await _register(db_isolated_client, email, username)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email"] == email
    assert body["username"] == username
    assert body["id"]
    assert body["api_key_configured"] is False


@pytest.mark.asyncio
async def test_register_duplicate_email_rejected(db_isolated_client):
    email, username = _unique_creds()
    first = await _register(db_isolated_client, email, username)
    assert first.status_code == 200
    dup = await _register(db_isolated_client, email, "other_user")
    assert dup.status_code == 400


@pytest.mark.asyncio
async def test_register_weak_password_rejected(db_isolated_client):
    """密码复杂度不足（单一字符类）→ 400"""
    email, username = _unique_creds()
    resp = await _register(db_isolated_client, email, username, password="a" * 12)
    assert resp.status_code == 400


# ─────────────────────────────────────────────
# 登录
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_login_success_returns_token_pair(db_isolated_client):
    email, username = _unique_creds()
    await _register(db_isolated_client, email, username)
    resp = await _login(db_isolated_client, email)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password_401(db_isolated_client):
    email, username = _unique_creds()
    await _register(db_isolated_client, email, username)
    resp = await _login(db_isolated_client, email, password="WrongPass9!x")
    assert resp.status_code == 401


# ─────────────────────────────────────────────
# JWT 访问 /me
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_me_with_access_token(db_isolated_client):
    email, username = _unique_creds()
    await _register(db_isolated_client, email, username)
    tokens = (await _login(db_isolated_client, email)).json()
    resp = await db_isolated_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == email


@pytest.mark.asyncio
async def test_me_rejects_refresh_token_as_access(db_isolated_client):
    """S1/M2 类型隔离：refresh token 当 access 用 → 401"""
    email, username = _unique_creds()
    await _register(db_isolated_client, email, username)
    tokens = (await _login(db_isolated_client, email)).json()
    resp = await db_isolated_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_rejects_expired_token(db_isolated_client):
    """过期 access token（exp 已过）→ 401"""
    email, username = _unique_creds()
    reg = await _register(db_isolated_client, email, username)
    user_id = reg.json()["id"]
    expired = create_access_token(
        {"sub": user_id, "email": email}, expires_delta=timedelta(seconds=-10)
    )
    resp = await db_isolated_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_rejects_garbage_token(db_isolated_client):
    resp = await db_isolated_client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"}
    )
    assert resp.status_code == 401


# ─────────────────────────────────────────────
# refresh 流程
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_issues_working_token_pair(db_isolated_client):
    email, username = _unique_creds()
    await _register(db_isolated_client, email, username)
    tokens = (await _login(db_isolated_client, email)).json()

    resp = await db_isolated_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert resp.status_code == 200, resp.text
    new_tokens = resp.json()
    assert new_tokens["access_token"]

    # 新 access token 可直接访问 /me
    me = await db_isolated_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == email

    # 新 refresh token 当 access 用仍被拒绝（类型隔离不变）
    bad = await db_isolated_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_tokens['refresh_token']}"},
    )
    assert bad.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rejects_access_token(db_isolated_client):
    """类型隔离：access token 不能当 refresh 用 → 401"""
    email, username = _unique_creds()
    await _register(db_isolated_client, email, username)
    tokens = (await _login(db_isolated_client, email)).json()
    resp = await db_isolated_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]}
    )
    assert resp.status_code == 401

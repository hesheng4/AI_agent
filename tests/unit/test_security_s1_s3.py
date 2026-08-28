"""Round 16 — S1/S3 regression tests (refresh token + password complexity)."""

import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    validate_password_complexity,
)

# ---------------------------------------------------------------------------
# S3 — password complexity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("weak", ["password", "12345678", "abcdefgh", "ABCDEFGH", ""])
def test_s3_weak_password_rejected(weak):
    with pytest.raises(ValueError):
        validate_password_complexity(weak)


@pytest.mark.parametrize("strong", ["Abcdef12", "Passw0rd", "Abcdef!2", "aA1!"])
def test_s3_strong_password_accepted(strong):
    validate_password_complexity(strong)  # no raise


def test_s3_non_string_rejected():
    with pytest.raises(ValueError):
        validate_password_complexity(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# S1 — refresh token: type-strict decode + expiry
# ---------------------------------------------------------------------------


def test_s1_access_token_has_access_type():
    tok = create_access_token(data={"sub": "u1", "email": "a@b.c"})
    payload = decode_access_token(tok)
    assert payload is not None
    assert payload["type"] == "access"
    assert payload["sub"] == "u1"


def test_s1_refresh_token_has_refresh_type():
    tok = create_refresh_token(data={"sub": "u1", "email": "a@b.c"})
    payload = decode_refresh_token(tok)
    assert payload is not None
    assert payload["type"] == "refresh"
    assert payload["sub"] == "u1"


def test_s1_refresh_token_rejected_as_access():
    """Refresh token must NOT be usable as access token (type-strict)."""
    refresh = create_refresh_token(data={"sub": "u1", "email": "a@b.c"})
    assert decode_access_token(refresh) is None


def test_s1_access_token_rejected_as_refresh():
    """Access token must NOT be usable as refresh token (type-strict)."""
    access = create_access_token(data={"sub": "u1", "email": "a@b.c"})
    assert decode_refresh_token(access) is None


def test_s1_garbage_token_rejected():
    assert decode_access_token("not.a.jwt") is None
    assert decode_refresh_token("not.a.jwt") is None


@pytest.mark.asyncio
async def test_s1_refresh_endpoint_issues_new_tokens(db_isolated_client):
    """POST /auth/refresh with valid refresh token → new access + refresh pair.

    用 db_isolated_client 显式注册用户——此前版本依赖开发库已有 users 表
    （无用户则 skip），是隐式的环境依赖；隔离临时库后测试自包含。
    """
    import uuid

    from app.core.security import create_refresh_token

    token = uuid.uuid4().hex[:10]
    email = f"s1_{token}@example.com"
    reg = await db_isolated_client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": f"u_{token}", "password": "Passw0rd!S1"},
    )
    assert reg.status_code == 200, reg.text
    user_id = reg.json()["id"]

    # Build a refresh token directly (bypass login flow which needs DB user)
    refresh = create_refresh_token(data={"sub": user_id, "email": email})
    response = await db_isolated_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "access_token" in body and body["access_token"]
    assert "refresh_token" in body and body["refresh_token"]
    # New access token must be type=access
    new_payload = decode_access_token(body["access_token"])
    assert new_payload is not None and new_payload["type"] == "access"


@pytest.mark.asyncio
async def test_s1_refresh_endpoint_rejects_access_token(client):
    """Access token must not work on /auth/refresh (type-strict endpoint)."""
    from app.core.security import create_access_token

    access = create_access_token(data={"sub": "x", "email": "a@b.c"})
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": access},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_s1_refresh_endpoint_rejects_garbage(client):
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "garbage"},
    )
    assert response.status_code == 401

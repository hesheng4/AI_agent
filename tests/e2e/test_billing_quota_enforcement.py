"""E2E：套餐配额强制（credibility-convergence 批次二）

历史缺陷：BillingService.check_quota 从未接入任何生成端点，
用户超套餐后仍可无限调用——配额纯粹是可查询的数字。

修复：enforce_api_rate_limit 依赖（挂全部 research 域 21 条路由）
在限流后执行配额检查；无 UserAccount 行的用户懒创建 free 档。
本文件把用户用量拉满后验证 429，并验证懒创建不误伤新用户。
"""

import uuid

import pytest

pytestmark = pytest.mark.e2e

_PASSWORD = "Passw0rd!e2e"


def _unique_creds() -> tuple[str, str]:
    token = uuid.uuid4().hex
    return f"bil_{token[:12]}@example.com", f"u_{token[:10]}"


async def _register_and_login(client) -> dict[str, str]:
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
    body = resp.json()
    return {
        "Authorization": f"Bearer {body['access_token']}",
        "X-Test-User-Id": body.get("id", ""),
    }


async def _get_user_id(client, headers) -> str:
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_quota_exceeded_returns_429(db_isolated_client):
    """api_calls_used 拉满 → research 域端点 429（依赖层拒绝，不触达 LLM）"""
    headers = await _register_and_login(db_isolated_client)
    user_id = await _get_user_id(db_isolated_client, headers)

    import uuid as _uuid

    import app.core.database as dbmod
    from app.models.billing import PlanType, UserAccount

    # 注册流程不建 UserAccount 行 → 直接插入已超限的 free 档账号
    async with dbmod.async_session() as session:
        session.add(
            UserAccount(
                id=str(_uuid.uuid4()),
                user_id=user_id,
                plan=PlanType.FREE,
                api_calls_used=10_000,  # Free 档月度上限
                tokens_used=0,
            )
        )
        await session.commit()

    # 配额检查发生在依赖层：429 先于任何 LLM 调用
    resp = await db_isolated_client.post(
        "/api/v1/writing/outline",
        headers=headers,
        json={"topic": "test topic"},
    )
    assert resp.status_code == 429, resp.text
    assert "配额" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_quota_lazy_provision_not_blocking_new_users(db_isolated_client):
    """新用户（无 UserAccount 行）不被误杀：懒创建后放行到业务层"""
    headers = await _register_and_login(db_isolated_client)
    user_id = await _get_user_id(db_isolated_client, headers)

    import app.core.database as dbmod
    from sqlalchemy import select

    from app.models.billing import UserAccount

    # 注册流程不建账号 → 首次调用 research 域前无行
    async with dbmod.async_session() as session:
        row = (
            await session.execute(
                select(UserAccount).where(UserAccount.user_id == user_id)
            )
        ).scalar_one_or_none()
    # 依赖尚未触发（上面只调了 /auth/*，不挂 research 依赖）→ 应无行
    assert row is None

    # 触发 research 域依赖：LLM 侧会失败（无 key），但不能是 429 配额错误
    resp = await db_isolated_client.post(
        "/api/v1/writing/outline",
        headers=headers,
        json={"topic": "test topic"},
    )
    assert resp.status_code != 429, resp.text

    # 依赖执行后懒创建了 free 档账号
    async with dbmod.async_session() as session:
        row = (
            await session.execute(
                select(UserAccount).where(UserAccount.user_id == user_id)
            )
        ).scalar_one_or_none()
    assert row is not None

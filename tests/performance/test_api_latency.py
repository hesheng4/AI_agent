"""性能冒烟测试（差距 #7：tests/performance 矩阵落地）

不是压测——延迟冒烟：关键路径必须在宽松预算内返回。
阈值取秒级数量级（而非毫秒级），避免机器速度差异导致 CI 误报；
只测确定性本地路径（auth/JWT/静态表），不含 LLM 调用。
"""

import time
import uuid

import pytest

pytestmark = pytest.mark.performance

# 宽松预算（秒）：本地 sqlite + 进程内 ASGI 的正常数量级是毫秒，
# 阈值给 2-5 个数量级余量，只在出现挂起/死锁/慢查询时报警。
_BUDGET_FAST = 2.0
_BUDGET_CHAIN = 5.0

_PASSWORD = "Passw0rd!perf"


async def _timed(client, method, url, **kwargs) -> tuple[int, float]:
    start = time.perf_counter()
    resp = await client.request(method, url, **kwargs)
    return resp.status_code, time.perf_counter() - start


@pytest.mark.asyncio
async def test_health_within_budget(db_isolated_client):
    code, elapsed = await _timed(db_isolated_client, "GET", "/api/v1/auth/health")
    assert code == 200
    assert elapsed < _BUDGET_FAST, f"health 耗时 {elapsed:.2f}s 超预算"


@pytest.mark.asyncio
async def test_auth_chain_within_budget(db_isolated_client):
    """注册 → 登录 → /me 全链路（含 sqlite 建表/写入 + PBKDF2 哈希 + JWT）"""
    token = uuid.uuid4().hex
    email, username = f"perf_{token[:12]}@example.com", f"p_{token[:10]}"

    code, reg_s = await _timed(
        db_isolated_client,
        "POST",
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": _PASSWORD},
    )
    assert code == 200, f"register {code}"

    login_resp = await db_isolated_client.post(
        "/api/v1/auth/login", json={"email": email, "password": _PASSWORD}
    )
    login_start = time.perf_counter()
    await login_resp.aread()
    login_s = time.perf_counter() - login_start
    assert login_resp.status_code == 200
    access = login_resp.json()["access_token"]

    me_code, me_s = await _timed(
        db_isolated_client,
        "GET",
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert me_code == 200, f"me {me_code}"

    total = reg_s + login_s + me_s
    assert total < _BUDGET_CHAIN, (
        f"auth 链路总耗时 {total:.2f}s 超预算 "
        f"(register={reg_s:.2f}s login={login_s:.2f}s me={me_s:.2f}s)"
    )


@pytest.mark.asyncio
async def test_capability_map_within_budget(db_isolated_client):
    """静态表端点：注册→登录→GET capability-map，认证后读取应为毫秒级"""
    token = uuid.uuid4().hex
    email, username = f"perf_{token[:12]}@example.com", f"p_{token[:10]}"
    await db_isolated_client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": _PASSWORD},
    )
    tokens = (
        await db_isolated_client.post(
            "/api/v1/auth/login", json={"email": email, "password": _PASSWORD}
        )
    ).json()

    code, elapsed = await _timed(
        db_isolated_client,
        "GET",
        "/api/v1/coordinator/capability-map",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert code == 200
    assert elapsed < _BUDGET_FAST, f"capability-map 耗时 {elapsed:.2f}s 超预算"

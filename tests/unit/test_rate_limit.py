import pytest

from app.core.rate_limit import MemoryRateLimiter, get_rate_limit_config


@pytest.fixture
def limiter():
    """创建速率限制器实例"""
    return MemoryRateLimiter()


@pytest.mark.asyncio
async def test_rate_limit_allow(limiter):
    """测试允许请求"""
    assert await limiter.check_rate_limit("user1", max_requests=5, window=60) is True


@pytest.mark.asyncio
async def test_rate_limit_exceeded(limiter):
    """测试超过限制"""
    for _ in range(5):
        await limiter.check_rate_limit("user1", max_requests=5, window=60)
    assert await limiter.check_rate_limit("user1", max_requests=5, window=60) is False


@pytest.mark.asyncio
async def test_rate_limit_remaining(limiter):
    """测试剩余次数"""
    await limiter.check_rate_limit("user1", max_requests=5, window=60)
    await limiter.check_rate_limit("user1", max_requests=5, window=60)

    remaining = await limiter.get_remaining("user1", max_requests=5, window=60)
    assert remaining == 3


@pytest.mark.asyncio
async def test_rate_limit_reset(limiter):
    """测试重置限制"""
    for _ in range(5):
        await limiter.check_rate_limit("user1", max_requests=5, window=60)

    await limiter.reset("user1")
    assert await limiter.check_rate_limit("user1", max_requests=5, window=60) is True


@pytest.mark.asyncio
async def test_rate_limit_different_users(limiter):
    """测试不同用户独立计数"""
    for _ in range(5):
        await limiter.check_rate_limit("user1", max_requests=5, window=60)
    assert await limiter.check_rate_limit("user2", max_requests=5, window=60) is True


def test_rate_limit_config():
    """测试套餐配置"""
    free_config = get_rate_limit_config("free")
    assert free_config["max_requests"] == 10

    pro_config = get_rate_limit_config("pro")
    assert pro_config["max_requests"] == 100

    enterprise_config = get_rate_limit_config("enterprise")
    assert enterprise_config["max_requests"] == 1000


def test_rate_limit_unknown_plan():
    """测试未知套餐"""
    config = get_rate_limit_config("unknown")
    # 应该返回free套餐配置
    assert config["max_requests"] == 10


@pytest.mark.asyncio
async def test_global_cleanup_removes_users_with_only_expired_requests():
    """回归 P4：global_cleanup 应删除所有请求都已过期的用户

    旧版只看 requests[-1]，若最后一条未过期但前面有过期条目，
    用户不会被清理 → 内存只增不减。新版按完整列表清理。
    """
    import time

    limiter = MemoryRateLimiter(max_users=2)
    # user_a：有一条未过期 + 一条已过期（最后一条未过期，旧版会误判保留）
    limiter._requests["user_a"] = {
        "requests": [time.time() - 120, time.time()]  # 旧条目已过期，新条目未过期
    }
    # user_b：仅一条已过期（应被清理）
    limiter._requests["user_b"] = {"requests": [time.time() - 120]}

    limiter._global_cleanup(window=60)

    # user_a 应保留（仍有一条有效），user_b 应被删除
    assert "user_a" in limiter._requests
    assert "user_b" not in limiter._requests
    # user_a 的过期条目应被清掉，仅留 1 条有效
    assert len(limiter._requests["user_a"]["requests"]) == 1

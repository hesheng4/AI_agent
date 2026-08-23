from unittest.mock import patch

import pytest

from app.core.cache import MemoryCache


@pytest.fixture
def cache():
    """创建缓存实例"""
    return MemoryCache(default_ttl=60)


@pytest.mark.asyncio
async def test_cache_set_get(cache):
    """测试缓存写入和读取"""
    await cache.set("key1", "value1")
    assert await cache.get("key1") == "value1"


@pytest.mark.asyncio
async def test_cache_miss(cache):
    """测试缓存未命中"""
    assert await cache.get("nonexistent") is None


@pytest.mark.asyncio
async def test_cache_delete(cache):
    """测试缓存删除"""
    await cache.set("key1", "value1")
    await cache.delete("key1")
    assert await cache.get("key1") is None


@pytest.mark.asyncio
async def test_cache_ttl():
    """测试缓存过期"""
    from datetime import datetime, timedelta

    cache = MemoryCache(default_ttl=60)
    base_time = datetime(2025, 1, 1, 12, 0, 0)

    with patch("app.core.cache.datetime") as mock_dt:
        mock_dt.now.return_value = base_time
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        await cache.set("key1", "value1", ttl=1)
        assert await cache.get("key1") == "value1"

        mock_dt.now.return_value = base_time + timedelta(seconds=2)
        assert await cache.get("key1") is None


@pytest.mark.asyncio
async def test_cache_clear_all(cache):
    """测试清空所有缓存"""
    await cache.set("key1", "value1")
    await cache.set("key2", "value2")

    count = await cache.clear()
    assert count == 2
    assert await cache.get("key1") is None
    assert await cache.get("key2") is None


@pytest.mark.asyncio
async def test_cache_clear_by_prefix(cache):
    """测试按前缀清空缓存"""
    await cache.set("user:1", "data1")
    await cache.set("user:2", "data2")
    await cache.set("session:1", "session1")

    count = await cache.clear("user:")
    assert count == 2
    assert await cache.get("user:1") is None
    assert await cache.get("session:1") == "session1"


@pytest.mark.asyncio
async def test_cache_stats():
    """测试缓存统计"""
    from datetime import datetime, timedelta

    cache = MemoryCache(default_ttl=60)
    base_time = datetime(2025, 1, 1, 12, 0, 0)

    with patch("app.core.cache.datetime") as mock_dt:
        mock_dt.now.return_value = base_time
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        await cache.set("key1", "value1", ttl=60)
        await cache.set("key2", "value2", ttl=1)

        mock_dt.now.return_value = base_time + timedelta(seconds=2)
        stats = await cache.stats()
        assert stats["total"] == 2
        assert stats["active"] == 1
        assert stats["expired"] == 1


@pytest.mark.asyncio
async def test_cache_complex_value(cache):
    """测试复杂值缓存"""
    data = {
        "name": "测试",
        "items": [1, 2, 3],
        "nested": {"key": "value"},
    }
    await cache.set("complex", data)
    assert await cache.get("complex") == data


def test_cache_make_key(cache):
    """测试缓存key生成"""
    key1 = cache._make_key("prefix", {"a": 1, "b": 2})
    key2 = cache._make_key("prefix", {"b": 2, "a": 1})  # 不同顺序
    key3 = cache._make_key("prefix", {"a": 1, "b": 3})  # 不同值

    # 相同参数应该生成相同key
    assert key1 == key2
    # 不同参数应该生成不同key
    assert key1 != key3
    # key应该包含前缀
    assert key1.startswith("prefix:")


@pytest.mark.asyncio
async def test_cache_overwrite(cache):
    """测试覆盖写入"""
    await cache.set("key1", "value1")
    await cache.set("key1", "value2")
    assert await cache.get("key1") == "value2"


@pytest.mark.asyncio
async def test_cache_ttl_zero_uses_default():
    """回归 P6：ttl=0 应回退到 default_ttl，而非写入后立即过期

    旧版 `ttl = ttl or self.default_ttl` 表面对，但若有人误改 ttl=0 会立即过期；
    且与 Redis SET EX=0 报错行为不一致。明确 0/None 均用默认 TTL。
    """
    from datetime import datetime, timedelta

    cache = MemoryCache(default_ttl=60)
    base_time = datetime(2025, 1, 1, 12, 0, 0)

    with patch("app.core.cache.datetime") as mock_dt:
        mock_dt.now.return_value = base_time
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        # ttl=0 应使用 default_ttl=60，写入成功
        await cache.set("key1", "value1", ttl=0)
        assert await cache.get("key1") == "value1"
        # 推进 30 秒（< default_ttl 60），应仍命中
        mock_dt.now.return_value = base_time + timedelta(seconds=30)
        assert await cache.get("key1") == "value1"

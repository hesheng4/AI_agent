"""S4 tests — 缓存 key 确定性序列化。
验证 _stable_repr 与 _hash_key 对自定义对象/JSON 类型产生稳定 key，
修复 str() 默认 repr 带内存地址导致 cache miss 的缺陷。
"""

import json

import pytest

from app.core.cache import _hash_key, _stable_repr, cached

# ── _stable_repr 确定性 ──


def test_stable_repr_primitives_deterministic():
    """基本类型序列化稳定且等价于 json.dumps。"""
    assert _stable_repr({"a": 1, "b": 2}) == json.dumps(
        {"a": 1, "b": 2}, sort_keys=True, ensure_ascii=False
    )
    assert _stable_repr([1, 2, 3]) == "[1, 2, 3]"
    assert _stable_repr("x") == '"x"'


def test_stable_repr_sort_keys_independent_of_order():
    """dict 键顺序不影响结果（sort_keys=True）。"""
    a = _stable_repr({"x": 1, "y": 2})
    b = _stable_repr({"y": 2, "x": 1})
    assert a == b


def test_stable_repr_custom_object_no_memory_address():
    """自定义对象不含内存地址（0x...），且等值实例产生相同序列化。"""

    class Foo:
        def __init__(self, v):
            self.v = v

        def __repr__(self):
            return f"Foo(v={self.v})"

    r1 = _stable_repr(Foo(1))
    r2 = _stable_repr(Foo(1))
    # 不含内存地址模式
    assert "0x" not in r1
    # 等值实例 → 相同序列化（依赖 __repr__ 稳定）
    assert r1 == r2


def test_stable_repr_datetime_serializable():
    """datetime 通过 default=str 回退，不抛 TypeError。"""
    from datetime import datetime

    dt = datetime(2024, 1, 1, 12, 0, 0)
    # 不应抛异常
    r = _stable_repr({"ts": dt})
    assert "2024" in r


def test_stable_repr_nested_structure():
    """嵌套结构递归序列化。"""
    data = {"list": [1, {"k": "v"}], "num": 3.14}
    r = _stable_repr(data)
    assert json.loads(r) == data


def test_stable_repr_circular_ref_fallback():
    """循环引用兜底：json 失败时回退到 repr 哈希，不抛异常。"""

    class Node:
        def __init__(self):
            self.next = None

    a = Node()
    a.next = a  # 循环
    r = _stable_repr(a)
    # 回退路径：类型名:哈希
    assert "Node" in r or len(r) > 0


# ── _hash_key 确定性 ──


def test_hash_key_stable_for_same_params():
    """相同参数 → 相同 key。"""
    params = {"prompt": "hello", "model": "gpt", "temp": 0}
    k1 = _hash_key("llm", params)
    k2 = _hash_key("llm", params)
    assert k1 == k2
    assert k1.startswith("llm:")


def test_hash_key_different_prefix_different_key():
    """不同 prefix → 不同 key。"""
    params = {"x": 1}
    assert _hash_key("a", params) != _hash_key("b", params)


def test_hash_key_different_params_different_key():
    """不同参数 → 不同 key。"""
    assert _hash_key("llm", {"p": "a"}) != _hash_key("llm", {"p": "b"})


def test_hash_key_order_independent():
    """dict 键顺序不影响 key。"""
    k1 = _hash_key("llm", {"a": 1, "b": 2})
    k2 = _hash_key("llm", {"b": 2, "a": 1})
    assert k1 == k2


def test_hash_key_custom_object_stable():
    """自定义对象作参数值：等值实例 → 相同 key（不依赖内存地址）。"""

    class Conf:
        def __init__(self, m):
            self.m = m

        def __repr__(self):
            return f"Conf(m={self.m})"

    k1 = _hash_key("x", {"c": Conf(1)})
    k2 = _hash_key("x", {"c": Conf(1)})
    assert k1 == k2


# ── cached 装饰器不再用 str() ──


@pytest.mark.asyncio
async def test_cached_decorator_hits_on_equivalent_custom_args():
    """@cached 装饰器：等值自定义对象参数 → 缓存命中（验证 S4 修复）。

    修复前：str(obj) 含 0x 内存地址，每次调用都 miss。
    修复后：_stable_repr 用类型名+repr 哈希，等值实例命中。
    """
    call_count = 0

    class Req:
        def __init__(self, q):
            self.q = q

        def __repr__(self):
            return f"Req(q={self.q!r})"

    @cached("test_s4", ttl=60)
    async def fn(req):
        nonlocal call_count
        call_count += 1
        return f"result:{req.q}"

    # 首次调用：miss，执行
    r1 = await fn(Req("hello"))
    assert r1 == "result:hello"
    assert call_count == 1
    # 等值实例二次调用：应命中，不执行
    r2 = await fn(Req("hello"))
    assert r2 == "result:hello"
    assert call_count == 1, "等值自定义对象应命中缓存（S4 修复）"
    # 清理缓存避免污染其他测试
    await fn.cache_clear()


@pytest.mark.asyncio
async def test_cached_decorator_miss_on_different_args():
    """不同参数 → miss，执行。"""
    call_count = 0

    @cached("test_s4_diff", ttl=60)
    async def fn(x):
        nonlocal call_count
        call_count += 1
        return x * 2

    assert await fn(3) == 6
    assert await fn(4) == 8
    assert call_count == 2
    await fn.cache_clear()

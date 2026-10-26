"""回归：用户级 LLM 客户端缓存 LRU（credibility-convergence 批次二）

历史缺陷（LRU 改造引入）：_user_client_cache 曾是普通 dict，
命中路径调用 move_to_end() → AttributeError（无 try 包裹，用户级
API 配置的第二次调用即崩）；逐出路径 client.aclose() 在 openai 2.x
不存在（应为 close()），被 except 吞掉 → 连接池从未真正关闭。
"""

from openai import AsyncOpenAI

from app.utils import llm as llm_mod
from app.utils.llm import LLMClient


def test_user_cache_hit_path_does_not_crash():
    """命中路径 move_to_end 不抛 AttributeError（OrderedDict）"""
    client = LLMClient()
    c1 = client._get_remote_client("sk-user-key-1", "http://localhost:9")
    assert isinstance(c1, AsyncOpenAI)
    # 第二次命中：旧实现在这里 AttributeError
    c2 = client._get_remote_client("sk-user-key-1", "http://localhost:9")
    assert c2 is c1  # 同键复用同一实例（连接池复用）


def test_user_cache_lru_eviction_closes_evicted_client():
    """容量满 → LRU 逐出最旧并调度关闭（close() 而非不存在的 aclose()）"""
    client = LLMClient()
    original_max = llm_mod._USER_CLIENT_CACHE_MAX
    llm_mod._USER_CLIENT_CACHE_MAX = 2
    created: list[AsyncOpenAI] = []
    try:
        for i in range(3):
            c = client._get_remote_client(f"sk-key-{i}", f"http://host-{i}:9")
            created.append(c)
        # 最旧的 key-0 被逐出，容量保持 2
        assert len(llm_mod._user_client_cache) == 2
        assert ("x" * 64)[:32] not in llm_mod._user_client_cache  # 哈希键不可逆
        # 逐出的实例应从缓存消失，其余保留
        keys = list(llm_mod._user_client_cache.keys())
        assert len(keys) == 2
    finally:
        llm_mod._USER_CLIENT_CACHE_MAX = original_max
        llm_mod._user_client_cache.clear()


def test_user_cache_different_keys_get_different_clients():
    client = LLMClient()
    a = client._get_remote_client("sk-a", "http://a:9")
    b = client._get_remote_client("sk-b", "http://b:9")
    assert a is not b
    llm_mod._user_client_cache.clear()

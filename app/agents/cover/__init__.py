from functools import lru_cache

from app.agents.cover.agent import CoverAgent

__all__ = ["CoverAgent", "get_cover_agent"]


@lru_cache(maxsize=1)
def get_cover_agent() -> CoverAgent:
    """返回单例 CoverAgent，避免每次请求重复实例化 LLM 客户端"""
    return CoverAgent()

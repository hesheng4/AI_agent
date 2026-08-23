from functools import lru_cache

from app.agents.reader.agent import ReaderAgent

__all__ = ["ReaderAgent", "get_reader_agent"]


@lru_cache(maxsize=1)
def get_reader_agent() -> ReaderAgent:
    """返回单例 ReaderAgent，避免每次请求重复实例化 LLM 客户端"""
    return ReaderAgent()

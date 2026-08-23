"""Writing Agent module"""

from functools import lru_cache

from app.agents.writing.agent import WritingAgent

__all__ = ["WritingAgent", "get_writing_agent"]


@lru_cache(maxsize=1)
def get_writing_agent() -> WritingAgent:
    """返回单例 WritingAgent，避免每次请求重复实例化"""
    return WritingAgent()

"""Literature Agent module"""

from functools import lru_cache

from app.agents.literature.agent import LiteratureAgent

__all__ = ["LiteratureAgent", "get_literature_agent"]


@lru_cache(maxsize=1)
def get_literature_agent() -> LiteratureAgent:
    """返回单例 LiteratureAgent，避免每次请求重复实例化"""
    return LiteratureAgent()

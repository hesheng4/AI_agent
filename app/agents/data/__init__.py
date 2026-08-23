"""Data Agent module"""

from functools import lru_cache

from app.agents.data.agent import DataAgent

__all__ = ["DataAgent", "get_data_agent"]


@lru_cache(maxsize=1)
def get_data_agent() -> DataAgent:
    """返回单例 DataAgent，避免每次请求重复实例化 LLM 客户端"""
    return DataAgent()

"""Data Availability Agent module"""

from functools import lru_cache

from app.agents.data_agent.agent import DataAvailabilityAgent

__all__ = ["DataAvailabilityAgent", "get_data_availability_agent"]


@lru_cache(maxsize=1)
def get_data_availability_agent() -> DataAvailabilityAgent:
    """返回单例 DataAvailabilityAgent，避免每次请求重复实例化 LLM 客户端"""
    return DataAvailabilityAgent()

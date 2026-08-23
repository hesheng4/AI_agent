"""Coordinator Agent module"""

from functools import lru_cache

from app.agents.coordinator.agent import CoordinatorAgent

__all__ = ["CoordinatorAgent", "get_coordinator_agent"]


@lru_cache(maxsize=1)
def get_coordinator_agent() -> CoordinatorAgent:
    """返回单例 CoordinatorAgent，避免每次请求重复实例化"""
    return CoordinatorAgent()

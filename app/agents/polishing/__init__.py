from app.agents.polishing.agent import PolishingAgent

__all__ = ["PolishingAgent"]

from functools import lru_cache


@lru_cache(maxsize=1)
def get_polishing_agent() -> PolishingAgent:
    """返回单例 PolishingAgent，避免每次请求重复实例化"""
    return PolishingAgent()


__all__ = list(__all__) + ["get_polishing_agent"]

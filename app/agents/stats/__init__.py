from app.agents.stats.agent import StatsAgent

__all__ = ["StatsAgent"]

from functools import lru_cache


@lru_cache(maxsize=1)
def get_stats_agent() -> StatsAgent:
    """返回单例 StatsAgent，避免每次请求重复实例化"""
    return StatsAgent()


__all__ = list(__all__) + ["get_stats_agent"]

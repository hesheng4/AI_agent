from functools import lru_cache

from app.agents.paper2ppt.agent import Paper2PPTAgent

__all__ = ["Paper2PPTAgent", "get_paper2ppt_agent"]


@lru_cache(maxsize=1)
def get_paper2ppt_agent() -> Paper2PPTAgent:
    """返回单例 Paper2PPTAgent，避免每次请求重复实例化 LLM 客户端"""
    return Paper2PPTAgent()

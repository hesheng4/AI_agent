from functools import lru_cache

from app.agents.reviewer.agent import ReviewerAgent

__all__ = ["ReviewerAgent", "get_reviewer_agent"]


@lru_cache(maxsize=1)
def get_reviewer_agent() -> ReviewerAgent:
    """返回单例 ReviewerAgent，避免每次请求重复实例化 LLM 客户端"""
    return ReviewerAgent()

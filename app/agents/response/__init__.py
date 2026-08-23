from functools import lru_cache

from app.agents.response.agent import ResponseAgent

__all__ = ["ResponseAgent", "get_response_agent"]


@lru_cache(maxsize=1)
def get_response_agent() -> ResponseAgent:
    """返回单例 ResponseAgent，避免每次请求重复实例化 LLM 客户端"""
    return ResponseAgent()

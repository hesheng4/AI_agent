from app.agents.methods.agent import MethodsAgent

__all__ = ["MethodsAgent"]

from functools import lru_cache


@lru_cache(maxsize=1)
def get_methods_agent() -> MethodsAgent:
    """返回单例 MethodsAgent，避免每次请求重复实例化"""
    return MethodsAgent()


__all__ = list(__all__) + ["get_methods_agent"]

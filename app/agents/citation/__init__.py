"""Citation Agent module"""

from functools import lru_cache

from app.agents.citation.agent import CitationAgent

__all__ = ["CitationAgent", "get_citation_agent"]


@lru_cache(maxsize=1)
def get_citation_agent() -> CitationAgent:
    """返回单例 CitationAgent，避免每次请求重复实例化 LLM 客户端"""
    return CitationAgent()

from functools import lru_cache

from app.agents.paper_to_patent.agent import PaperToPatentAgent

__all__ = ["PaperToPatentAgent", "get_paper_to_patent_agent"]


@lru_cache(maxsize=1)
def get_paper_to_patent_agent() -> PaperToPatentAgent:
    """返回单例 PaperToPatentAgent，避免每次请求重复实例化 LLM 客户端"""
    return PaperToPatentAgent()

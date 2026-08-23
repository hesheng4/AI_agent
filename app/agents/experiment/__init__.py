"""Experiment Agent module"""

from functools import lru_cache

from app.agents.experiment.agent import ExperimentAgent

__all__ = ["ExperimentAgent", "get_experiment_agent"]


@lru_cache(maxsize=1)
def get_experiment_agent() -> ExperimentAgent:
    """返回单例 ExperimentAgent，避免每次请求重复实例化 LLM 客户端"""
    return ExperimentAgent()

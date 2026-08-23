from app.agents.submission_package.agent import SubmissionPackageAgent

__all__ = ["SubmissionPackageAgent"]

from functools import lru_cache


@lru_cache(maxsize=1)
def get_submission_package_agent() -> SubmissionPackageAgent:
    """返回单例 SubmissionPackageAgent，避免每次请求重复实例化"""
    return SubmissionPackageAgent()


__all__ = list(__all__) + ["get_submission_package_agent"]

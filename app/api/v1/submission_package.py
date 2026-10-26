"""Submission package API endpoints"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agents.submission_package import SubmissionPackageAgent
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(tags=["submission-package"])
_agent = SubmissionPackageAgent()


class SubPkgRequest(BaseModel):
    task: str = Field(
        default="checklist", description="match_journal|checklist|consistency_check"
    )
    abstract: str = Field(default="")
    journal: str = Field(default="nature")
    artefacts: dict[str, Any] = Field(default_factory=dict)


class SubPkgResponse(BaseModel):
    result: dict[str, Any]


@router.post("/", response_model=SubPkgResponse)
async def subpkg_endpoint(
    req: SubPkgRequest, user: User = Depends(get_current_user)
) -> SubPkgResponse:
    result = await _agent.process(
        {
            **req.model_dump(),
            "_user_api_key": user.api_key,
            "_user_api_base_url": user.api_base_url,
            "_user_api_model": user.api_model,
        }
    )
    return SubPkgResponse(result=result)

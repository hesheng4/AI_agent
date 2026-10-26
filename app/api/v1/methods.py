"""Methods API endpoints"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agents.methods import MethodsAgent
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(tags=["methods"])
_agent = MethodsAgent()


class MethodsRequest(BaseModel):
    task: str = Field(
        default="audit", description="audit|draft|check_ethics|remove_vague"
    )
    content: str = Field(default="")
    study_type: str = Field(default="wet-lab")
    journal: str = Field(default="nature")


class MethodsResponse(BaseModel):
    result: dict[str, Any]


@router.post("/", response_model=MethodsResponse)
async def methods_endpoint(
    req: MethodsRequest, user: User = Depends(get_current_user)
) -> MethodsResponse:
    result = await _agent.process(
        {
            **req.model_dump(),
            "_user_api_key": user.api_key,
            "_user_api_base_url": user.api_base_url,
            "_user_api_model": user.api_model,
        }
    )
    return MethodsResponse(result=result)

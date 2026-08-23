"""Polishing API endpoints"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agents.polishing import PolishingAgent
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(tags=["polishing"])
_agent = PolishingAgent()


class PolishingRequest(BaseModel):
    task: str = Field(
        default="polish",
        description="polish|diagnose|terminology|latex_layout|translate",
    )
    content: str = Field(default="")
    journal: str = Field(default="nature")


class PolishingResponse(BaseModel):
    result: dict[str, Any]


@router.post("/", response_model=PolishingResponse)
async def polishing_endpoint(
    req: PolishingRequest, user: User = Depends(get_current_user)
):
    result = await _agent.process(
        {
            **req.model_dump(),
            "_user_api_key": user.api_key,
            "_user_api_base_url": user.api_base_url,
            "_user_api_model": user.api_model,
        }
    )
    return PolishingResponse(result=result)

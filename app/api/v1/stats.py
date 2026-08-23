"""Stats API endpoints"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agents.stats import StatsAgent
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(tags=["stats"])
_agent = StatsAgent()


class StatsRequest(BaseModel):
    task: str = Field(
        default="audit", description="audit|draft|check_test|check_multiple_comparison"
    )
    content: str = Field(default="")
    report_location: str = Field(default="results")
    journal: str = Field(default="nature")


class StatsResponse(BaseModel):
    result: dict[str, Any]


@router.post("/", response_model=StatsResponse)
async def stats_endpoint(req: StatsRequest, user: User = Depends(get_current_user)):
    result = await _agent.process(
        {
            **req.model_dump(),
            "_user_api_key": user.api_key,
            "_user_api_base_url": user.api_base_url,
            "_user_api_model": user.api_model,
        }
    )
    return StatsResponse(result=result)

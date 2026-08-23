from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.billing import PLANS, BillingService
from app.core.database import get_db
from app.models.billing import UserAccount
from app.models.user import User

router = APIRouter()


class QuotaCheckResponse(BaseModel):
    allowed: bool
    reason: str = None
    plan: str = None


class UsageResponse(BaseModel):
    api_calls_used: int
    tokens_used: int
    plan: str


class PlansResponse(BaseModel):
    plans: dict


@router.get("/check-quota", response_model=QuotaCheckResponse)
async def check_quota(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    billing_service = BillingService(db)
    result = await billing_service.check_quota(current_user.id)
    return QuotaCheckResponse(**result)


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(UserAccount).where(UserAccount.user_id == current_user.id)
    )
    account = result.scalar_one_or_none()

    if not account:
        return UsageResponse(api_calls_used=0, tokens_used=0, plan="free")

    return UsageResponse(
        api_calls_used=account.api_calls_used,
        tokens_used=account.tokens_used,
        plan=account.plan.value,
    )


@router.get("/plans", response_model=PlansResponse)
async def get_plans():
    plans = {
        plan_type.value: {
            "name": plan_info["name"],
            "price": str(plan_info["price"]),
            "api_calls": plan_info["api_calls"],
            "tokens": plan_info["tokens"],
        }
        for plan_type, plan_info in PLANS.items()
    }
    return PlansResponse(plans=plans)

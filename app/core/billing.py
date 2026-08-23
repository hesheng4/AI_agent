from decimal import Decimal
from typing import Any

from app.models.billing import PlanType

PLANS = {
    PlanType.FREE: {
        "name": "免费版",
        "price": Decimal("0"),
        "api_calls": 100,
        "tokens": 10000,
        "storage": "100MB",
        "features": ["basic_search", "basic_analysis"],
    },
    PlanType.BASIC: {
        "name": "基础版",
        "price": Decimal("99"),
        "api_calls": 1000,
        "tokens": 100000,
        "storage": "1GB",
        "features": ["all_features"],
    },
    PlanType.PRO: {
        "name": "专业版",
        "price": Decimal("299"),
        "api_calls": 10000,
        "tokens": 1000000,
        "storage": "10GB",
        "features": ["all_features", "priority_support"],
    },
    PlanType.ENTERPRISE: {
        "name": "企业版",
        "price": Decimal("0"),
        "api_calls": -1,
        "tokens": -1,
        "storage": "unlimited",
        "features": ["all_features", "dedicated_support", "custom_integration"],
    },
}


class BillingService:
    def __init__(self, db):
        self.db = db

    async def check_quota(self, user_id: str) -> dict[str, Any]:
        """检查用户配额"""
        from sqlalchemy import select

        from app.models.billing import UserAccount

        result = await self.db.execute(
            select(UserAccount).where(UserAccount.user_id == user_id)
        )
        account = result.scalar_one_or_none()

        if not account:
            return {"allowed": False, "reason": "Account not found"}

        plan = PLANS.get(account.plan, PLANS[PlanType.FREE])

        if plan["api_calls"] != -1 and account.api_calls_used >= plan["api_calls"]:
            return {"allowed": False, "reason": "API quota exceeded"}

        if plan["tokens"] != -1 and account.tokens_used >= plan["tokens"]:
            return {"allowed": False, "reason": "Token quota exceeded"}

        return {"allowed": True, "plan": plan["name"]}

    async def record_usage(self, user_id: str, api_calls: int = 1, tokens: int = 0):
        """记录使用量"""
        import uuid

        from sqlalchemy import update

        from app.models.billing import UsageRecord, UserAccount

        await self.db.execute(
            update(UserAccount)
            .where(UserAccount.user_id == user_id)
            .values(
                api_calls_used=UserAccount.api_calls_used + api_calls,
                tokens_used=UserAccount.tokens_used + tokens,
            )
        )

        record = UsageRecord(
            id=str(uuid.uuid4()),
            user_id=user_id,
            api_calls=api_calls,
            tokens_used=tokens,
            endpoint="",
            response_time=0,
        )
        self.db.add(record)

        await self.db.commit()

    def calculate_cost(self, api_calls: int, tokens: int) -> float:
        """计算费用，返回 float 以避免 Decimal 与 float 字面量比较的精度陷阱"""
        api_cost = Decimal(str(api_calls)) * Decimal("0.001")
        token_cost = Decimal(str(tokens)) * Decimal("0.00001")
        return float(api_cost + token_cost)

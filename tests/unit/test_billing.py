import pytest

from app.core.billing import PLANS, BillingService, PlanType


def test_plans_defined():
    assert PlanType.FREE in PLANS
    assert PlanType.BASIC in PLANS
    assert PlanType.PRO in PLANS
    assert PlanType.ENTERPRISE in PLANS


def test_free_plan_limits():
    plan = PLANS[PlanType.FREE]
    assert plan["api_calls"] == 100
    assert plan["tokens"] == 10000
    assert plan["price"] == 0


def test_calculate_cost():
    service = BillingService(None)

    cost = service.calculate_cost(100, 1000)
    assert cost == pytest.approx(0.11, rel=1e-9)


def test_calculate_cost_zero():
    service = BillingService(None)
    assert service.calculate_cost(0, 0) == 0.0


def test_calculate_cost_large_numbers():
    service = BillingService(None)
    cost = service.calculate_cost(1_000_000, 10_000_000)
    assert cost == pytest.approx(1100.0, rel=1e-6)

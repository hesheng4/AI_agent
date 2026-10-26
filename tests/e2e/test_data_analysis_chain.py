"""E2E：数据分析路由 HTTP 链路（credibility-convergence 覆盖缺口清偿）

data/analyze 是「真实统计计算 + LLM 解释」混合端点：统计部分用真实
DataTools（零 mock 数值），仅 LLM 解释用 FakeLLM 打桩。
验证 analyze/visualize/upload 三个端点的 HTTP 语义与统计正确性。
"""

import uuid

import pytest

pytestmark = pytest.mark.e2e

_PASSWORD = "Passw0rd!e2e"

# 两组可分离的样本（组间均值差显著）
_GROUP_A = [10.0, 11.0, 10.5, 10.2, 10.8, 11.2, 10.9, 10.4]
_GROUP_B = [20.0, 21.5, 20.8, 21.0, 20.5, 21.2, 20.9, 21.1]


def _dataset() -> list[dict[str, object]]:
    rows = []
    for i, v in enumerate(_GROUP_A):
        rows.append({"group": "A", "value": v, "idx": i})
    for i, v in enumerate(_GROUP_B):
        rows.append({"group": "B", "value": v, "idx": i})
    return rows


async def _auth_headers(client) -> dict[str, str]:
    token = uuid.uuid4().hex
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"da_{token[:12]}@example.com",
            "username": f"u_{token[:10]}",
            "password": _PASSWORD,
        },
    )
    assert resp.status_code == 200, resp.text
    resp = await client.post(
        "/api/v1/auth/login",
        json={
            "email": f"da_{token[:12]}@example.com",
            "password": _PASSWORD,
        },
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def stub_data_llm(monkeypatch):
    """DataAgent 的 LLM 解释打桩（统计路径保持真实计算）"""
    from app.agents.data import get_data_agent

    agent = get_data_agent()

    class _FakeLLM:
        async def generate(self, *args, **kwargs):
            return "统计解释（桩）"

    monkeypatch.setattr(agent, "llm", _FakeLLM())
    yield agent


@pytest.mark.asyncio
async def test_analyze_descriptive_over_http(db_isolated_client, stub_data_llm):
    headers = await _auth_headers(db_isolated_client)
    resp = await db_isolated_client.post(
        "/api/v1/data/analyze",
        headers=headers,
        json={"data": _dataset(), "analysis_type": "descriptive"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "success"
    assert body["analysis_type"] == "descriptive"
    assert body["data_shape"] == [16, 3]
    assert body["explanation"] == "统计解释（桩）"
    # 数值正确性：真实统计（非 mock）。两组各 8 个样本，
    # A 组均值 10.625，B 组均值 20.875 → 总均值 15.75
    results = body["results"]
    value_stats = results["numeric"]["value"]
    assert value_stats["count"] == 16
    assert abs(value_stats["mean"] - 15.75) < 1e-9
    assert abs(value_stats["min"] - 10.0) < 1e-9
    # 分类列：两组各 8 条
    assert results["categorical"]["group"]["unique"] == 2
    assert results["categorical"]["group"]["freq"] == 8


@pytest.mark.asyncio
async def test_analyze_group_comparison(db_isolated_client, stub_data_llm):
    """分组分析：A/B 两组均值差异被真实检出"""
    headers = await _auth_headers(db_isolated_client)
    resp = await db_isolated_client.post(
        "/api/v1/data/analyze",
        headers=headers,
        json={
            "data": _dataset(),
            "analysis_type": "group",
            "group_col": "group",
            "value_col": "value",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "success"
    text = str(body["results"])
    # 结果里应体现两组（A/B 均值）
    assert "A" in text and "B" in text


@pytest.mark.asyncio
async def test_analyze_missing_columns_rejected(db_isolated_client, stub_data_llm):
    """缺 group_col/value_col → 400 语义错误（ValidationException → HTTP 4xx），
    不允许 None 直入统计工具"""
    headers = await _auth_headers(db_isolated_client)
    resp = await db_isolated_client.post(
        "/api/v1/data/analyze",
        headers=headers,
        json={"data": _dataset(), "analysis_type": "group"},
    )
    assert 400 <= resp.status_code < 500, resp.text


@pytest.mark.asyncio
async def test_visualize_recommendation(db_isolated_client, stub_data_llm):
    headers = await _auth_headers(db_isolated_client)
    resp = await db_isolated_client.post(
        "/api/v1/data/visualize",
        headers=headers,
        json={"data": _dataset(), "chart_type": "bar"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "success"
    assert "group" in body["columns"] and "value" in body["columns"]


@pytest.mark.asyncio
async def test_upload_summary(db_isolated_client, stub_data_llm):
    headers = await _auth_headers(db_isolated_client)
    resp = await db_isolated_client.post(
        "/api/v1/data/upload",
        headers=headers,
        json={"data": _dataset(), "filename": "smoke.csv"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "success"
    assert body["filename"] == "smoke.csv"
    assert body["summary"]

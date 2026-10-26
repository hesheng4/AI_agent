"""E2E：导出与计费路由 HTTP 冒烟（credibility-convergence 覆盖缺口清偿）

背景：覆盖分析发现 17 个 API 路由模块零 HTTP 层测试，其中 export（5 端点，
二进制/附件路径）与 billing（3 端点）为纯计算端点，无需 LLM 桩即可全链路验证。
"""

import uuid

import pytest

pytestmark = pytest.mark.e2e

_PASSWORD = "Passw0rd!e2e"


def _unique_creds() -> tuple[str, str]:
    token = uuid.uuid4().hex
    return f"exp_{token[:12]}@example.com", f"u_{token[:10]}"


async def _auth_headers(client) -> dict[str, str]:
    email, username = _unique_creds()
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": _PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": _PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


_PAPERS = [
    {
        "title": "Attention Is All You Need",
        "authors": ["Vaswani", "Shazeer"],
        "year": 2017,
        "journal": "NeurIPS",
    },
    {
        "title": "Deep Residual Learning",
        "authors": ["He", "Ren"],
        "year": 2016,
        "journal": "CVPR",
    },
]


@pytest.mark.asyncio
async def test_export_csv_chain(db_isolated_client):
    headers = await _auth_headers(db_isolated_client)
    resp = await db_isolated_client.post(
        "/api/v1/export/csv",
        headers=headers,
        json={"data": [{"col1": "a", "col2": 1}], "filename": "smoke"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/csv")
    assert 'attachment; filename="smoke.csv"' in resp.headers["content-disposition"]
    assert "col1" in resp.text and "a" in resp.text


@pytest.mark.asyncio
async def test_export_json_chain(db_isolated_client):
    headers = await _auth_headers(db_isolated_client)
    resp = await db_isolated_client.post(
        "/api/v1/export/json",
        headers=headers,
        json={"data": [{"k": "v"}], "filename": "smoke"},
    )
    assert resp.status_code == 200, resp.text
    assert "application/json" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_export_bibtex_chain(db_isolated_client):
    headers = await _auth_headers(db_isolated_client)
    resp = await db_isolated_client.post(
        "/api/v1/export/bibtex",
        headers=headers,
        json={"papers": _PAPERS, "filename": "refs"},
    )
    assert resp.status_code == 200, resp.text
    assert 'filename="refs.bib"' in resp.headers["content-disposition"]
    assert "@" in resp.text  # BibTeX 条目符


@pytest.mark.asyncio
async def test_export_ris_chain(db_isolated_client):
    headers = await _auth_headers(db_isolated_client)
    resp = await db_isolated_client.post(
        "/api/v1/export/ris",
        headers=headers,
        json={"papers": _PAPERS, "filename": "refs"},
    )
    assert resp.status_code == 200, resp.text
    assert 'filename="refs.ris"' in resp.headers["content-disposition"]
    assert "TY  -" in resp.text  # RIS 条目头


@pytest.mark.asyncio
async def test_export_markdown_chain(db_isolated_client):
    headers = await _auth_headers(db_isolated_client)
    resp = await db_isolated_client.post(
        "/api/v1/export/markdown",
        headers=headers,
        json={"data": [{"name": "x", "value": 2}], "filename": "tbl"},
    )
    assert resp.status_code == 200, resp.text
    assert "name" in resp.text


@pytest.mark.asyncio
async def test_export_requires_auth(db_isolated_client):
    resp = await db_isolated_client.post("/api/v1/export/csv", json={"data": []})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_billing_plans_public_and_usage_authed(db_isolated_client):
    """/plans 公开（价格表，信息级）；/usage 须登录且懒创建后可查"""
    resp = await db_isolated_client.get("/api/v1/billing/plans")
    assert resp.status_code == 200, resp.text
    plans = resp.json()["plans"]
    assert "free" in plans
    assert plans["free"]["api_calls"]  # Free 档有调用配额数字

    headers = await _auth_headers(db_isolated_client)
    # /billing/usage 本身不触发 research 域依赖；先打一次 research 端点
    # 触发懒创建？→ 不需要：usage 端点对无账号用户返回零值（向后兼容）
    resp = await db_isolated_client.get("/api/v1/billing/usage", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["plan"] in {"free", "basic", "pro", "enterprise"}
    assert body["api_calls_used"] >= 0


@pytest.mark.asyncio
async def test_billing_usage_requires_auth(db_isolated_client):
    resp = await db_isolated_client.get("/api/v1/billing/usage")
    assert resp.status_code == 401

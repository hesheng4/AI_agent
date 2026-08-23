"""P0 安全修复回归测试。

覆盖两项体检发现（reports/project_full_audit_2026-08-23.md）：
1. SPA 兜底路由路径穿越 — `GET /../../.env` 曾返回 200 + 文件内容；
   修复后必须回落到 index.html，绝不能吐出 .env 内容。
2. ascend / adaptation / alignment 三组路由曾被漏加鉴权 — 现在
   无 token / 坏 token 必须 401。
"""

import pytest

# ---------------------------------------------------------------------------
# 1. SPA 兜底路由路径穿越
# ---------------------------------------------------------------------------

# Starlette 会对 %2F 解码，因此这些编码变体在路由层等价于 ../..
_TRAVERSAL_PATHS = [
    "/..%2F..%2F.env",
    "/..%2F.env",
    "/%2e%2e/%2e%2e/.env",
    "/..%2F..%2F..%2Fetc%2Fpasswd",
]


@pytest.mark.parametrize("path", _TRAVERSAL_PATHS)
@pytest.mark.asyncio
async def test_spa_fallback_rejects_traversal(client, path):
    """穿越路径不得返回目标文件内容（回落 SPA 入口是允许的）。"""
    response = await client.get(path)
    # 200（index.html）或 404 都可接受，关键是内容不能泄露
    body = response.text
    assert "OPENAI_API_KEY" not in body, (
        f"{path} 泄露了 .env 内容（OPENAI_API_KEY 出现在响应中）"
    )
    assert "SECRET_KEY" not in body, f"{path} 泄露了 .env 内容（SECRET_KEY）"
    assert "DATABASE_URL" not in body, f"{path} 泄露了 .env 内容（DATABASE_URL）"


@pytest.mark.asyncio
async def test_spa_fallback_still_serves_index(client):
    """根路径仍正常返回 SPA 入口（修复不能误伤正常访问）。"""
    response = await client.get("/")
    assert response.status_code == 200
    assert "<!DOCTYPE html>" in response.text or "<html" in response.text.lower()


# ---------------------------------------------------------------------------
# 2. ascend 域三组路由鉴权（原为 0 鉴权，2026-08-23 补 dependencies）
# ---------------------------------------------------------------------------

_ASCEND_AUTHED_ENDPOINTS = [
    ("GET", "/api/v1/ascend/info"),
    ("PUT", "/api/v1/ascend/mode"),
    ("GET", "/api/v1/adaptation/status"),
    ("GET", "/api/v1/alignment/status"),
]


@pytest.mark.parametrize("method,path", _ASCEND_AUTHED_ENDPOINTS)
@pytest.mark.asyncio
async def test_ascend_domain_requires_auth(client, method, path):
    """无 Authorization → 401（修复前 ascend/adaptation/alignment 返回 200）。"""
    response = await client.request(method, path)
    assert response.status_code == 401, (
        f"{method} {path} returned {response.status_code} without auth; "
        f"expected 401. Body: {response.text[:200]}"
    )


@pytest.mark.parametrize("method,path", _ASCEND_AUTHED_ENDPOINTS)
@pytest.mark.asyncio
async def test_ascend_domain_rejects_invalid_token(client, method, path):
    """垃圾 bearer token → 401。"""
    response = await client.request(
        method, path, headers={"Authorization": "Bearer not-a-real-jwt"}
    )
    assert response.status_code == 401, (
        f"{method} {path} accepted invalid token ({response.status_code})"
    )

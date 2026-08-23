import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/profiling/status",
        "/api/v1/validator/env-check",
        "/api/v1/toolchain/status",
        "/api/v1/perf-tuning/status",
        "/api/v1/debugging/status",
        "/api/v1/history-to-skill/status",
    ],
)
async def test_high_risk_routers_require_auth(client, path):
    response = await client.get(path)
    assert response.status_code == 401

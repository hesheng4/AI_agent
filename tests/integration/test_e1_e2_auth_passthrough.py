"""Round 15 — E1/E2 end-to-end regression tests.

E1: API endpoint auth — every routed endpoint depends on get_current_user;
    verify missing/invalid token → 401, not 200.
E2: Coordinator _user_api_* passthrough — verify both process_simple (single
    agent) and process (parallel plan) paths forward user API credentials to
    sub-agent process() calls. Locks CO6 closure (Round 12 §4 latent risk).
"""

import pytest

from app.agents.coordinator import get_coordinator_agent

# ---------------------------------------------------------------------------
# E1 — endpoint auth enforcement
# ---------------------------------------------------------------------------

# Representative endpoints across routers (one per router is enough — they
# share the same get_current_user dependency). Paths verified via OpenAPI
# schema introspection — sub-router prefix lives only in api/v1/__init__.py
# include_router call (Q6 fix: collapsed doubled prefix).
_AUTHED_ENDPOINTS = [
    ("POST", "/api/v1/coordinator/route"),
    ("POST", "/api/v1/cover/"),
    ("POST", "/api/v1/citation/add"),
    ("POST", "/api/v1/methods/"),
    ("POST", "/api/v1/polishing/"),
    ("POST", "/api/v1/stats/"),
    ("POST", "/api/v1/submission-package/"),
    ("GET", "/api/v1/coordinator/capability-map"),
    ("GET", "/api/v1/coordinator/workflow-templates"),
]


@pytest.mark.parametrize("method,path", _AUTHED_ENDPOINTS)
@pytest.mark.asyncio
async def test_e1_endpoint_requires_auth(client, method, path):
    """No Authorization header → 401 (not 200/422/500)."""
    response = await client.request(method, path)
    # 401 means get_current_user rejected; 200 would be a missing-auth bug.
    # 422 (validation) would also be a leak — auth should run before body parse.
    assert response.status_code == 401, (
        f"{method} {path} returned {response.status_code} without auth; "
        f"expected 401. Body: {response.text[:200]}"
    )


@pytest.mark.parametrize("method,path", _AUTHED_ENDPOINTS)
@pytest.mark.asyncio
async def test_e1_endpoint_rejects_invalid_token(client, method, path):
    """Garbage bearer token → 401."""
    response = await client.request(
        method, path, headers={"Authorization": "Bearer not-a-real-jwt"}
    )
    assert response.status_code == 401, (
        f"{method} {path} accepted invalid token ({response.status_code}); "
        f"expected 401."
    )


# ---------------------------------------------------------------------------
# E2 — coordinator _user_api_* passthrough (CO6 closure)
# ---------------------------------------------------------------------------


class _SpyAgent:
    """Spy agent that records the request it received (replaces lazy load)."""

    def __init__(self):
        self.received = None
        self.name = "spy"

    async def process(self, request):
        self.received = dict(request)
        return {"spy_received": True}


@pytest.mark.asyncio
async def test_e2_process_simple_forwards_user_api(monkeypatch):
    """process_simple forwards _user_api_* to the routed sub-agent."""
    coord = get_coordinator_agent()
    spy = _SpyAgent()

    # Force lazy loader to return our spy for 'cover' (a known SKILL_KEYWORD_MAP entry).
    coord._agent_instances["cover"] = spy

    request = {
        "task": "投稿信起草",  # planner maps → cover
        "content": "test abstract",
        "_user_api_key": "user-key-123",
        "_user_api_base_url": "https://user.example.com",
        "_user_api_model": "user-model-x",
    }
    await coord.process_simple(request)

    assert spy.received is not None, "spy agent was not invoked"
    assert spy.received.get("_user_api_key") == "user-key-123"
    assert spy.received.get("_user_api_base_url") == "https://user.example.com"
    assert spy.received.get("_user_api_model") == "user-model-x"


@pytest.mark.asyncio
async def test_e2_process_parallel_forwards_user_api(monkeypatch):
    """process() (parallel plan) forwards _user_api_* to ALL sub-agents.

    Regression guard for CO6: decompose_task references the same request dict,
    so _user_api_* must reach every sub-agent's process() unchanged.
    """
    coord = get_coordinator_agent()
    spies: dict[str, _SpyAgent] = {}

    # Patch lazy loader to return a spy per agent name.
    real_get_agent = coord.get_agent

    def _spy_factory(name):
        if name not in spies:
            spies[name] = _SpyAgent()
        return spies[name]

    coord.get_agent = _spy_factory  # type: ignore[assignment]

    try:
        # '文献综述' triggers a multi-agent plan (literature + writing etc.)
        request = {
            "task": "请帮我做一份文献综述",
            "query": "machine learning",
            "content": "test content",
            "_user_api_key": "parallel-key-xyz",
            "_user_api_base_url": "https://parallel.example.com",
            "_user_api_model": "parallel-model-9",
        }
        try:
            await coord.process(request)
        except Exception:
            # Sub-agents may fail on synthetic input; we only care that
            # spies captured the request before any failure.
            pass
    finally:
        coord.get_agent = real_get_agent  # type: ignore[assignment]

    assert spies, "no sub-agent was invoked by process()"
    for name, spy in spies.items():
        assert spy.received is not None, f"agent {name} received no request"
        assert spy.received.get("_user_api_key") == "parallel-key-xyz", (
            f"agent {name} got wrong/missing _user_api_key: "
            f"{spy.received.get('_user_api_key')!r}"
        )
        assert spy.received.get("_user_api_base_url") == "https://parallel.example.com"
        assert spy.received.get("_user_api_model") == "parallel-model-9"


@pytest.mark.asyncio
async def test_e2_process_simple_no_user_api_keys():
    """When _user_api_* absent, sub-agent still receives the request (None defaults).

    Ensures we don't inject KeyError or half-populated credentials.
    """
    coord = get_coordinator_agent()
    spy = _SpyAgent()
    coord._agent_instances["cover"] = spy

    request = {"task": "投稿信起草", "content": "test"}
    await coord.process_simple(request)

    assert spy.received is not None
    # Keys may be absent or None — both are fine; no exception is the contract.
    assert "_user_api_key" not in spy.received or spy.received["_user_api_key"] is None

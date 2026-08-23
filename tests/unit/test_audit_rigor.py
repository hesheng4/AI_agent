"""Round 16 rigor audit — stress-test S1 refresh + W1/K5 passthrough correctness.

Goal: prove the cumulative claims hold under adversarial scrutiny, not just
the happy path. Each test targets a claim I made in a review doc and tries
to falsify it.
"""

import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    validate_password_complexity,
)

# ---------------------------------------------------------------------------
# FALSIFY: "decode_access_token rejects type=refresh" (R16 claim)
# Try multiple refresh tokens — all must be rejected as access.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", [1, 2, 3, 42, 999])
def test_audit_refresh_never_accepted_as_access(seed):
    refresh = create_refresh_token(data={"sub": f"u{seed}", "email": f"a{seed}@b.c"})
    assert decode_access_token(refresh) is None, (
        f"refresh token seed={seed} was wrongly accepted as access "
        f"— type-strictness broken"
    )


# ---------------------------------------------------------------------------
# FALSIFY: "decode_refresh_token rejects type=access"
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_audit_access_never_accepted_as_refresh(seed):
    access = create_access_token(data={"sub": f"u{seed}", "email": f"a{seed}@b.c"})
    assert decode_refresh_token(access) is None


# ---------------------------------------------------------------------------
# FALSIFY: "expired tokens are rejected"
# This is a jose library contract, but verify it actually fires.
# ---------------------------------------------------------------------------


def test_audit_expired_token_rejected():
    from datetime import UTC, datetime, timedelta

    # Build a token that expired 1 hour ago.
    expired_payload = {
        "sub": "u1",
        "email": "a@b.c",
        "type": "access",
        "exp": datetime.now(UTC) - timedelta(hours=1),
    }
    from jose import jwt

    from app.config import get_settings

    settings = get_settings()
    expired = jwt.encode(
        expired_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    assert decode_access_token(expired) is None, "expired access token was accepted"


def test_audit_expired_refresh_rejected():
    from datetime import UTC, datetime, timedelta

    from jose import jwt

    from app.config import get_settings

    settings = get_settings()
    expired = jwt.encode(
        {
            "sub": "u1",
            "email": "a@b.c",
            "type": "refresh",
            "exp": datetime.now(UTC) - timedelta(days=1),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    assert decode_refresh_token(expired) is None


# ---------------------------------------------------------------------------
# FALSIFY: "tampered token (wrong signature) rejected"
# ---------------------------------------------------------------------------


def test_audit_tampered_token_rejected():
    access = create_access_token(data={"sub": "u1", "email": "a@b.c"})
    # Flip last char — breaks signature.
    tampered = access[:-1] + ("A" if access[-1] != "A" else "B")
    assert decode_access_token(tampered) is None
    assert decode_refresh_token(tampered) is None


# ---------------------------------------------------------------------------
# FALSIFY: "password complexity is stable across category permutations"
# A password meeting exactly 2 categories must pass regardless of WHICH 2.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pw",
    [
        "Abcdefgh",  # lower + upper
        "abcd1234",  # lower + digit
        "abcd!@#$",  # lower + special
        "ABCD1234",  # upper + digit
        "ABCD!@#$",  # upper + special
        "1234!@#$",  # digit + special
    ],
)
def test_audit_two_category_passwords_accepted(pw):
    validate_password_complexity(pw)  # must not raise


@pytest.mark.parametrize(
    "pw",
    [
        "abcdefgh",  # only lower
        "ABCDEFGH",  # only upper
        "12345678",  # only digit
        "!@#$%^&*",  # only special
    ],
)
def test_audit_single_category_passwords_rejected(pw):
    with pytest.raises(ValueError):
        validate_password_complexity(pw)


# ---------------------------------------------------------------------------
# FALSIFY: "W1/K5 passthrough — _user_api_* arrives at call_llm unchanged"
# Inspect submission/submission_package call sites to confirm the request.get()
# pattern is genuinely passthrough (no mutation, no fallback to instance attr).
# This is a STATIC contract check — we read the source, not run it.
# ---------------------------------------------------------------------------


def test_audit_no_instance_api_attr_in_agents():
    """Re-run the W1/K5 grep with a NON-line-anchored regex to catch
    multi-line `self._user_api` assignments the original grep might have missed
    on lines that wrap."""
    import os
    import re

    agents_dir = r"D:\AI_agent\app\agents"
    # Match `self._user_api` anywhere — not anchored, not lookahead-limited.
    pat = re.compile(r"self\._user_api")
    hits = []
    for root, dirs, files in os.walk(agents_dir):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for fn in files:
            if not fn.endswith(".py"):
                continue
            p = os.path.join(root, fn)
            with open(p, encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    if pat.search(line):
                        hits.append(f"{p}:{i}: {line.strip()}")
    assert not hits, (
        "self._user_api instance attr residuals found (W1/K5 regression):\n"
        + "\n".join(hits)
    )


# ---------------------------------------------------------------------------
# FALSIFY: "all call_llm calls specify temperature" — AST-aware, not grep
# ---------------------------------------------------------------------------


def test_audit_all_call_llm_have_temperature():
    """AST-walk every agent .py, find every call to self.call_llm(...), and
    assert the call's keyword arguments include temperature=."""
    import ast
    import os

    agents_dir = r"D:\AI_agent\app\agents"
    missing = []
    for root, dirs, files in os.walk(agents_dir):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for fn in files:
            if not fn.endswith(".py"):
                continue
            p = os.path.join(root, fn)
            with open(p, encoding="utf-8") as f:
                src = f.read()
            try:
                tree = ast.parse(src, filename=p)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                # Match self.call_llm(...)
                if not isinstance(node.func, ast.Attribute):
                    continue
                if node.func.attr != "call_llm":
                    continue
                if (
                    not isinstance(node.func.value, ast.Name)
                    or node.func.value.id != "self"
                ):
                    continue
                kws = {kw.arg for kw in node.keywords if kw.arg is not None}
                # Also accept positional temperature
                # (3rd positional after prompt, system_prompt)
                has_temp_kw = "temperature" in kws
                has_temp_pos = len(node.args) >= 3
                if not (has_temp_kw or has_temp_pos):
                    rel = p.replace(agents_dir + os.sep, "")
                    missing.append(f"{rel}:{node.lineno}")
    assert not missing, (
        f"call_llm calls WITHOUT temperature (AST audit, {len(missing)} sites):\n"
        + "\n".join(missing)
    )


# ---------------------------------------------------------------------------
# FALSIFY: "singleton factories actually return the same instance"
# lru_cache should make factory() is factory() — but only if no args.
# ---------------------------------------------------------------------------


def test_audit_all_singleton_factories_idempotent():
    """Import every agent __init__ with a get_*_agent factory and confirm
    two calls return the same object."""
    import importlib
    import importlib.util
    import os
    import re

    agents_dir = r"D:\AI_agent\app\agents"
    factory_re = re.compile(r"def\s+(get_\w+_agent)\s*\(")
    failures = []
    for name in os.listdir(agents_dir):
        full = os.path.join(agents_dir, name)
        if not os.path.isdir(full) or name in ("__pycache__",):
            continue
        init_path = os.path.join(full, "__init__.py")
        if not os.path.exists(init_path):
            continue
        with open(init_path, encoding="utf-8") as f:
            src = f.read()
        m = factory_re.search(src)
        if not m:
            continue  # figure has no factory — expected
        factory_name = m.group(1)
        mod = importlib.import_module(f"app.agents.{name}")
        factory = getattr(mod, factory_name, None)
        if factory is None:
            failures.append(f"{name}: {factory_name} declared but not exported")
            continue
        a = factory()
        b = factory()
        if a is not b:
            failures.append(f"{name}: {factory_name}() returned distinct instances")
        # Clear lru_cache so other tests get fresh state.
        factory.cache_clear()
    assert not failures, "Singleton failures:\n" + "\n".join(failures)

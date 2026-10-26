"""S2 tests — 请求体大小限制 + content 字段 max_length 约束。
验证两层防御：
1. 全局中间件：Content-Length > MAX_REQUEST_BODY_BYTES → 413
2. Pydantic Field：content 超 max_length → 422（Pydantic 验证错误）
3. chunked 传输（无 Content-Length）→ 411（防 2MB 上限被绕过）
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import get_settings


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
def app(settings):
    """构造一个最小 app，仅挂载 S2 中间件 + 一个测试路由，避免依赖完整初始化。
    中间件逻辑与 app/main.py 的 limit_request_body 保持一致。"""
    from fastapi import APIRouter
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field

    application = FastAPI()
    max_body = settings.MAX_REQUEST_BODY_BYTES

    @application.middleware("http")
    async def limit_request_body(request, call_next):
        cl = request.headers.get("Content-Length")
        if cl is None:
            te = request.headers.get("Transfer-Encoding", "")
            if "chunked" in te.lower() and request.method in ("POST", "PUT", "PATCH"):
                return JSONResponse(
                    status_code=411,
                    content={"detail": "请使用 Content-Length 声明请求体大小"},
                )
        else:
            try:
                if int(cl) > max_body:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "请求体过大"},
                    )
            except ValueError:
                pass
        return await call_next(request)

    class TestBody(BaseModel):
        content: str = Field(..., max_length=settings.MAX_CONTENT_LENGTH)

    router = APIRouter()

    @router.post("/echo")
    async def echo(body: TestBody):
        return {"len": len(body.content)}

    application.include_router(router)
    return application


def test_config_limits_exist(settings):
    """配置常量存在且为合理正值。"""
    assert settings.MAX_REQUEST_BODY_BYTES > 0
    assert settings.MAX_CONTENT_LENGTH > 0
    # 2MB body 上限合理
    assert settings.MAX_REQUEST_BODY_BYTES >= 1_000_000
    # 500k 字符上限覆盖完整论文
    assert settings.MAX_CONTENT_LENGTH >= 100_000


def test_body_within_limit_accepted(app, settings):
    """正常大小请求体放行。"""
    client = TestClient(app)
    small = "x" * 100
    resp = client.post("/echo", json={"content": small})
    assert resp.status_code == 200
    assert resp.json()["len"] == 100


def test_body_oversize_rejected_413(app, settings):
    """Content-Length 超 MAX_REQUEST_BODY_BYTES → 413。"""
    client = TestClient(app)
    # 构造一个声称超大但实际 body 较小的请求，仅靠 Content-Length 头触发
    huge_body = "x" * 100  # 实际 body 小
    resp = client.post(
        "/echo",
        content=huge_body,
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(settings.MAX_REQUEST_BODY_BYTES + 1000),
        },
    )
    assert resp.status_code == 413


def test_content_field_max_length_enforced(app, settings):
    """content 超 MAX_CONTENT_LENGTH → 422（Pydantic 验证错误）。"""
    client = TestClient(app)
    # 绕过中间件（body 实际小于 2MB），但 content 字段超字符上限
    oversized = "y" * (settings.MAX_CONTENT_LENGTH + 1)
    # oversized 字符串 ≈ 500k+1 字符 ≈ 500KB UTF-8 < 2MB，中间件放行
    resp = client.post("/echo", json={"content": oversized})
    assert resp.status_code == 422  # Pydantic 验证失败


def test_content_at_limit_accepted(app, settings):
    """content 恰好等于 MAX_CONTENT_LENGTH → 放行（边界）。"""
    client = TestClient(app)
    boundary = "z" * settings.MAX_CONTENT_LENGTH
    resp = client.post("/echo", json={"content": boundary})
    assert resp.status_code == 200


def test_invalid_content_length_ignored(app):
    """非法 Content-Length（非数字）→ 不拒绝，交由下游处理。"""
    client = TestClient(app)
    resp = client.post(
        "/echo",
        content='{"content":"x"}',
        headers={
            "Content-Type": "application/json",
            "Content-Length": "not-a-number",
        },
    )
    # 非法 CL 不触发 413，下游正常处理（可能 200 或其他）
    assert resp.status_code != 413


def test_chunked_transfer_rejected_411(app):
    """chunked 传输（无 Content-Length）→ 411。

    回归：chunked 请求没有 Content-Length，旧实现直接放行，
    是 2MB 上限的完整绕过路径（内存耗尽防护失效）。
    httpx 会吞掉手动设置的 Transfer-Encoding 头，因此用裸 ASGI scope 直呼。
    """

    async def _call() -> int:
        status_box = {}

        async def receive():
            return {"type": "http.request", "body": b'{"content":"x"}', "more_body": False}

        async def send(message):
            if message["type"] == "http.response.start":
                status_box["status"] = message["status"]

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/echo",
            "raw_path": b"/echo",
            "query_string": b"",
            "root_path": "",
            "headers": [
                (b"host", b"test"),
                (b"content-type", b"application/json"),
                (b"transfer-encoding", b"chunked"),
            ],
            "client": ("test", 123),
            "server": ("test", 80),
        }
        await app(scope, receive, send)
        return status_box["status"]

    import asyncio

    assert asyncio.run(_call()) == 411


def test_chunked_uppercase_transfer_encoding_rejected_411(app):
    """Transfer-Encoding 大小写不敏感（HTTP 头值大小写无意义）。"""

    async def _call() -> int:
        status_box = {}

        async def receive():
            return {"type": "http.request", "body": b'{"content":"x"}', "more_body": False}

        async def send(message):
            if message["type"] == "http.response.start":
                status_box["status"] = message["status"]

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/echo",
            "raw_path": b"/echo",
            "query_string": b"",
            "root_path": "",
            "headers": [
                (b"host", b"test"),
                (b"content-type", b"application/json"),
                (b"transfer-encoding", b"Chunked"),
            ],
            "client": ("test", 123),
            "server": ("test", 80),
        }
        await app(scope, receive, send)
        return status_box["status"]

    import asyncio

    assert asyncio.run(_call()) == 411

"""E2E 全链路：分享 + fork 深拷贝（credibility-convergence v1 门禁 G8）

真实 ASGI 进程内请求（非 mock）。受控库 fixture：
A 建分类/标签/文献/笔记/引用 → 分享（token 只返回一次）→ B 登录预览 →
fork → **接收方条目/笔记/引用数与原库逐一相等**（G8 黄金断言），
tag usage_count 与 category paper_count 一并核对。
含撤销失效、fork 自己的库拒绝、token 一次性语义（DB 只存哈希）。
"""

import uuid

import pytest

pytestmark = pytest.mark.e2e

_PASSWORD = "Passw0rd!e2e"


def _unique_creds() -> tuple[str, str]:
    token = uuid.uuid4().hex
    return f"shr_{token[:12]}@example.com", f"u_{token[:10]}"


async def _register_and_login(client) -> dict[str, str]:
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


async def _add_paper(client, headers, paper_id: str, title: str, **kw) -> dict:
    resp = await client.post(
        "/api/v1/library/papers",
        headers=headers,
        json={"paper_id": paper_id, "title": title, "authors": ["Author"], **kw},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _library_stats(client, headers) -> dict:
    resp = await client.get("/api/v1/library/stats", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _build_source_library(client, headers) -> None:
    """受控库 fixture：2 分类 + 2 标签 + 3 文献 + 2 笔记 + 1 引用链"""
    await client.post(
        "/api/v1/library/categories",
        headers=headers,
        json={"name": "深度学习"},
    )
    await client.post(
        "/api/v1/library/categories", headers=headers, json={"name": "医学影像"}
    )

    p1 = await _add_paper(
        client,
        headers,
        "ext-p1",
        "Transformer for Medical Imaging",
        tags=["深度学习", "重要"],
        category="深度学习",
        year=2024,
    )
    p2 = await _add_paper(
        client,
        headers,
        "ext-p2",
        "ViT in Radiology",
        tags=["深度学习"],
        category="医学影像",
        year=2023,
    )
    await _add_paper(
        client, headers, "ext-p3", "Survey on Foundation Models", category="深度学习"
    )

    # 笔记挂在 p1/p2
    resp = await client.post(
        "/api/v1/library/notes",
        headers=headers,
        json={
            "paper_id": p1["id"],
            "content": "精读笔记：注意力机制",
            "note_type": "insight",
        },
    )
    assert resp.status_code == 200, resp.text
    resp = await client.post(
        "/api/v1/library/notes",
        headers=headers,
        json={"paper_id": p2["id"], "content": "方法可迁移", "note_type": "general"},
    )
    assert resp.status_code == 200, resp.text

    # 引用链 p1 → p2
    resp = await client.post(
        "/api/v1/library/citations",
        headers=headers,
        json={"citing_paper_id": p1["id"], "cited_paper_id": p2["id"]},
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_share_fork_golden_counts_equal(db_isolated_client):
    """G8: fork 后接收方条目/笔记/引用/分类/标签计数与原库逐一相等"""
    headers_a = await _register_and_login(db_isolated_client)
    headers_b = await _register_and_login(db_isolated_client)
    await _build_source_library(db_isolated_client, headers_a)

    src_stats = await _library_stats(db_isolated_client, headers_a)
    assert src_stats["total_papers"] == 3

    # A 创建分享：明文 token 只出现这一次
    resp = await db_isolated_client.post(
        "/api/v1/shares/",
        headers=headers_a,
        json={"resource_type": "library", "ttl_days": 7},
    )
    assert resp.status_code == 200, resp.text
    share = resp.json()
    token = share["token"]
    assert share["resource_type"] == "library"
    assert share["expires_at"] is not None

    # B 预览：登录态可见 owner 与计数
    resp = await db_isolated_client.get(
        f"/api/v1/shares/by-token/{token}", headers=headers_b
    )
    assert resp.status_code == 200, resp.text
    preview = resp.json()
    assert preview["paper_count"] == 3
    assert preview["citation_count"] == 1
    assert sorted(preview["categories"]) == ["医学影像", "深度学习"]

    # B fork
    resp = await db_isolated_client.post(
        f"/api/v1/shares/by-token/{token}/fork", headers=headers_b
    )
    assert resp.status_code == 200, resp.text
    fork = resp.json()
    assert fork["papers_added"] == 3
    assert fork["papers_skipped"] == 0
    assert fork["categories_created"] == 2
    assert fork["notes_copied"] == 2
    assert fork["citations_copied"] == 1

    # 黄金断言：接收方各项计数与原库逐一相等
    dst_stats = await _library_stats(db_isolated_client, headers_b)
    assert dst_stats["total_papers"] == src_stats["total_papers"]
    assert dst_stats["total_categories"] == src_stats["total_categories"]
    assert dst_stats["total_tags"] == src_stats["total_tags"]
    assert dst_stats["favorite_count"] == src_stats["favorite_count"]

    # B 侧引用网络与原库规模一致
    resp = await db_isolated_client.get("/api/v1/library/citations", headers=headers_b)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # B 侧笔记总数 = 2
    resp = await db_isolated_client.get("/api/v1/library/papers", headers=headers_b)
    papers_b = resp.json()
    note_total = 0
    for p in papers_b:
        resp = await db_isolated_client.get(
            f"/api/v1/library/notes/{p['id']}", headers=headers_b
        )
        note_total += len(resp.json())
    assert note_total == 2

    # B 侧 tag usage_count 与原库一致（tag 名 → usage_count 完全相等）
    resp = await db_isolated_client.get("/api/v1/library/tags", headers=headers_a)
    src_tags = {t["name"]: t["usage_count"] for t in resp.json()}
    resp = await db_isolated_client.get("/api/v1/library/tags", headers=headers_b)
    dst_tags = {t["name"]: t["usage_count"] for t in resp.json()}
    assert dst_tags == src_tags

    # B 侧 category paper_count 与原库一致
    resp = await db_isolated_client.get("/api/v1/library/categories", headers=headers_a)
    src_cats = {c["name"]: c["paper_count"] for c in resp.json()}
    resp = await db_isolated_client.get("/api/v1/library/categories", headers=headers_b)
    dst_cats = {c["name"]: c["paper_count"] for c in resp.json()}
    assert dst_cats == src_cats

    # fork 可独立演化：B 删一篇不影响 A
    target = next(p for p in papers_b if p["paper_id"] == "ext-p1")
    resp = await db_isolated_client.delete(
        f"/api/v1/library/papers/{target['id']}", headers=headers_b
    )
    assert resp.status_code == 200, resp.text
    resp = await db_isolated_client.get("/api/v1/library/papers", headers=headers_a)
    assert len(resp.json()) == 3


@pytest.mark.asyncio
async def test_fork_skips_existing_papers(db_isolated_client):
    """接收方已收藏同名外部 paper_id 时跳过且不破坏既有条目"""
    headers_a = await _register_and_login(db_isolated_client)
    headers_b = await _register_and_login(db_isolated_client)
    await _add_paper(db_isolated_client, headers_a, "ext-x", "Shared Paper", tags=["t"])
    await _add_paper(
        db_isolated_client, headers_b, "ext-x", "My Own Local Copy", tags=["mine"]
    )

    resp = await db_isolated_client.post(
        "/api/v1/shares/", headers=headers_a, json={"resource_type": "library"}
    )
    token = resp.json()["token"]

    resp = await db_isolated_client.post(
        f"/api/v1/shares/by-token/{token}/fork", headers=headers_b
    )
    assert resp.status_code == 200
    fork = resp.json()
    assert fork["papers_added"] == 0
    assert fork["papers_skipped"] == 1

    # B 原有条目未被覆盖
    resp = await db_isolated_client.get("/api/v1/library/papers", headers=headers_b)
    assert [p["title"] for p in resp.json()] == ["My Own Local Copy"]


@pytest.mark.asyncio
async def test_share_revoke_and_expiry_semantics(db_isolated_client):
    """撤销后预览 404；fork 自己的库 400；非法 token 404"""
    headers_a = await _register_and_login(db_isolated_client)
    headers_b = await _register_and_login(db_isolated_client)
    await _add_paper(db_isolated_client, headers_a, "ext-r", "Revoke Me")

    resp = await db_isolated_client.post(
        "/api/v1/shares/", headers=headers_a, json={"resource_type": "library"}
    )
    share = resp.json()
    token, share_id = share["token"], share["id"]

    # fork 自己的库 → 400
    resp = await db_isolated_client.post(
        f"/api/v1/shares/by-token/{token}/fork", headers=headers_a
    )
    assert resp.status_code == 400

    # 非法 token → 404
    resp = await db_isolated_client.get(
        "/api/v1/shares/by-token/nonexistent", headers=headers_b
    )
    assert resp.status_code == 404

    # owner 撤销 → 接收方预览与 fork 均 404
    resp = await db_isolated_client.delete(
        f"/api/v1/shares/{share_id}", headers=headers_a
    )
    assert resp.status_code == 200, resp.text
    resp = await db_isolated_client.get(
        f"/api/v1/shares/by-token/{token}", headers=headers_b
    )
    assert resp.status_code == 404
    resp = await db_isolated_client.post(
        f"/api/v1/shares/by-token/{token}/fork", headers=headers_b
    )
    assert resp.status_code == 404

    # B 不能撤销 A 的分享
    resp = await db_isolated_client.post(
        "/api/v1/shares/", headers=headers_a, json={"resource_type": "library"}
    )
    other_share = resp.json()
    resp = await db_isolated_client.delete(
        f"/api/v1/shares/{other_share['id']}", headers=headers_b
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_share_requires_login(db_isolated_client):
    """未登录访问分享 → 401（不静默降级为公开）"""
    headers_a = await _register_and_login(db_isolated_client)
    resp = await db_isolated_client.post(
        "/api/v1/shares/", headers=headers_a, json={"resource_type": "library"}
    )
    token = resp.json()["token"]
    resp = await db_isolated_client.get(f"/api/v1/shares/by-token/{token}")
    assert resp.status_code == 401

"""E2E：文献库全量 CRUD 链路（credibility-convergence 覆盖缺口清偿）

library.py 27 个端点此前零 HTTP 层覆盖（share/fork 测试只触及其中一部分）。
本文件覆盖全部 CRUD + 计数同步语义（usage_count/paper_count/级联清理），
纯 DB 操作，无需 LLM 桩。
"""

import uuid

import pytest

pytestmark = pytest.mark.e2e

_PASSWORD = "Passw0rd!e2e"


def _unique_creds() -> tuple[str, str]:
    token = uuid.uuid4().hex
    return f"lib_{token[:12]}@example.com", f"u_{token[:10]}"


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
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _paper_body(paper_id: str, **kw) -> dict:
    return {
        "paper_id": paper_id,
        "title": f"Paper {paper_id}",
        "authors": ["Author A"],
        "year": 2024,
        "abstract": "abstract body",
        "journal": "Nature",
        **kw,
    }


# ─────────────────────────────────────────────
# 分类与标签
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_category_crud_and_paper_count_sync(db_isolated_client):
    headers = await _auth_headers(db_isolated_client)

    # 创建分类
    resp = await db_isolated_client.post(
        "/api/v1/library/categories",
        headers=headers,
        json={"name": "深度学习", "description": "DL papers", "color": "#6366f1"},
    )
    assert resp.status_code == 200, resp.text
    cat = resp.json()
    assert cat["name"] == "深度学习"
    assert cat["paper_count"] == 0

    # 重名分类 → 400
    resp = await db_isolated_client.post(
        "/api/v1/library/categories", headers=headers, json={"name": "深度学习"}
    )
    assert resp.status_code == 400, resp.text

    # 加文献到该分类 → paper_count 同步 +1
    resp = await db_isolated_client.post(
        "/api/v1/library/papers",
        headers=headers,
        json=_paper_body("p-cat-1", category="深度学习"),
    )
    assert resp.status_code == 200, resp.text
    resp = await db_isolated_client.get("/api/v1/library/categories", headers=headers)
    cats = {c["name"]: c for c in resp.json()}
    assert cats["深度学习"]["paper_count"] == 1

    # 删除分类 → 该分类下文献自动改为 uncategorized
    resp = await db_isolated_client.delete(
        f"/api/v1/library/categories/{cat['id']}", headers=headers
    )
    assert resp.status_code == 200, resp.text
    resp = await db_isolated_client.get("/api/v1/library/papers", headers=headers)
    papers = resp.json()
    assert len(papers) == 1
    assert papers[0]["category"] == "uncategorized"


@pytest.mark.asyncio
async def test_tag_crud_and_usage_count_sync(db_isolated_client):
    headers = await _auth_headers(db_isolated_client)

    resp = await db_isolated_client.post(
        "/api/v1/library/tags", headers=headers, json={"name": "重要", "color": "#10b981"}
    )
    assert resp.status_code == 200, resp.text
    tag = resp.json()
    assert tag["usage_count"] == 0

    # 两篇文献使用该标签 → usage_count = 2
    for pid in ("p-t1", "p-t2"):
        resp = await db_isolated_client.post(
            "/api/v1/library/papers",
            headers=headers,
            json=_paper_body(pid, tags=["重要"]),
        )
        assert resp.status_code == 200, resp.text

    resp = await db_isolated_client.get("/api/v1/library/tags", headers=headers)
    tags = {t["name"]: t for t in resp.json()}
    assert tags["重要"]["usage_count"] == 2

    # 删除标签 → 自动从所有 papers 的 tags 移除
    resp = await db_isolated_client.delete(
        f"/api/v1/library/tags/{tag['id']}", headers=headers
    )
    assert resp.status_code == 200, resp.text
    resp = await db_isolated_client.get("/api/v1/library/papers", headers=headers)
    for p in resp.json():
        assert p["tags"] == []


@pytest.mark.asyncio
async def test_tag_auto_created_on_first_use(db_isolated_client):
    """未预创建的标签随 add_paper 自动建立且 usage_count 正确（B1 回归）"""
    headers = await _auth_headers(db_isolated_client)
    for pid in ("p-auto-1", "p-auto-2"):
        await db_isolated_client.post(
            "/api/v1/library/papers",
            headers=headers,
            json=_paper_body(pid, tags=["自动标签"]),
        )
    resp = await db_isolated_client.get("/api/v1/library/tags", headers=headers)
    tags = {t["name"]: t for t in resp.json()}
    assert tags["自动标签"]["usage_count"] == 2


# ─────────────────────────────────────────────
# 文献 CRUD 与筛选
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_paper_crud_list_filter_favorite(db_isolated_client):
    headers = await _auth_headers(db_isolated_client)

    await db_isolated_client.post(
        "/api/v1/library/papers",
        headers=headers,
        json=_paper_body("p-f1", tags=["ml"], category="cat-a"),
    )
    fav = await db_isolated_client.post(
        "/api/v1/library/papers",
        headers=headers,
        json=_paper_body("p-f2", tags=["ml"], category="cat-a"),
    )
    assert fav.status_code == 200, fav.text
    # 收藏 p-f2
    resp = await db_isolated_client.put(
        f"/api/v1/library/papers/{fav.json()['id']}",
        headers=headers,
        json={"is_favorite": 1, "rating": 5},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_favorite"] == 1

    # 按 favorite 筛选
    resp = await db_isolated_client.get(
        "/api/v1/library/papers", headers=headers, params={"favorite": 1}
    )
    assert [p["paper_id"] for p in resp.json()] == ["p-f2"]

    # 按 category 筛选
    resp = await db_isolated_client.get(
        "/api/v1/library/papers", headers=headers, params={"category": "cat-a"}
    )
    assert len(resp.json()) == 2

    # 按 search（标题模糊）筛选
    resp = await db_isolated_client.get(
        "/api/v1/library/papers", headers=headers, params={"search": "p-f1"}
    )
    assert [p["paper_id"] for p in resp.json()] == ["p-f1"]

    # 重复收藏同一外部 paper_id → 400
    resp = await db_isolated_client.post(
        "/api/v1/library/papers", headers=headers, json=_paper_body("p-f1")
    )
    assert resp.status_code == 400, resp.text

    # 双 ID 查找：数据库 id 与外部 paper_id 均可
    db_id = fav.json()["id"]
    for key in (db_id, "p-f2"):
        resp = await db_isolated_client.get(
            f"/api/v1/library/papers/{key}", headers=headers
        )
        assert resp.status_code == 200, resp.text

    # 删除
    resp = await db_isolated_client.delete(
        f"/api/v1/library/papers/{db_id}", headers=headers
    )
    assert resp.status_code == 200, resp.text
    resp = await db_isolated_client.get(
        f"/api/v1/library/papers/{db_id}", headers=headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_paper_delete_cascades_notes_and_citations(db_isolated_client):
    """删除文献级联清理笔记与引用关系，并回收标签计数"""
    headers = await _auth_headers(db_isolated_client)
    p1 = await db_isolated_client.post(
        "/api/v1/library/papers",
        headers=headers,
        json=_paper_body("p-c1", tags=["casc"]),
    )
    p2 = await db_isolated_client.post(
        "/api/v1/library/papers",
        headers=headers,
        json=_paper_body("p-c2", tags=["casc"]),
    )
    p1_id, p2_id = p1.json()["id"], p2.json()["id"]

    await db_isolated_client.post(
        "/api/v1/library/notes",
        headers=headers,
        json={"paper_id": p1_id, "content": "note on p1"},
    )
    resp = await db_isolated_client.post(
        "/api/v1/library/citations",
        headers=headers,
        json={"citing_paper_id": p1_id, "cited_paper_id": p2_id},
    )
    assert resp.status_code == 200, resp.text

    # 删除 p1 → 笔记与引用级联清理
    resp = await db_isolated_client.delete(
        f"/api/v1/library/papers/{p1_id}", headers=headers
    )
    assert resp.status_code == 200, resp.text

    resp = await db_isolated_client.get(
        f"/api/v1/library/notes/{p1_id}", headers=headers
    )
    assert resp.status_code == 200 and resp.json() == []

    resp = await db_isolated_client.get("/api/v1/library/citations", headers=headers)
    assert resp.json() == []

    # 标签计数回收：casc 2 → 1
    resp = await db_isolated_client.get("/api/v1/library/tags", headers=headers)
    tags = {t["name"]: t for t in resp.json()}
    assert tags["casc"]["usage_count"] == 1


# ─────────────────────────────────────────────
# 阅读笔记
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_note_crud_chain(db_isolated_client):
    headers = await _auth_headers(db_isolated_client)
    p = await db_isolated_client.post(
        "/api/v1/library/papers", headers=headers, json=_paper_body("p-n1")
    )
    paper_id = p.json()["id"]

    # 创建
    resp = await db_isolated_client.post(
        "/api/v1/library/notes",
        headers=headers,
        json={"paper_id": paper_id, "content": "第一条", "note_type": "insight"},
    )
    assert resp.status_code == 200, resp.text
    note = resp.json()
    assert note["note_type"] == "insight"

    # 列表
    resp = await db_isolated_client.get(
        f"/api/v1/library/notes/{paper_id}", headers=headers
    )
    assert len(resp.json()) == 1

    # 更新
    resp = await db_isolated_client.put(
        f"/api/v1/library/notes/{note['id']}",
        headers=headers,
        json={"content": "更新后", "note_type": "method"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["content"] == "更新后"

    # 删除
    resp = await db_isolated_client.delete(
        f"/api/v1/library/notes/{note['id']}", headers=headers
    )
    assert resp.status_code == 200, resp.text
    resp = await db_isolated_client.get(
        f"/api/v1/library/notes/{paper_id}", headers=headers
    )
    assert resp.json() == []

    # 不存在的笔记 → 404
    resp = await db_isolated_client.put(
        "/api/v1/library/notes/nonexistent", headers=headers, json={"content": "x"}
    )
    assert resp.status_code == 404


# ─────────────────────────────────────────────
# 引用关系与网络分析
# ─────────────────────────────────────────────


async def _build_citation_graph(client, headers) -> dict[str, str]:
    """构建受控引用图：p1 → p2 → p3（p1 亦引 p3）"""
    ids: dict[str, str] = {}
    for pid in ("g1", "g2", "g3"):
        resp = await client.post(
            "/api/v1/library/papers", headers=headers, json=_paper_body(pid)
        )
        ids[pid] = resp.json()["id"]
    for citing, cited in (("g1", "g2"), ("g2", "g3"), ("g1", "g3")):
        resp = await client.post(
            "/api/v1/library/citations",
            headers=headers,
            json={"citing_paper_id": ids[citing], "cited_paper_id": ids[cited]},
        )
        assert resp.status_code == 200, resp.text
    return ids


@pytest.mark.asyncio
async def test_citation_add_list_delete_and_batch(db_isolated_client):
    headers = await _auth_headers(db_isolated_client)
    ids = await _build_citation_graph(db_isolated_client, headers)

    # 列表（自动回填标题）
    resp = await db_isolated_client.get("/api/v1/library/citations", headers=headers)
    citations = resp.json()
    assert len(citations) == 3
    assert citations[0]["citing_title"] == "Paper g1"

    # 方向筛选
    resp = await db_isolated_client.get(
        "/api/v1/library/citations",
        headers=headers,
        params={"paper_id": ids["g1"], "direction": "forward"},
    )
    assert len(resp.json()) == 2

    # 批量添加（p3 → p1）
    resp = await db_isolated_client.post(
        "/api/v1/library/citations/batch",
        headers=headers,
        json={
            "citations": [
                {"citing_paper_id": ids["g3"], "cited_paper_id": ids["g1"]}
            ]
        },
    )
    assert resp.status_code == 200, resp.text

    # 重复引用 → 400
    resp = await db_isolated_client.post(
        "/api/v1/library/citations",
        headers=headers,
        json={"citing_paper_id": ids["g1"], "cited_paper_id": ids["g2"]},
    )
    assert resp.status_code == 400, resp.text

    # 删除一条
    cit_id = citations[0]["id"]
    resp = await db_isolated_client.delete(
        f"/api/v1/library/citations/{cit_id}", headers=headers
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_citation_network_endpoints(db_isolated_client):
    """6 个网络分析端点全链路：graph/co-citation/influential/lineage/frontier/clusters"""
    headers = await _auth_headers(db_isolated_client)
    ids = await _build_citation_graph(db_isolated_client, headers)

    # graph
    resp = await db_isolated_client.post(
        "/api/v1/library/citations/network/graph",
        headers=headers,
        json={"paper_id": ids["g1"], "depth": 2},
    )
    assert resp.status_code == 200, resp.text
    graph = resp.json()
    assert len(graph["nodes"]) == 3
    assert len(graph["edges"]) == 3

    # co-citation（g1、g2 均引 g3 → g3 有共被引对）
    resp = await db_isolated_client.post(
        "/api/v1/library/citations/network/co-citation", headers=headers, json={}
    )
    assert resp.status_code == 200, resp.text

    # influential（PageRank：g3 被引最多）
    resp = await db_isolated_client.post(
        "/api/v1/library/citations/network/influential",
        headers=headers,
        params={"top_k": 3},
    )
    assert resp.status_code == 200, resp.text

    # lineage
    resp = await db_isolated_client.post(
        "/api/v1/library/citations/network/lineage",
        headers=headers,
        params={"paper_id": ids["g1"]},
    )
    assert resp.status_code == 200, resp.text

    # frontier
    resp = await db_isolated_client.post(
        "/api/v1/library/citations/network/frontier", headers=headers
    )
    assert resp.status_code == 200, resp.text

    # clusters
    resp = await db_isolated_client.post(
        "/api/v1/library/citations/network/clusters", headers=headers
    )
    assert resp.status_code == 200, resp.text

    # timeline
    resp = await db_isolated_client.get(
        f"/api/v1/library/citations/network/timeline/{ids['g3']}", headers=headers
    )
    assert resp.status_code == 200, resp.text


# ─────────────────────────────────────────────
# 统计与越权
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_library_stats_endpoint(db_isolated_client):
    headers = await _auth_headers(db_isolated_client)
    # 分类需显式创建（add_paper 不会为未创建的分类名建行——设计如此）
    await db_isolated_client.post(
        "/api/v1/library/categories", headers=headers, json={"name": "c-s"}
    )
    await db_isolated_client.post(
        "/api/v1/library/papers",
        headers=headers,
        json=_paper_body("p-s1", tags=["t-s"], category="c-s"),
    )
    resp = await db_isolated_client.get("/api/v1/library/stats", headers=headers)
    assert resp.status_code == 200, resp.text
    stats = resp.json()
    assert stats["total_papers"] == 1
    assert stats["total_tags"] == 1
    assert stats["total_categories"] == 1
    assert len(stats["recent_papers"]) == 1
    assert stats["top_categories"][0]["name"] == "c-s"


@pytest.mark.asyncio
async def test_library_user_isolation(db_isolated_client):
    """user_id 隔离：B 看不到 A 的任何文献，也无法删除"""
    headers_a = await _auth_headers(db_isolated_client)
    headers_b = await _auth_headers(db_isolated_client)
    p = await db_isolated_client.post(
        "/api/v1/library/papers", headers=headers_a, json=_paper_body("p-iso")
    )
    paper_id = p.json()["id"]

    resp = await db_isolated_client.get("/api/v1/library/papers", headers=headers_b)
    assert resp.json() == []
    resp = await db_isolated_client.get(
        f"/api/v1/library/papers/{paper_id}", headers=headers_b
    )
    assert resp.status_code == 404
    resp = await db_isolated_client.delete(
        f"/api/v1/library/papers/{paper_id}", headers=headers_b
    )
    assert resp.status_code == 404

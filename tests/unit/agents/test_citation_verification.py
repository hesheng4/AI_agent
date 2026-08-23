"""引用验证服务（外部实查 CrossRef/OpenAlex）单元测试

覆盖：DOI 提取、标题归一化、三级验证策略（CrossRef DOI 直查 →
CrossRef bibliographic 检索 → OpenAlex 兜底）、网络失败优雅降级、
确定性结果缓存、agent 层集成（per_reference/verified_count 等新字段）。
全程使用 httpx.MockTransport 模拟响应，不发真实网络请求。
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.agents.citation.agent import CitationAgent
from app.core.cache import cache
from app.services import citation_verification as cv


@pytest.fixture(autouse=True)
async def _clear_cache():
    """每个测试前清空缓存，避免跨用例污染"""
    await cache.clear()
    yield
    await cache.clear()


def _make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=5.0)


def _patch_client(handler):
    """把模块级 _get_client 替换为 MockTransport 客户端"""
    client = _make_client(handler)
    return patch("app.services.citation_verification._get_client", return_value=client)


# ─────────────────────────────────────────────
# 文本工具
# ─────────────────────────────────────────────


def test_extract_doi_variants():
    assert cv.extract_doi("doi:10.1000/abc.123") == "10.1000/abc.123"
    assert cv.extract_doi("https://doi.org/10.1000/abc.123") == "10.1000/abc.123"
    assert cv.extract_doi("See 10.1000/abc.123.") == "10.1000/abc.123"
    assert cv.extract_doi("(10.1000/abc.123);") == "10.1000/abc.123"
    assert cv.extract_doi("No DOI here") is None


def test_normalize_title():
    assert (
        cv._normalize_title("  [12] Deep Learning for Medical Imaging ")
        == "deeplearningformedicalimaging"
    )
    assert cv._normalize_title("- A Survey on Transformers") == "asurveyontransformers"
    assert cv._normalize_title("Attention Is All You Need!") == "attentionisallyouneed"
    # 中文标题应保留（\u4e00-\u9fff 不在剔除范围内）
    assert (
        cv._normalize_title("基于深度学习的图像分类研究")
        == "基于深度学习的图像分类研究"
    )


# ─────────────────────────────────────────────
# 策略 1：CrossRef DOI 直查
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_doi_hit():
    ref = "Smith A. (2019). Some Title. doi:10.1234/abc"

    def handler(request):
        assert "/works/" in request.url.path  # DOI 直查路径
        return httpx.Response(
            200,
            json={
                "message": {
                    "title": ["Some Title"],
                    "DOI": "10.1234/abc",
                    "author": [{"given": "Alice", "family": "Smith"}],
                    "issued": {"date-parts": [[2020]]},
                }
            },
        )

    with _patch_client(handler):
        result = await cv.verify_reference(ref)

    assert result.status == "verified"
    assert result.source == "crossref_doi"
    assert result.matched_doi == "10.1234/abc"
    assert result.matched_title == "Some Title"
    assert result.matched_year == 2020
    assert "Alice Smith" in result.matched_authors
    # 引用年份(2019)与匹配年份(2020)不符，应产生提示
    assert any("年份不符" in i for i in result.issues)


@pytest.mark.asyncio
async def test_verify_doi_not_found():
    def handler(request):
        return httpx.Response(404)

    with _patch_client(handler):
        result = await cv.verify_reference("10.9999/nonexistent.123")

    assert result.status == "not_found"
    assert result.source == "crossref_doi"


# ─────────────────────────────────────────────
# 策略 2：CrossRef bibliographic 检索（回归：items 内层即 work，无 message 包装）
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_crossref_query_title_match():
    ref = "The Magic Paper Title"

    def handler(request):
        assert "query.bibliographic" in str(request.url)
        return httpx.Response(
            200,
            json={
                "message": {
                    "items": [
                        {
                            "title": ["The Magic Paper Title"],
                            "DOI": "10.1234/def",
                            "author": [],
                            "issued": {"date-parts": [[2020]]},
                        }
                    ]
                }
            },
        )

    with _patch_client(handler):
        result = await cv.verify_reference(ref)

    assert result.status == "verified"
    assert result.source == "crossref_query"
    assert result.matched_doi == "10.1234/def"


@pytest.mark.asyncio
async def test_verify_crossref_query_weak_match_uncertain():
    # 完整引用文本（含作者/年份/期刊）只与候选标题子串匹配 → uncertain
    ref = "Smith A. (2020). The Magic Paper Title. Journal of X."

    def handler(request):
        return httpx.Response(
            200,
            json={
                "message": {
                    "items": [
                        {
                            "title": ["The Magic Paper Title"],
                            "DOI": "10.1234/def",
                            "author": [],
                            "issued": {"date-parts": [[2020]]},
                        }
                    ]
                }
            },
        )

    with _patch_client(handler):
        result = await cv.verify_reference(ref)

    assert result.status == "uncertain"
    assert result.source == "crossref_query"
    assert any("部分匹配" in i for i in result.issues)


# ─────────────────────────────────────────────
# 策略 3：OpenAlex 兜底
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_openalex_fallback():
    ref = "Paper Only In OpenAlex"

    def handler(request):
        if "openalex" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "title": "Paper Only In OpenAlex",
                            "doi": "https://doi.org/10.1234/oa",
                            "publication_year": 2021,
                            "authorships": [
                                {"author": {"display_name": "Bob Lee"}}
                            ],
                        }
                    ]
                },
            )
        # CrossRef 检索返回空结果
        return httpx.Response(200, json={"message": {"items": []}})

    with _patch_client(handler):
        result = await cv.verify_reference(ref)

    assert result.status == "verified"
    assert result.source == "openalex"
    assert result.matched_doi == "10.1234/oa"


# ─────────────────────────────────────────────
# 降级：网络失败 / HTTP 429 不阻断流程
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_all_sources_fail_degrades_to_uncertain():
    def handler(request):
        raise httpx.ConnectError("network down", request=request)

    with _patch_client(handler):
        result = await cv.verify_reference("Some Ref 2020")

    assert result.status == "uncertain"
    assert result.error == "all external sources failed"


@pytest.mark.asyncio
async def test_verify_http_429_degrades_to_uncertain():
    def handler(request):
        return httpx.Response(429)

    with _patch_client(handler):
        result = await cv.verify_reference("Some Ref 2020")

    assert result.status == "uncertain"
    assert result.error == "all external sources failed"


# ─────────────────────────────────────────────
# 缓存：仅缓存确定性结果（verified / not_found）
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_reference_cache_hit_skips_network():
    calls: list[str] = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "message": {
                    "items": [
                        {
                            "title": ["Cache Me"],
                            "DOI": "10.1234/cache",
                            "issued": {"date-parts": [[2020]]},
                        }
                    ]
                }
            },
        )

    with _patch_client(handler):
        r1 = await cv.verify_reference("Cache Me")
        r2 = await cv.verify_reference("Cache Me")

    assert r1.status == "verified"
    assert r2.status == "verified"
    assert len(calls) == 1  # 第二次命中缓存，未发网络请求


@pytest.mark.asyncio
async def test_uncertain_result_not_cached():
    calls: list[str] = []

    def handler(request):
        calls.append(str(request.url))
        raise httpx.ConnectError("network down", request=request)

    with _patch_client(handler):
        await cv.verify_reference("Some Ref 2020")
        await cv.verify_reference("Some Ref 2020")

    # uncertain 不缓存，每次重查；单次调用会依次请求 CrossRef + OpenAlex 两个源
    assert len(calls) == 4


# ─────────────────────────────────────────────
# 批量验证：受限并发，逐条独立
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_references_batch_independent():
    def handler(request):
        if "openalex" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "title": "OA Paper",
                            "doi": "https://doi.org/10.1234/oa",
                            "publication_year": 2020,
                        }
                    ]
                },
            )
        return httpx.Response(200, json={"message": {"items": []}})

    with _patch_client(handler):
        results = await cv.verify_references(["OA Paper", "Other Paper"])

    assert isinstance(results, list)
    assert len(results) == 2
    assert all(isinstance(r, cv.ReferenceVerification) for r in results)
    assert results[0].status == "verified"
    assert results[1].status == "not_found"  # 无匹配，逐条独立判定


# ─────────────────────────────────────────────
# Agent 层集成：外部实查结果注入返回与 LLM prompt
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_agent_verify_citations_includes_external_results():
    agent = CitationAgent()
    fake = [
        cv.ReferenceVerification(reference="r1", status="verified", matched_title="T"),
        cv.ReferenceVerification(
            reference="r2",
            status="not_found",
            issues=["未在 CrossRef 找到匹配文献"],
        ),
    ]
    captured: dict[str, str] = {}

    async def fake_llm(prompt, *args, **kwargs):
        captured["prompt"] = prompt
        return "ok"

    with patch.object(agent, "call_llm", new=AsyncMock(side_effect=fake_llm)), patch(
        "app.agents.citation.agent.verify_references", new=AsyncMock(return_value=fake)
    ):
        result = await agent.verify_citations(
            {"content": "x", "references": ["r1", "r2"]}
        )

    assert result["verified_count"] == 1
    assert result["suspicious_count"] == 1
    assert len(result["per_reference"]) == 2
    assert result["total_references"] == 2
    # LLM prompt 应注入外部实查摘要，并提示重点复核 not_found 条目
    assert "外部实查结果" in captured["prompt"]
    assert "not_found" in captured["prompt"]


@pytest.mark.asyncio
async def test_agent_verify_citations_degrades_without_external():
    """外部实查抛异常时降级为纯 LLM 判断，不阻断"""
    agent = CitationAgent()

    async def fake_llm(prompt, *args, **kwargs):
        return "ok"

    with patch.object(agent, "call_llm", new=AsyncMock(side_effect=fake_llm)), patch(
        "app.agents.citation.agent.verify_references",
        new=AsyncMock(side_effect=RuntimeError("network down")),
    ):
        result = await agent.verify_citations(
            {"content": "x", "references": ["r1"]}
        )

    assert result["verified_count"] == 0
    assert result["suspicious_count"] == 0
    assert result["per_reference"] == []
    assert result["total_references"] == 1

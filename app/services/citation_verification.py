"""引用验证服务 — 外部实查（CrossRef + OpenAlex）

三步策略（按优先级）：
1. 引用含 DOI → CrossRef `works/{doi}` 直查（最准确）
2. 无 DOI → CrossRef bibliographic 检索 + 归一化标题/年份匹配
3. 兜底 → OpenAlex works 检索 + 归一化标题/年份匹配

工程特性：
- 双后端缓存（键=归一化标题哈希，默认 TTL 24h，仅缓存确定性结果）
- 受限并发（信号量，默认 4）+ 礼貌池 mailto（CrossRef/OpenAlex 免费无 key）
- 网络失败/超时优雅降级为 `uncertain`，绝不阻断主流程

对应 P0-1 优化：把 citation 的"纯 LLM 引用验证"升级为"外部实查 +
LLM 论断判断"，幻觉引用（不存在的 DOI / 找不到的标题）被明确打标。
"""

import asyncio
import hashlib
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import httpx

from app.config import get_settings
from app.core.cache import cache
from app.utils.logger import get_logger

logger = get_logger("citation_verification")
settings = get_settings()

CROSSREF_WORKS = "https://api.crossref.org/works"
OPENALEX_WORKS = "https://api.openalex.org/works"

# DOI 形如 10.<4-9位数字>/<后缀>，后缀可含字母数字与 . - _ ( ) / : 等
DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s]+")
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")

# 标题匹配阈值：>= MATCH_STRONG 判 verified；>= MATCH_WEAK 判 uncertain
MATCH_STRONG = 0.75
MATCH_WEAK = 0.30

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """懒初始化共享 AsyncClient（httpx 连接池复用）"""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=settings.CITATION_VERIFY_TIMEOUT)
    return _client


async def close() -> None:
    """关闭共享 HTTP 客户端（应用关闭时调用）"""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


# ─────────────────────────────────────────────
# 文本工具
# ─────────────────────────────────────────────


def extract_doi(reference: str) -> str | None:
    """从引用文本提取 DOI，兼容 `doi:` 前缀与 `https://doi.org/` 形式"""
    m = DOI_RE.search(reference)
    if not m:
        return None
    return m.group(0).rstrip(".,;)]}")


def _normalize_title(text: str) -> str:
    """标题归一化：去编号前缀/引号/标点/大小写/空白，中英文均可"""
    t = re.sub(r"^\s*(?:\[\d+\]|\[\w+\]|[-–—]\s*|\d+[.)]?\s*)", "", text.strip())
    t = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", t.lower())
    return t


def _hash_ref(reference: str) -> str:
    return hashlib.sha256(_normalize_title(reference).encode()).hexdigest()[:16]


def _title_score(candidate: str, norm_query: str) -> float:
    """标题匹配度：完全相等 1.0；子串匹配按长度比打折

    norm_query 内部会再归一化一次，兼容未预归一化的调用方。
    """
    norm_cand = _normalize_title(candidate)
    norm_query = _normalize_title(norm_query)
    if not norm_cand or not norm_query:
        return 0.0
    if norm_cand == norm_query:
        return 1.0
    if norm_query in norm_cand or norm_cand in norm_query:
        short, long = sorted((norm_cand, norm_query), key=len)
        return 0.8 * len(short) / len(long)
    return 0.0


def _doi_from_url(value: str | None) -> str | None:
    """OpenAlex 的 doi 字段是完整 URL，取出裸 DOI"""
    if not value:
        return None
    return value.split("doi.org/", 1)[-1].lower()


def _year_from_reference(reference: str) -> int | None:
    m = YEAR_RE.search(reference)
    return int(m.group(0)) if m else None


def _crossref_authors(message: dict) -> list[str]:
    out = []
    for a in message.get("author") or []:
        name = " ".join(x for x in (a.get("given"), a.get("family")) if x)
        if name:
            out.append(name)
    return out


def _crossref_year(message: dict) -> int | None:
    for key in ("published-print", "published-online", "issued", "created"):
        parts = (message.get(key) or {}).get("date-parts") or [[]]
        for p in parts:
            if p and p[0]:
                return int(p[0])
    return None


def _year_issue(reference: str, matched_year: int | None) -> str | None:
    """引用文本中的年份与匹配结果不一致时给出提示"""
    if matched_year is None:
        return None
    ref_year = _year_from_reference(reference)
    if ref_year and ref_year != matched_year:
        return f"年份不符：引用 {ref_year}，匹配到 {matched_year}"
    return None


# ─────────────────────────────────────────────
# 数据模型
# ─────────────────────────────────────────────


@dataclass
class ReferenceVerification:
    """单条引用的外部核查结果"""

    reference: str
    status: str  # verified / not_found / uncertain
    matched_doi: str | None = None
    matched_title: str | None = None
    matched_year: int | None = None
    matched_authors: list[str] = field(default_factory=list)
    source: str | None = None  # crossref_doi / crossref_query / openalex
    issues: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference": self.reference,
            "status": self.status,
            "matched_doi": self.matched_doi,
            "matched_title": self.matched_title,
            "matched_year": self.matched_year,
            "matched_authors": list(self.matched_authors),
            "source": self.source,
            "issues": list(self.issues),
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReferenceVerification:
        return cls(**data)


# ─────────────────────────────────────────────
# 三级验证策略
# ─────────────────────────────────────────────


async def _crossref_doi(
    client: httpx.AsyncClient, reference: str, doi: str
) -> ReferenceVerification | None:
    """策略 1：CrossRef DOI 直查。网络失败返回 None（降级到检索）。"""
    try:
        resp = await client.get(
            f"{CROSSREF_WORKS}/{quote(doi, safe='')}",
            params={"mailto": settings.CROSSREF_MAILTO},
        )
    except httpx.HTTPError as e:
        logger.warning("CrossRef DOI 查询失败(%s): %s", doi, e)
        return None
    if resp.status_code == 404:
        return ReferenceVerification(
            reference=reference,
            status="not_found",
            source="crossref_doi",
            issues=["DOI 未在 CrossRef 登记"],
        )
    if resp.status_code != 200:
        return None
    msg = resp.json().get("message", {})
    title = (msg.get("title") or [""])[0]
    year = _crossref_year(msg)
    issue = _year_issue(reference, year)
    return ReferenceVerification(
        reference=reference,
        status="verified",
        matched_doi=doi,
        matched_title=title,
        matched_year=year,
        matched_authors=_crossref_authors(msg),
        source="crossref_doi",
        issues=[issue] if issue else [],
    )


async def _crossref_query(
    client: httpx.AsyncClient, reference: str
) -> ReferenceVerification | None:
    """策略 2：CrossRef bibliographic 检索 + 标题/年份匹配。网络失败返回 None。"""
    try:
        resp = await client.get(
            CROSSREF_WORKS,
            params={
                "query.bibliographic": reference,
                "rows": "3",
                "mailto": settings.CROSSREF_MAILTO,
            },
        )
    except httpx.HTTPError as e:
        logger.warning("CrossRef 检索失败: %s", e)
        return None
    if resp.status_code != 200:
        return None
    norm = _normalize_title(reference)
    items = (resp.json().get("message") or {}).get("items") or []
    best, best_score = None, 0.0
    for item in items:
        # CrossRef /works 列表接口的 items 内层直接就是 work 对象
        # （含 title/DOI/author/issued），并无嵌套 "message" 包装
        msg = item
        title = (msg.get("title") or [""])[0]
        score = _title_score(title, norm)
        if score > best_score:
            best, best_score = msg, score
    if best is None:
        return ReferenceVerification(
            reference=reference,
            status="not_found",
            source="crossref_query",
            issues=["未在 CrossRef 找到匹配文献"],
        )
    title = (best.get("title") or [""])[0]
    year = _crossref_year(best)
    issue = _year_issue(reference, year)
    if best_score >= MATCH_STRONG:
        return ReferenceVerification(
            reference=reference,
            status="verified",
            matched_doi=_doi_from_url(best.get("DOI")),
            matched_title=title,
            matched_year=year,
            matched_authors=_crossref_authors(best),
            source="crossref_query",
            issues=[issue] if issue else [],
        )
    if best_score >= MATCH_WEAK:
        return ReferenceVerification(
            reference=reference,
            status="uncertain",
            matched_title=title,
            matched_year=year,
            source="crossref_query",
            issues=["标题仅部分匹配，请人工复核"],
        )
    return ReferenceVerification(
        reference=reference,
        status="not_found",
        source="crossref_query",
        issues=["未在 CrossRef 找到匹配文献"],
    )


async def _openalex_query(
    client: httpx.AsyncClient, reference: str
) -> ReferenceVerification | None:
    """策略 3：OpenAlex works 检索 + 标题/年份匹配（免费无 key 兜底源）。"""
    try:
        resp = await client.get(
            OPENALEX_WORKS,
            params={
                "search": reference,
                "per-page": "3",
                "mailto": settings.OPENALEX_MAILTO,
            },
        )
    except httpx.HTTPError as e:
        logger.warning("OpenAlex 检索失败: %s", e)
        return None
    if resp.status_code != 200:
        return None
    norm = _normalize_title(reference)
    results = resp.json().get("results") or []
    best, best_score = None, 0.0
    for item in results:
        title = item.get("title") or ""
        score = _title_score(title, norm)
        if score > best_score:
            best, best_score = item, score
    if best is None:
        return ReferenceVerification(
            reference=reference,
            status="not_found",
            source="openalex",
            issues=["未在 OpenAlex 找到匹配文献"],
        )
    title = best.get("title") or ""
    year = best.get("publication_year")
    authors = [
        a.get("author", {}).get("display_name", "")
        for a in (best.get("authorships") or [])
    ]
    authors = [x for x in authors if x]
    issue = _year_issue(reference, year)
    if best_score >= MATCH_STRONG:
        return ReferenceVerification(
            reference=reference,
            status="verified",
            matched_doi=_doi_from_url(best.get("doi")),
            matched_title=title,
            matched_year=year,
            matched_authors=authors,
            source="openalex",
            issues=[issue] if issue else [],
        )
    if best_score >= MATCH_WEAK:
        return ReferenceVerification(
            reference=reference,
            status="uncertain",
            matched_title=title,
            matched_year=year,
            source="openalex",
            issues=["标题仅部分匹配，请人工复核"],
        )
    return ReferenceVerification(
        reference=reference,
        status="not_found",
        source="openalex",
        issues=["未在 OpenAlex 找到匹配文献"],
    )


async def _verify_one(
    client: httpx.AsyncClient, reference: str
) -> ReferenceVerification:
    """三级策略串联：DOI 直查 → CrossRef 检索 → OpenAlex 兜底"""
    doi = extract_doi(reference)
    if doi:
        result = await _crossref_doi(client, reference, doi)
        if result is not None:
            return result
    # CrossRef 检索明确未匹配（not_found）时不短路返回，继续 OpenAlex 兜底
    crossref_result = await _crossref_query(client, reference)
    if crossref_result is not None and crossref_result.status != "not_found":
        return crossref_result
    openalex_result = await _openalex_query(client, reference)
    if openalex_result is not None:
        return openalex_result
    # 全部源均不可用：优先保留 CrossRef 的明确结论，否则标记 uncertain
    if crossref_result is not None:
        return crossref_result
    return ReferenceVerification(
        reference=reference,
        status="uncertain",
        issues=["外部验证服务不可用，请人工复核"],
        error="all external sources failed",
    )


# ─────────────────────────────────────────────
# 对外接口（带缓存 + 受限并发）
# ─────────────────────────────────────────────


async def verify_reference(
    reference: str, semaphore: asyncio.Semaphore | None = None
) -> ReferenceVerification:
    """验证单条引用：先查缓存，未命中走三级策略，确定性结果写回缓存"""
    key = f"citation:verify:{_hash_ref(reference)}"
    cached = await cache.get(key)
    if cached is not None:
        return ReferenceVerification.from_dict(cached)

    if semaphore is not None:
        async with semaphore:
            result = await _verify_one(_get_client(), reference)
    else:
        result = await _verify_one(_get_client(), reference)

    # 只缓存确定性结果（verified / not_found），uncertain 每次重查
    if result.status in ("verified", "not_found"):
        await cache.set(key, result.to_dict(), settings.CITATION_VERIFY_CACHE_TTL)
    return result


async def verify_references(references: list[str]) -> list[ReferenceVerification]:
    """批量验证引用：受限并发聚合，逐条独立失败互不影响"""
    if not references:
        return []
    sem = asyncio.Semaphore(settings.CITATION_VERIFY_CONCURRENCY)
    return list(await asyncio.gather(*(verify_reference(r, sem) for r in references)))

"""E2E：LLM 生成类端点 HTTP 冒烟（credibility-convergence 覆盖缺口清偿）

背景：覆盖分析发现 research 域 21 个路由模块多数零 HTTP 层覆盖。
本文件以统一 FakeLLM 桩（零外网）逐一打通各模块的主端点，
断言 200 + success；统计/文件型子路径由专属测试文件覆盖。

不覆盖（属文件生成/依赖缺失域，另测）：paper2ppt、paper_to_patent、figure
（matplotlib 可选依赖）；review-loop（多轮循环依赖 LLM 输出解析，
进程内单测已覆盖）。
"""

import uuid

import pytest

pytestmark = pytest.mark.e2e

_PASSWORD = "Passw0rd!e2e"

_LONG_CONTENT = (
    "# Introduction\n本研究提出一种面向医学影像的深度学习方法。"
    "我们在三个公开数据集上进行了系统实验，结果表明所提方法在多项指标上"
    "显著优于现有基线。方法部分详述网络结构与训练细节。\n" * 3
)


class FakeLLM:
    """最小 LLM 桩：generate 返回固定文本，支持流式"""

    def __init__(self, response: str = "桩输出：这是模拟的 LLM 回复。"):
        self._response = response
        self.calls = 0

    async def generate(self, *args, **kwargs):
        self.calls += 1
        return self._response

    async def generate_stream(self, *args, **kwargs):
        self.calls += 1
        yield self._response


@pytest.fixture
def stub_llm_class(monkeypatch):
    """类级打桩：patch LLMClient.generate/generate_stream。

    部分 agent（reader/reviewer/response）在路由内每请求新建实例，
    打实例属性无法命中；类级打桩对单例与新建实例一律生效。
    """
    from app.utils.llm import LLMClient

    fake = FakeLLM()
    monkeypatch.setattr(LLMClient, "generate", fake.generate)
    monkeypatch.setattr(LLMClient, "generate_stream", fake.generate_stream)
    return fake


async def _auth_headers(client) -> dict[str, str]:
    token = uuid.uuid4().hex
    email = f"llm_{token[:12]}@example.com"
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": f"u_{token[:10]}",
            "password": _PASSWORD,
        },
    )
    assert resp.status_code == 200, resp.text
    user_id = resp.json()["id"]
    # writing/literature 路由在代理之前有 LLM Key 预检 → 给测试用户配 Key
    import app.core.database as dbmod
    from sqlalchemy import update

    from app.models.user import User

    async with dbmod.async_session() as session:
        await session.execute(
            update(User).where(User.id == user_id).values(api_key="sk-test-stub")
        )
        await session.commit()
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": _PASSWORD},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ─────────────────────────────────────────────
# literature（检索需同时打桩外网 tools）
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_literature_search_over_http(db_isolated_client, monkeypatch, stub_llm_class):
    from app.agents.literature import get_literature_agent

    agent = get_literature_agent()
    if hasattr(agent, "tools_handler") and hasattr(agent.tools_handler, "search_papers"):

        async def _fake_search(query, filters=None):  # noqa: ANN001
            return [
                {
                    "id": "smoke-1",
                    "title": "Smoke Search Paper",
                    "authors": ["A"],
                    "abstract": "abstract",
                    "year": 2024,
                }
            ]

        monkeypatch.setattr(agent.tools_handler, "search_papers", _fake_search)

    headers = await _auth_headers(db_isolated_client)
    resp = await db_isolated_client.post(
        "/api/v1/literature/search",
        headers=headers,
        json={"query": "deep learning medical imaging"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "success"
    assert body["papers"] and body["papers"][0]["title"] == "Smoke Search Paper"


@pytest.mark.asyncio
async def test_literature_summarize_over_http(db_isolated_client, monkeypatch, stub_llm_class):
    from app.agents.literature import get_literature_agent

    headers = await _auth_headers(db_isolated_client)
    resp = await db_isolated_client.post(
        "/api/v1/literature/summarize",
        headers=headers,
        json={"papers": [{"title": "Smoke Paper", "abstract": _LONG_CONTENT}]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "success"


# ─────────────────────────────────────────────
# writing / reviewer / response / reader
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_writing_outline_over_http(db_isolated_client, monkeypatch, stub_llm_class):
    from app.agents.writing import get_writing_agent

    headers = await _auth_headers(db_isolated_client)
    resp = await db_isolated_client.post(
        "/api/v1/writing/outline",
        headers=headers,
        json={"topic": "深度学习在医学影像中的应用"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "success"


@pytest.mark.asyncio
async def test_reviewer_assess_and_quick_check(db_isolated_client, monkeypatch, stub_llm_class):
    from app.agents.reviewer.agent import ReviewerAgent

    headers = await _auth_headers(db_isolated_client)
    resp = await db_isolated_client.post(
        "/api/v1/reviewer/assess",
        headers=headers,
        json={"content": _LONG_CONTENT, "paper_type": "research"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "success"

    resp = await db_isolated_client.post(
        "/api/v1/reviewer/quick-check",
        headers=headers,
        json={"content": _LONG_CONTENT},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "success"


@pytest.mark.asyncio
async def test_response_draft_audit_revise(db_isolated_client, monkeypatch, stub_llm_class):
    from app.agents.response.agent import ResponseAgent

    headers = await _auth_headers(db_isolated_client)
    resp = await db_isolated_client.post(
        "/api/v1/response/draft",
        headers=headers,
        json={"reviewer_comments": ["方法部分不够详细", "缺少消融实验"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "success"

    resp = await db_isolated_client.post(
        "/api/v1/response/audit",
        headers=headers,
        json={"response_content": "感谢审稿人意见，我们补充如下……"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "success"

    resp = await db_isolated_client.post(
        "/api/v1/response/revise",
        headers=headers,
        json={"response_content": "原回复", "feedback": "语气再礼貌些"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "success"


@pytest.mark.asyncio
async def test_reader_read_full(db_isolated_client, monkeypatch, stub_llm_class):
    from app.agents.reader.agent import ReaderAgent

    headers = await _auth_headers(db_isolated_client)
    resp = await db_isolated_client.post(
        "/api/v1/reader/read-full",
        headers=headers,
        json={"content": _LONG_CONTENT, "source_format": "pasted-text"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["paper_md"]


# ─────────────────────────────────────────────
# citation / cover / methods / polishing / stats
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_citation_add_verify_format(db_isolated_client, monkeypatch, stub_llm_class):
    from app.agents.citation import get_citation_agent

    headers = await _auth_headers(db_isolated_client)

    resp = await db_isolated_client.post(
        "/api/v1/citation/add",
        headers=headers,
        json={"content": _LONG_CONTENT, "journal_scope": "general"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "success"

    resp = await db_isolated_client.post(
        "/api/v1/citation/verify",
        headers=headers,
        json={"content": _LONG_CONTENT, "references": ["Ref 1 (2020)"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "success"

    resp = await db_isolated_client.post(
        "/api/v1/citation/format",
        headers=headers,
        json={"references": ["Ref 1 (2020)"], "style": "nature"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "success"


@pytest.mark.asyncio
async def test_single_agent_endpoints_smoke(db_isolated_client, monkeypatch, stub_llm_class):
    """cover / methods / polishing / stats / submission-package 五个单端点模块"""
    from app.agents.cover import get_cover_agent
    from app.agents.methods import MethodsAgent
    from app.agents.polishing import PolishingAgent
    from app.agents.stats import StatsAgent
    from app.agents.submission_package import SubmissionPackageAgent


    headers = await _auth_headers(db_isolated_client)
    cases = [
        ("/api/v1/cover/", {"task": "draft", "title": "T", "abstract": "A"}),
        ("/api/v1/methods/", {"task": "audit", "content": _LONG_CONTENT}),
        ("/api/v1/polishing/", {"task": "polish", "content": _LONG_CONTENT}),
        ("/api/v1/stats/", {"task": "audit", "content": _LONG_CONTENT}),
        (
            "/api/v1/submission-package/",
            {"task": "checklist", "abstract": _LONG_CONTENT},
        ),
    ]
    for path, payload in cases:
        resp = await db_isolated_client.post(path, headers=headers, json=payload)
        assert resp.status_code == 200, f"{path}: {resp.text}"
        # 五个模块响应均为 {result: {...}} 形状（无顶层 status）
        assert "result" in resp.json(), f"{path}: {resp.text}"


@pytest.mark.asyncio
async def test_data_availability_three_endpoints(db_isolated_client, monkeypatch, stub_llm_class):
    from app.agents.data_agent import get_data_availability_agent

    headers = await _auth_headers(db_isolated_client)

    resp = await db_isolated_client.post(
        "/api/v1/data-availability/generate-statement",
        headers=headers,
        json={"data_description": "小鼠肿瘤体积测量数据"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "success"

    resp = await db_isolated_client.post(
        "/api/v1/data-availability/audit-statement",
        headers=headers,
        json={"statement": "本文数据已上传至公共仓库。"},
    )
    assert resp.status_code == 200, resp.text

    resp = await db_isolated_client.post(
        "/api/v1/data-availability/select-repository",
        headers=headers,
        json={"data_type": "imaging"},
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_experiment_llm_endpoints(db_isolated_client, monkeypatch, stub_llm_class):
    """design/optimize/predict 走 LLM 桩（statistical-test/power-analysis 另测）"""
    from app.agents.experiment import get_experiment_agent

    headers = await _auth_headers(db_isolated_client)

    resp = await db_isolated_client.post(
        "/api/v1/experiment/design",
        headers=headers,
        json={"research_goal": "验证药物 A 对肿瘤的抑制效果", "variables": ["剂量"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "success"

    resp = await db_isolated_client.post(
        "/api/v1/experiment/optimize",
        headers=headers,
        json={
            "historical_data": [{"dose": 1, "score": 0.5}, {"dose": 2, "score": 0.8}],
            "target_metric": "score",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "success"

    resp = await db_isolated_client.post(
        "/api/v1/experiment/predict",
        headers=headers,
        json={
            "params": {"dose": 3},
            "historical_data": [{"dose": 1, "score": 0.5}, {"dose": 2, "score": 0.8}],
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "success"

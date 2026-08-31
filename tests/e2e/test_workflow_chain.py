"""E2E 工作流链路：文献检索 → 写作 → 润色 → 模拟审稿 → 审稿回复（模板驱动）

意图契约（红先行可执行规格）：
- POST /orchestrate 支持显式 ``workflow_template``（Q4）；缺省时零回归。
- 模板即契约（Q3）：write_from_scratch / revise 模板的每步 (agent, task)
  必须能被目标 Agent 实际执行——模板任务名须与 Agent 任务分派表一致
  （writing.generate / reviewer.assess / citation.verify-citations）。
- 上游结果沿边真实流入下游（Q8 边级判定）：判定依据是「注入值原文出现在
  下游 Agent 的 LLM prompt」（FakeLLM 调用日志），确定性 Agent 直接读结果字段；
  「请求里存在该字段」永不算通过。
- 全程零外网：所有 Agent 的 LLM 换成脚本化 FakeLLM，文献检索打桩。

红基线（2026-08-31 实测：9 红 / 1 绿）：
- 唯一绿：test_template_step_task_names_dispatchable——契约目标名
  （writing.generate / reviewer.assess / citation.verify-citations）
  在现有 Agent 分派表中存在，断链的是模板引用而非 handler。
- 零回归用例也是红：decompose_task 不重写 task（planner.py 原样
  透传自然语言任务），连「文献检索」单 Agent 编排都 500
  （Agent[literature] 未知任务类型: 文献检索）——比原预估更严重。
修复落地后全绿并作为永久回归（make test 门禁）。
"""

import json
import uuid
from typing import Any

import pytest

from app.agents.coordinator import get_coordinator_agent
from app.agents.coordinator.planner import (
    AGENT_DEPENDENCIES,
    WORKFLOW_TEMPLATES,
)

pytestmark = pytest.mark.e2e

# ─────────────────────────────────────────────
# 可观察标记（FakeLLM 返回内容携带，用于边级判定）
# ─────────────────────────────────────────────

DRAFT_MARKER = "DRAFT_SECTION_e2e_" + uuid.uuid4().hex[:8]
REVISED_MARKER = "REVISED_CONTENT_e2e_" + uuid.uuid4().hex[:8]
ISSUE_MARKER = "ISSUE_GAP_e2e_" + uuid.uuid4().hex[:8]
ROUTE_AGENTS_MARKER = ["literature"]

_ROUTING_SYSTEM_MARKER = "你是研究Agent平台的路由器"
_REVISE_PROMPT_MARKER = "学术论文修订专家"
_STRUCTURED_MARKER = "improvement_suggestions"
_SCORE_MARKER = "量化评分"
_GENERATE_PROMPT_MARKER = "请根据以下大纲"


def _paper_title_marker() -> str:
    return "MarkerPaper_" + uuid.uuid4().hex[:8]


# ─────────────────────────────────────────────
# FakeLLM：脚本化 LLM，按 prompt 标记分派罐头响应并记录全部调用
# ─────────────────────────────────────────────


class FakeLLM:
    """替换 LLMClient：generate/generate_with_usage/chat 同签名，零网络。"""

    def __init__(self, route_agents: list[str] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.route_agents = (
            route_agents if route_agents is not None else ROUTE_AGENTS_MARKER
        )

    # 供测试代码反查：哪个 Agent 的哪次调用包含指定文本
    def prompts_for(self, agent: str) -> str:
        return "\n".join(
            f"{c.get('prompt')}\n{c.get('system_prompt') or ''}"
            for c in self.calls
            if c["agent"] == agent
        )

    def _record(self, agent: str, prompt: str, system_prompt: str | None) -> None:
        self.calls.append(
            {"agent": agent, "prompt": prompt, "system_prompt": system_prompt}
        )

    def _respond(self, agent: str, prompt: str, system_prompt: str | None) -> str:
        self._record(agent, prompt, system_prompt)
        text = f"{system_prompt or ''}\n{prompt}"

        if _ROUTING_SYSTEM_MARKER in text:
            return json.dumps({"agents": self.route_agents}, ensure_ascii=False)
        # revise 标记须先于结构化评审标记判定（修订 prompt 也含评审语境）
        if _REVISE_PROMPT_MARKER in text:
            return json.dumps(
                {
                    "revised_content": (
                        f"修订后的正文（{REVISED_MARKER}）：方法与结果均已补齐。"
                    ),
                    "change_log": [
                        {"issue": ISSUE_MARKER, "location": "结果", "change": "补齐"}
                    ],
                    "skipped": [],
                },
                ensure_ascii=False,
            )
        if _STRUCTURED_MARKER in text:
            return json.dumps(
                {
                    "strengths": [{"text": "研究问题清晰，链路完整。"}],
                    "improvement_suggestions": [
                        {
                            "issue": ISSUE_MARKER,
                            "location": "结果",
                            "suggestion": "补充对照组统计检验。",
                            "severity": "major",
                            "category": "methodological",
                        }
                    ],
                },
                ensure_ascii=False,
            )
        if _SCORE_MARKER in text:
            return json.dumps(
                {
                    "overall": 7,
                    "originality": 7,
                    "importance": 7,
                    "readership": 7,
                    "soundness": 7,
                    "readability": 8,
                }
            )
        if _GENERATE_PROMPT_MARKER in text:
            return f"{DRAFT_MARKER}\n本段为生成草稿，供后续润色与审稿链路消费。"
        return f"OK[{agent}]：任务已处理（FakeLLM 占位响应）。"

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        use_cache: bool = True,
        user_api_key: str | None = None,
        user_api_base_url: str | None = None,
        user_api_model: str | None = None,
    ) -> str:
        return self._respond(self._agent_name, prompt, system_prompt)

    async def generate_with_usage(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        prompt = kwargs.get("prompt") or (args[0] if args else "")
        system_prompt = kwargs.get("system_prompt") or (
            args[1] if len(args) > 1 else None
        )
        content = self._respond(self._agent_name, prompt, system_prompt)
        return {"content": content, "usage": {"prompt_tokens": 1, "total_tokens": 1}}

    async def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        last_user = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"), ""
        )
        return self._respond(self._agent_name, last_user, None)


# ─────────────────────────────────────────────
# 打桩协调器：全部 Agent 挂 FakeLLM + 文献检索打桩
# ─────────────────────────────────────────────


@pytest.fixture
async def fake_coordinator(monkeypatch):
    """进程内协调器：FakeLLM 全量替换 + literature 检索打桩，零外网。"""
    coordinator = get_coordinator_agent()
    fakes: dict[str, FakeLLM] = {}

    from app.agents.registry import get_agent_registry

    names = sorted(get_agent_registry())

    # 模板契约涉及的 Agent 必须全部在册（也覆盖修复后新增的名字）
    template_agents = {
        step["agent"]
        for tpl in ("write_from_scratch", "revise")
        for step in WORKFLOW_TEMPLATES[tpl]["steps"]
    }
    for name in sorted(template_agents | set(names)):
        try:
            agent = coordinator.get_agent(name)
        except Exception:
            continue
        if agent is None:
            continue
        fake = FakeLLM()
        fake._agent_name = name
        fakes[name] = fake
        if hasattr(agent, "llm"):
            monkeypatch.setattr(agent, "llm", fake)

    coord_fake = FakeLLM()
    coord_fake._agent_name = "coordinator"
    fakes["coordinator"] = coord_fake
    monkeypatch.setattr(coordinator, "llm", coord_fake)

    # 唯一外网点：文献检索打桩（标题带唯一标记，供下游 prompt 判定）
    literature = coordinator.get_agent("literature")
    title = _paper_title_marker()
    canned_papers = [
        {
            "id": "paper_e2e_1",
            "title": title,
            "authors": ["Author A"],
            "abstract": "Abstract body for e2e chain.",
            "year": 2024,
            "journal": "Journal E2E",
        }
    ]

    async def _fake_search(query, filters=None):  # noqa: ANN001
        return canned_papers

    monkeypatch.setattr(
        literature.tools_handler, "search_papers", _fake_search, raising=True
    )

    yield {"coordinator": coordinator, "fakes": fakes, "paper_title": title}

    # 清理被污染的实例缓存（lru_cache 单例跨用例复用）
    coordinator._agent_instances.clear()


def _template_agents(template: str) -> set[str]:
    return {step["agent"] for step in WORKFLOW_TEMPLATES[template]["steps"]}


# ─────────────────────────────────────────────
# ① write_from_scratch 全链路（模板驱动 + 边级注入判定）
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_write_from_scratch_chain_success(fake_coordinator):
    """write_from_scratch：12 步全部执行成功，无失败 Agent。"""
    coordinator = fake_coordinator["coordinator"]
    result = await coordinator.process(
        {
            "task": "从零撰写一篇论文",
            "content": "# Introduction\n研究背景占位内容。",
            "workflow_template": "write_from_scratch",
            "outline": "1. Introduction\n2. Methods",
            "section": "Introduction",
            "data_description": "实验数据集：两组对照样本",
        }
    )
    assert result["status"] == "success", result
    assert not result.get("failed_agents"), result

    template_agents = _template_agents("write_from_scratch")
    used = set(result["agents_used"])
    assert template_agents <= used, (
        f"模板 Agent 未全部执行: 缺失 {template_agents - used}"
    )


@pytest.mark.asyncio
async def test_write_from_scratch_literature_to_writing_edge(fake_coordinator):
    """边 literature→writing：检索到的论文标题须原文出现在写作 Agent 的 prompt。"""
    coordinator = fake_coordinator["coordinator"]
    title = fake_coordinator["paper_title"]
    fakes = fake_coordinator["fakes"]

    result = await coordinator.process(
        {
            "task": "从零撰写一篇论文",
            "content": "# Introduction\n研究背景占位内容。",
            "workflow_template": "write_from_scratch",
            "outline": "1. Introduction\n2. Methods",
            "section": "Introduction",
            "data_description": "实验数据集：两组对照样本",
        }
    )
    assert result["status"] == "success", result

    writing_prompts = fakes["writing"].prompts_for("writing")
    assert title in writing_prompts, (
        "上游 literature 的论文标题未注入 writing 的 LLM prompt，"
        "literature→writing 边未接通"
    )


@pytest.mark.asyncio
async def test_write_from_scratch_draft_reaches_polishing_and_reviewer(
    fake_coordinator,
):
    """边 writing→polishing / writing→reviewer：草稿标记须出现在下游 prompt。"""
    coordinator = fake_coordinator["coordinator"]
    fakes = fake_coordinator["fakes"]

    result = await coordinator.process(
        {
            "task": "从零撰写一篇论文",
            "content": "# Introduction\n研究背景占位内容。",
            "workflow_template": "write_from_scratch",
            "outline": "1. Introduction\n2. Methods",
            "section": "Introduction",
            "data_description": "实验数据集：两组对照样本",
        }
    )
    assert result["status"] == "success", result

    polishing_prompts = fakes["polishing"].prompts_for("polishing")
    assert DRAFT_MARKER in polishing_prompts, (
        "writing 生成的草稿未流入 polishing 的 LLM prompt，"
        "writing→polishing 边未接通"
    )

    reviewer_prompts = fakes["reviewer"].prompts_for("reviewer")
    assert DRAFT_MARKER in reviewer_prompts, (
        "writing 生成的草稿未流入 reviewer 的 LLM prompt，"
        "writing→reviewer 边未接通"
    )


# ─────────────────────────────────────────────
# ② revise 全链路（审稿意见 → 回复 → 修订 → 润色 → 复审）
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_revise_chain_success(fake_coordinator):
    """revise：5 步模板全部执行成功。"""
    coordinator = fake_coordinator["coordinator"]
    result = await coordinator.process(
        {
            "task": "根据审稿意见修订论文",
            "content": "# Abstract\n待修订的稿件正文占位。",
            "workflow_template": "revise",
        }
    )
    assert result["status"] == "success", result
    assert not result.get("failed_agents"), result

    template_agents = _template_agents("revise")
    used = set(result["agents_used"])
    assert template_agents <= used, (
        f"模板 Agent 未全部执行: 缺失 {template_agents - used}"
    )


@pytest.mark.asyncio
async def test_revise_chain_review_issue_reaches_response_and_revision(
    fake_coordinator,
):
    """边级判定：结构化评审的改进意见须流入 response 与 writing.revise。"""
    coordinator = fake_coordinator["coordinator"]
    fakes = fake_coordinator["fakes"]

    result = await coordinator.process(
        {
            "task": "根据审稿意见修订论文",
            "content": "# Abstract\n待修订的稿件正文占位。",
            "workflow_template": "revise",
        }
    )
    assert result["status"] == "success", result

    response_prompts = fakes["response"].prompts_for("response")
    assert ISSUE_MARKER in response_prompts, (
        "reviewer 的改进意见未注入 response 的 LLM prompt，"
        "reviewer→response 边未接通"
    )

    writing_prompts = fakes["writing"].prompts_for("writing")
    assert ISSUE_MARKER in writing_prompts, (
        "reviewer 的改进意见未注入 writing.revise 的 LLM prompt，"
        "reviewer→writing 边未接通"
    )

    writing_result = result["results"].get("writing") or {}
    assert writing_result.get("revised_content"), (
        f"writing.revise 未产出修订正文: {writing_result}"
    )
    assert not writing_result.get("parse_error"), writing_result

    polishing_prompts = fakes["polishing"].prompts_for("polishing")
    assert REVISED_MARKER in polishing_prompts, (
        "修订后的正文未流入 polishing 的 LLM prompt，"
        "writing→polishing 边未接通"
    )


# ─────────────────────────────────────────────
# ③ 模板治理：重复 Agent、依赖边、任务名一致性
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_submit_template_duplicate_agent_rejected(fake_coordinator):
    """submit 模板含重复 Agent（submission_package×3、cover×2）→ 明确报错。"""
    coordinator = fake_coordinator["coordinator"]

    with pytest.raises(Exception) as exc_info:
        await coordinator.process(
            {
                "task": "投稿打包",
                "content": "稿件占位。",
                "workflow_template": "submit",
            }
        )
    message = str(exc_info.value)
    assert "重复" in message or "duplicate" in message.lower(), (
        f"重复 Agent 未被明确拒绝: {message}"
    )


def test_planner_dependency_edges_for_chain():
    """依赖图契约：citation 有依赖边；data 键名与 Agent 注册名一致。"""
    assert "citation" in AGENT_DEPENDENCIES, (
        "AGENT_DEPENDENCIES 缺少 citation 依赖边，引用校验不在任何上游之后"
    )
    assert "data_agent" in AGENT_DEPENDENCIES or "data" not in AGENT_DEPENDENCIES, (
        "AGENT_DEPENDENCIES 使用废弃键名 'data'，应为注册名 'data_agent'"
    )


@pytest.mark.asyncio
async def test_template_step_task_names_dispatchable(fake_coordinator):
    """模板任务名必须被目标 Agent 的任务分派表接受（写作/审稿/引用三处修正）。"""
    coordinator = fake_coordinator["coordinator"]

    probes = [
        ("writing", "generate", {"outline": "1. Intro", "section": "Intro"}),
        ("reviewer", "assess", {"content": "评审用占位正文。"}),
        ("citation", "verify-citations", {"content": "引用验证占位 [1]。"}),
    ]
    errors: list[str] = []
    for agent_name, task, extra in probes:
        agent = coordinator.get_agent(agent_name)
        try:
            await agent.process({"task": task, **extra})
        except Exception as e:
            message = str(e)
            if "未知任务" in message:
                errors.append(f"{agent_name}.{task} -> {message}")
    assert not errors, "模板任务名与 Agent 分派表不一致: " + "; ".join(errors)


# ─────────────────────────────────────────────
# ④ 零回归：不传模板时行为不变（今天即应绿）
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_orchestrate_without_template_zero_regression(fake_coordinator):
    """缺省 workflow_template：关键词路由 literature 单 Agent，结果含论文列表。"""
    coordinator = fake_coordinator["coordinator"]
    result = await coordinator.process(
        {"task": "文献检索", "query": "量子计算综述", "content": "检索近三年综述"}
    )
    assert result["status"] == "success", result
    assert "literature" in result["agents_used"], result
    literature_result = result["results"].get("literature") or {}
    papers = literature_result.get("papers")
    assert papers and papers[0]["title"] == fake_coordinator["paper_title"]


# ─────────────────────────────────────────────
# ⑤ HTTP 冒烟：/orchestrate 接受 workflow_template（唯一一条 HTTP 用例）
# ─────────────────────────────────────────────

_PASSWORD = "Passw0rd!e2e"


def _unique_creds() -> tuple[str, str]:
    token = uuid.uuid4().hex
    return f"e2e_wf_{token[:12]}@example.com", f"wf_{token[:10]}"


@pytest.mark.asyncio
async def test_orchestrate_accepts_workflow_template_over_http(
    db_isolated_client, monkeypatch
):
    """HTTP 冒烟：注册→登录→/orchestrate 传模板不被拒绝，且按模板展开执行。

    与进程内用例共享协调器单例，故本用例自行打桩（FakeLLM + 检索桩），
    不依赖用例执行顺序；结束后清理实例缓存。
    """
    coordinator = get_coordinator_agent()
    coordinator._agent_instances.clear()

    coord_fake = FakeLLM(route_agents=["literature"])
    coord_fake._agent_name = "coordinator"
    monkeypatch.setattr(coordinator, "llm", coord_fake)

    # literature 可能被兜底路由命中：打桩其 LLM 与检索，杜绝外网
    literature = coordinator.get_agent("literature")
    lit_fake = FakeLLM()
    lit_fake._agent_name = "literature"
    monkeypatch.setattr(literature, "llm", lit_fake)

    async def _fake_search(query, filters=None):  # noqa: ANN001
        return [{"id": "p1", "title": "HttpSmoke Paper", "year": 2024}]

    monkeypatch.setattr(
        literature.tools_handler, "search_papers", _fake_search, raising=True
    )

    # revise 模板链路的其余 Agent 全部挂 FakeLLM，杜绝真实 LLM 外网调用
    for name in ("reader", "reviewer", "response", "writing", "polishing"):
        agent = coordinator.get_agent(name)
        fake = FakeLLM()
        fake._agent_name = name
        monkeypatch.setattr(agent, "llm", fake)

    try:
        email, username = _unique_creds()
        reg = await db_isolated_client.post(
            "/api/v1/auth/register",
            json={"email": email, "username": username, "password": _PASSWORD},
        )
        assert reg.status_code == 200, reg.text
        login = await db_isolated_client.post(
            "/api/v1/auth/login", json={"email": email, "password": _PASSWORD}
        )
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]

        resp = await db_isolated_client.post(
            "/api/v1/coordinator/orchestrate",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "task": "根据审稿意见修订论文",
                "content": "# Abstract\nHTTP 冒烟稿件占位。",
                "workflow_template": "revise",
            },
        )
        assert resp.status_code == 200, (
            f"/orchestrate 拒绝了 workflow_template 请求: {resp.status_code} {resp.text}"
        )
        body = resp.json()
        assert body["task_id"] and body["trace_id"]

        final = body["result"]
        assert final["status"] == "success", final
        template_agents = _template_agents("revise")
        used = set(final["agents_used"])
        assert template_agents <= used, (
            f"HTTP 编排未按模板展开: 缺失 {template_agents - used}"
        )
    finally:
        coordinator._agent_instances.clear()


# ─────────────────────────────────────────────
# ⑥ 契约守卫：未知模板 id 必须被校验层拒绝（Q10/Q11）
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_orchestrate_rejects_unknown_workflow_template(db_isolated_client):
    """未知 workflow_template → 422（Pydantic 字段校验），而非 500/200。

    任务与 content 均合法，唯一错点是模板 id；返回 200（校验放行）
    或 500（落进业务异常）都算红。
    """
    email, username = _unique_creds()
    reg = await db_isolated_client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": _PASSWORD},
    )
    assert reg.status_code == 200, reg.text
    login = await db_isolated_client.post(
        "/api/v1/auth/login", json={"email": email, "password": _PASSWORD}
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    resp = await db_isolated_client.post(
        "/api/v1/coordinator/orchestrate",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "task": "文献检索",
            "query": "量子计算综述",
            "content": "检索近三年综述",
            "workflow_template": "no_such_template",
        },
    )
    assert resp.status_code == 422, (
        f"未知模板 id 应被字段校验以 422 拒绝，"
        f"实际得到 {resp.status_code}: {resp.text}"
    )


# ─────────────────────────────────────────────
# ⑦ 中链失败 fail-fast（Q12）：一步失败 → 整条编排失败，后续步骤不执行
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_template_midchain_failure_fails_fast(fake_coordinator, monkeypatch):
    """revise 第 2 步 reviewer 失败 → status=failed，后续步骤一律不执行。

    锁住 Q12 契约：模板是硬链，上游失败后下游拿不到注入产出，
    继续执行只会产生垃圾结果（修复前的 partial_failure 静默行为）。
    「未执行」用两重证据：agents_used 截止于失败点 + 下游 FakeLLM 零调用。
    """
    coordinator = fake_coordinator["coordinator"]
    fakes = fake_coordinator["fakes"]

    reviewer = coordinator.get_agent("reviewer")

    async def _boom(request):  # noqa: ANN001
        raise RuntimeError("e2e fail-fast 注入故障")

    monkeypatch.setattr(reviewer, "process", _boom)

    result = await coordinator.process(
        {
            "task": "根据审稿意见修订论文",
            "content": "# Abstract\nfail-fast 故障注入占位。",
            "workflow_template": "revise",
        }
    )

    assert result["status"] == "failed", result
    assert result["failed_agents"] == ["reviewer"], result
    assert "reviewer" in result.get("error", ""), (
        f"错误信息未指明失败步骤: {result}"
    )
    # agents_used 截止于失败点：失败前步骤在列，后续步骤缺席
    assert result["agents_used"] == ["reader", "reviewer"], result
    for name in ("response", "writing", "polishing"):
        assert name not in result["results"], f"{name} 不应出现在结果中"
        assert not fakes[name].calls, (
            f"{name} 在上游失败后仍被执行（FakeLLM 有 {len(fakes[name].calls)} 次调用）"
        )


@pytest.mark.asyncio
async def test_no_template_failure_semantics_unchanged(fake_coordinator):
    """零回归：非模板路径的失败语义不受 Q12 影响（仍为异常直抛）。"""
    coordinator = fake_coordinator["coordinator"]

    literature = coordinator.get_agent("literature")

    async def _boom(request):  # noqa: ANN001
        raise RuntimeError("e2e 非模板路径故障")

    original = literature.process
    literature.process = _boom
    try:
        with pytest.raises(Exception) as exc_info:
            await coordinator.process(
                {"task": "文献检索", "query": "量子计算综述"}
            )
        assert "非模板路径故障" in str(exc_info.value)
    finally:
        literature.process = original

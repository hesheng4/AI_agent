from typing import Any

from app.utils.exceptions import AgentException

# ── 16 Nature-skills 关键词路由表 ──
# 格式: (agent_name, [中文关键词], [英文关键词])
SKILL_KEYWORD_MAP: list[tuple[str, list[str], list[str]]] = [
    (
        "literature",
        ["文献", "文献检索", "学术论文", "搜索论文"],
        ["literature", "academic-search", "paper search", "find papers"],
    ),
    ("citation", ["引用", "参考文献", "引文"], ["citation", "reference", "cite"]),
    (
        "reader",
        ["阅读", "阅读理解", "论文阅读", "解读"],
        ["reader", "read", "understand", "comprehend"],
    ),
    ("writing", ["写作", "写论文", "撰写"], ["writing", "write", "draft", "compose"]),
    (
        "polishing",
        ["润色", "修改", "语言润色", "语言修改"],
        ["polishing", "polish", "refine", "edit language"],
    ),
    (
        "stats",
        ["统计", "统计分析", "p值", "效应量", "检验", "多重比较"],
        [
            "stats",
            "statistics",
            "p-value",
            "effect size",
            "test",
            "multiple comparison",
        ],
    ),
    (
        "methods",
        ["方法", "Methods", "可复现", "伦理", "材料"],
        ["methods", "reproducibility", "ethics", "materials", "protocol"],
    ),
    (
        "figure",
        ["作图", "图", "图表", "绘图", "可视化"],
        ["figure", "chart", "plot", "visualization", "graph"],
    ),
    (
        # data_agent 必须排在 data 之前：identify_agents 的关键词特异性
        # 规则会让「数据可用性」命中 data_agent 而不再拖上通用的 data
        "data_agent",
        ["数据可用性", "数据声明", "数据共享", "数据仓库"],
        ["data availability", "data statement", "repository"],
    ),
    (
        "data",
        ["数据分析", "数据集", "数据"],
        ["data", "dataset"],
    ),
    (
        "reviewer",
        ["自审", "审稿", "评审", "自查"],
        ["reviewer", "review", "self-review", "check"],
    ),
    (
        "response",
        ["回复", "回复审稿", "审稿回复", "rebuttal"],
        ["response", "rebuttal", "reply", "revision response"],
    ),
    (
        "cover",
        ["投稿信", "cover letter", "投稿信起草", "presubmission"],
        ["cover", "cover letter", "presubmission"],
    ),
    (
        "submission_package",
        ["投稿", "投稿包", "投稿清单", "期刊匹配", "一致性"],
        [
            "submission",
            "submission package",
            "checklist",
            "journal match",
            "consistency",
        ],
    ),
    (
        # 「报告」已移除：泛化「请给一份报告」曾误路由 PPT（差距 #1），零命中走 LLM 兜底
        "paper2ppt",
        ["PPT", "演讲", "转化PPT"],
        ["paper2ppt", "ppt", "presentation", "slides"],
    ),
    (
        "paper_to_patent",
        ["专利", "发明专利", "转化专利"],
        ["patent", "paper to patent", "invention"],
    ),
    (
        "experiment",
        ["实验", "实验设计", "实验优化"],
        ["experiment", "design", "optimize"],
    ),
]

# ── 能力地图 ──
CAPABILITY_MAP: dict[str, dict[str, Any]] = {
    "literature": {
        "stage": "文献检索",
        "tasks": ["search", "summarize"],
        "description": "学术文献检索与摘要",
    },
    "citation": {
        "stage": "文献检索",
        "tasks": ["format", "check", "insert"],
        "description": "引用格式化与检查",
    },
    "reader": {
        "stage": "阅读理解",
        "tasks": ["read", "translate", "annotate"],
        "description": "全文中英对照阅读",
    },
    "writing": {
        "stage": "写作",
        "tasks": ["draft", "section", "revise"],
        "description": "学术写作与段落起草",
    },
    "polishing": {
        "stage": "润色",
        "tasks": ["polish", "shorten", "simplify"],
        "description": "语言润色与表达优化",
    },
    "stats": {
        "stage": "统计",
        "tasks": ["audit", "draft", "check_test", "check_multiple"],
        "description": "统计报告合规审计与起草",
    },
    "methods": {
        "stage": "方法",
        "tasks": ["audit", "draft", "check_ethics", "remove_vague"],
        "description": "Methods可复现性与合规审计",
    },
    "figure": {
        "stage": "作图",
        "tasks": ["generate", "refine"],
        "description": "科研图表生成与优化",
    },
    "data": {
        "stage": "数据",
        "tasks": ["analyze", "visualize", "upload", "summary"],
        "description": "数据分析与可视化",
    },
    "data_agent": {
        "stage": "数据",
        "tasks": ["generate-statement", "audit-statement", "select-repository"],
        "description": "数据可用性声明（FAIR 合规）",
    },
    "reviewer": {
        "stage": "自审",
        "tasks": ["review", "score"],
        "description": "模拟审稿与自检",
    },
    "response": {
        "stage": "回复审稿",
        "tasks": ["draft", "point_by_point"],
        "description": "审稿回复起草",
    },
    "cover": {
        "stage": "投稿",
        "tasks": ["draft", "audit", "presubmission"],
        "description": "投稿信起草与desk-reject防御",
    },
    "submission_package": {
        "stage": "投稿",
        "tasks": ["match_journal", "checklist", "consistency_check"],
        "description": "投稿包组装与跨件一致性检查",
    },
    "paper2ppt": {
        "stage": "传播",
        "tasks": ["convert"],
        "description": "论文转PPT演讲",
    },
    "paper_to_patent": {
        "stage": "传播",
        "tasks": ["convert"],
        "description": "论文转发明专利",
    },
    "experiment": {
        "stage": "实验",
        "tasks": ["design", "optimize", "predict"],
        "description": "实验设计与优化",
    },
}

# ── 4条工作流模板 ──
WORKFLOW_TEMPLATES: dict[str, dict[str, Any]] = {
    "write_from_scratch": {
        "label": "从头写论文",
        "steps": [
            {
                "step": 1,
                "agent": "literature",
                "task": "search",
                "desc": "文献检索与筛选",
            },
            {"step": 2, "agent": "reader", "task": "read", "desc": "精读关键文献"},
            {"step": 3, "agent": "experiment", "task": "design", "desc": "实验设计"},
            {"step": 4, "agent": "writing", "task": "generate", "desc": "起草论文初稿"},
            {"step": 5, "agent": "methods", "task": "draft", "desc": "起草Methods"},
            {"step": 6, "agent": "stats", "task": "draft", "desc": "统计报告起草"},
            {"step": 7, "agent": "figure", "task": "generate", "desc": "生成图表"},
            {
                "step": 8,
                "agent": "data_agent",
                "task": "generate-statement",
                "desc": "数据可用性声明",
            },
            {"step": 9, "agent": "polishing", "task": "polish", "desc": "全文润色"},
            {"step": 10, "agent": "reviewer", "task": "assess", "desc": "自审模拟"},
            {
                "step": 11,
                "agent": "citation",
                "task": "verify-citations",
                "desc": "引用检查",
            },
            {
                "step": 12,
                "agent": "submission_package",
                "task": "checklist",
                "desc": "投稿清单检查",
            },
        ],
    },
    "submit": {
        "label": "投稿",
        "steps": [
            {
                "step": 1,
                "agent": "submission_package",
                "task": "match_journal",
                "desc": "期刊匹配",
            },
            {"step": 2, "agent": "cover", "task": "draft", "desc": "投稿信起草"},
            {
                "step": 3,
                "agent": "submission_package",
                "task": "checklist",
                "desc": "投稿清单",
            },
            {
                "step": 4,
                "agent": "submission_package",
                "task": "consistency_check",
                "desc": "跨件一致性检查",
            },
            {
                "step": 5,
                "agent": "cover",
                "task": "audit",
                "desc": "投稿信desk-reject审计",
            },
        ],
    },
    "revise": {
        "label": "修稿",
        "steps": [
            {"step": 1, "agent": "reader", "task": "read", "desc": "审读稿件与意见"},
            {"step": 2, "agent": "reviewer", "task": "assess", "desc": "意见结构化"},
            {"step": 3, "agent": "response", "task": "draft", "desc": "逐条回复起草"},
            {"step": 4, "agent": "writing", "task": "revise", "desc": "修改论文"},
            {"step": 5, "agent": "polishing", "task": "polish", "desc": "润色修改稿"},
        ],
    },
    "transform": {
        "label": "转化",
        "steps": [
            {"step": 1, "agent": "paper2ppt", "task": "convert", "desc": "论文转PPT"},
            {
                "step": 2,
                "agent": "paper_to_patent",
                "task": "convert",
                "desc": "论文转专利",
            },
        ],
    },
}

# ── 依赖关系（扩展版） ──
# 注意：data（通用数据分析）与 data_agent（数据可用性声明）是两个独立
# 注册 Agent，依赖边须各自保留，勿当作重复项清理。
AGENT_DEPENDENCIES: dict[str, list[str]] = {
    "writing": ["literature", "reader"],
    "data": ["experiment", "literature"],
    "data_agent": ["experiment", "literature"],
    "polishing": ["writing"],
    "reviewer": ["writing", "stats", "methods"],
    "citation": ["writing", "polishing"],
    "cover": ["writing"],
    "submission_package": ["cover", "stats", "methods"],
    "response": ["reviewer"],
}

# ── 上游结果字段级注入映射（差距 #3：声明式，替代 coordinator 的 if 链）──
# 格式: {下游 agent: {目标字段: (上游 agent, 源字段)}}
# 源字段三种形态：字符串=单个源字段；列表=顺序取第一个命中值；
# None=整个上游结果。目标字段默认只补缺失（调用方显式传入优先）；
# 模板驱动编排（子任务带 _template 标记）时上游产出覆写目标字段。
UPSTREAM_FIELD_MAP: dict[str, dict[str, tuple[str, str | list[str] | None]]] = {
    "writing": {
        "papers": ("literature", "papers"),
        "summaries": ("literature", "summaries"),
        "suggestions": ("reviewer", "improvement_suggestions"),
    },
    "data": {
        "papers": ("literature", "papers"),
        "experiment_plan": ("experiment", "plan"),
    },
    "data_agent": {
        "papers": ("literature", "papers"),
        "experiment_plan": ("experiment", "plan"),
    },
    "reviewer": {
        "content": ("writing", ["content", "revised_content"]),
    },
    "polishing": {
        "content": ("writing", ["content", "revised_content"]),
    },
    "response": {
        "review_result": ("reviewer", None),
    },
}

# ── 默认机器任务映射 ──
# 关键词路由命中的自然语言任务（如「文献检索」）不在 Agent 分派表里，
# 会被目标 Agent 以「未知任务类型」拒绝。分解子任务时统一改写为
# 分派表接受的机器任务名；不在表中的 Agent（如 reader，process 忽略
# task 字段）保持原样。
DEFAULT_AGENT_TASK: dict[str, str] = {
    "literature": "search",
    "citation": "verify-citations",
    "writing": "generate",
    "polishing": "polish",
    "stats": "audit",
    "methods": "audit",
    "figure": "generate",
    "data_agent": "generate-statement",
    "data": "analyze",
    "reviewer": "assess",
    "response": "draft",
    "cover": "draft",
    "submission_package": "checklist",
    "experiment": "design",
}


class TaskPlanner:
    """任务规划器 — 覆盖全部 16 Nature-skills"""

    def __init__(self, agents: dict[str, Any] | None = None):
        self.agents = agents or {}
        # 构建快速查找: 关键词 -> agent_name
        self._keyword_index: dict[str, str] = {}
        for agent_name, cn_keywords, en_keywords in SKILL_KEYWORD_MAP:
            for kw in cn_keywords + en_keywords:
                self._keyword_index[kw.lower()] = agent_name

    def identify_agents(self, request: dict[str, Any]) -> list[str]:
        """识别需要的Agent — 覆盖全部 17 skill 关键词"""
        task_type = request.get("task", "")

        # 1) 精确匹配 task 字段
        matched = self._keyword_index.get(task_type.lower())
        if matched:
            return [matched]

        # 2) 关键词扫描 task 字段；3) 兜底扫描整个 request
        text = task_type if task_type else ""
        agents_needed = self._match_keywords(text)
        if not agents_needed:
            agents_needed = self._match_keywords(str(request))

        return agents_needed

    def _match_keywords(self, text: str) -> list[str]:
        """关键词扫描 + 特异性去重

        「数据可用性」命中 data_agent 时，其超串「数据」（data）不应
        再把通用 agent 拉进来——保留更长关键词对应的 agent。
        """
        text_lower = text.lower()
        matched: dict[str, str] = {}  # kw -> agent_name（保持插入序）
        for kw, agent_name in self._keyword_index.items():
            if kw in text_lower:
                matched[kw] = agent_name
        agents: list[str] = []
        for kw, agent_name in matched.items():
            if any(kw != other and kw in other for other in matched):
                continue  # 存在更长的关键词已覆盖此通用词
            agents.append(agent_name)
        return list(dict.fromkeys(agents))

    def complete_upstream(self, agents: list[str]) -> list[str]:
        """补全缺失的上游 Agent — 对 AGENT_DEPENDENCIES 求传递闭包

        静态依赖表只表达「谁依赖谁」，而调度要求依赖闭包完整：
        用户只说「写论文」时 identify_agents 只命中 writing，但
        _group_by_level 发现其依赖 literature/reader 不在计划中会
        误报循环依赖。这里把缺失上游补进计划。

        仅 process() 多 Agent 编排路径调用；process_simple 是
        刻意的单 Agent 语义，不做补全。
        """
        result = list(dict.fromkeys(agents))  # 去重保序
        queue = list(result)
        while queue:
            for dep in AGENT_DEPENDENCIES.get(queue.pop(0), []):
                if dep not in result:
                    result.append(dep)
                    queue.append(dep)
        return result

    def validate_template(self, template_id: str, template: dict[str, Any]) -> None:
        """模板合法性校验：id 在册 + 同一 Agent 不得出现多次

        当前调度模型每个 Agent 只执行一个任务、上游结果经注入下传；
        同 Agent 多步（如 submit 模板的 submission_package×3）会导致
        结果相互覆盖，明确拒绝而非静默错乱。
        """
        if template_id not in WORKFLOW_TEMPLATES:
            raise AgentException(
                f"未知工作流模板: {template_id!r}，"
                f"可用: {sorted(WORKFLOW_TEMPLATES)}",
                "coordinator",
            )
        seen: set[str] = set()
        dupes: list[str] = []
        for step in template["steps"]:
            agent = step["agent"]
            if agent in seen:
                dupes.append(agent)
            seen.add(agent)
        if dupes:
            raise AgentException(
                f"工作流模板 {template_id!r} 含重复 Agent: "
                f"{sorted(set(dupes))}；每个 Agent 仅支持单步任务",
                "coordinator",
            )

    def decompose_task(
        self, request: dict[str, Any], agents: list[str]
    ) -> list[dict[str, Any]]:
        """分解任务

        - 模板驱动（request 含 workflow_template）：按模板步骤逐步展开，
          执行顺序即步骤顺序，每步依赖其前所有步骤的 Agent（上游结果
          经字段级注入下传）；子任务携带 _template 标记供注入侧识别覆写
          语义。
        - 无模板：每个命中 Agent 一个子任务，请求浅拷贝隔离，并把
          自然语言任务改写为分派表接受的机器任务名（DEFAULT_AGENT_TASK）。
        """
        template_id = request.get("workflow_template")
        if template_id:
            template = WORKFLOW_TEMPLATES[template_id]
            self.validate_template(template_id, template)
            return self._decompose_template(request, template)

        subtasks = []
        for agent_name in agents:
            sub_request = dict(request)
            default_task = DEFAULT_AGENT_TASK.get(agent_name)
            if default_task:
                sub_request["task"] = default_task
            subtasks.append(
                {"agent": agent_name, "request": sub_request, "dependencies": []}
            )
        return subtasks

    def _decompose_template(
        self, request: dict[str, Any], template: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """模板展开为逐步子任务：步骤顺序即执行顺序，依赖取前缀"""
        subtasks: list[dict[str, Any]] = []
        prior_agents: list[str] = []
        for step in template["steps"]:
            agent_name = step["agent"]
            sub_request = dict(request)
            sub_request.pop("workflow_template", None)
            sub_request["task"] = step["task"]
            if agent_name == "literature" and not str(
                sub_request.get("query") or ""
            ).strip():
                sub_request["query"] = self._synthesize_query(request)
            subtasks.append(
                {
                    "agent": agent_name,
                    "request": sub_request,
                    "dependencies": list(prior_agents),
                    "_template": template["label"],
                }
            )
            prior_agents.append(agent_name)
        return subtasks

    @staticmethod
    def _synthesize_query(request: dict[str, Any]) -> str:
        """模板首步文献检索缺 query 时，从请求上下文合成检索词"""
        for key in ("topic", "outline", "content", "task"):
            value = str(request.get(key) or "").strip()
            if value:
                return value[:200]
        return "相关领域综述"

    def analyze_dependencies(
        self, subtasks: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """分析依赖关系 — 使用扩展依赖表"""
        execution_plan = []
        for subtask in subtasks:
            agent = subtask["agent"]
            if agent in AGENT_DEPENDENCIES:
                subtask["dependencies"] = AGENT_DEPENDENCIES[agent]
            execution_plan.append(subtask)
        return execution_plan

    def get_capability_map(self) -> dict[str, dict[str, Any]]:
        """返回能力地图"""
        return CAPABILITY_MAP

    def get_workflow_templates(self) -> dict[str, dict[str, Any]]:
        """返回工作流模板"""
        return WORKFLOW_TEMPLATES

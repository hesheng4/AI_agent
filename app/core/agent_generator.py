"""E10: AI 辅助 Agent 代码生成 — 自然语言描述 → 6 处代码骨架

生成文件:
1. agents/{name}/agent.py — BaseAgent 子类
2. agents/{name}/manifest.yaml — manifest 元数据
3. api/v1/{name}.py — FastAPI 路由
4. frontend/src/pages/{Name}.tsx — React 页面
5. api.ts 片段 — 前端 API 调用
6. planner 条目 — 关键词 + 能力地图
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.utils.llm import LLMClient
from app.utils.logger import get_logger

logger = get_logger("core.agent_generator")
settings = get_settings()

# 临时生成目录
_GENERATED_DIR = Path(tempfile.gettempdir()) / "moguan_agent_generated"

# ===== LLM Prompt =====

_SYSTEM_PROMPT = """你是一个 Agent 代码生成器。根据用户描述生成完整的 Agent 代码骨架。

项目约定:
- Agent 目录名 = agent_name（小写连字符，如 extract-table）
- Agent 类名 = 目录名转 PascalCase + Agent（如 ExtractTableAgent）
- 继承 BaseAgent，实现 async process(request) -> dict
- process 内按 task 字段分派到不同 handler
- 每个 handler 调用 self.call_llm() 获取 LLM 输出
- API 路由参考 cover.py 模板：router + Request/Response model + endpoint
- 前端页面参考 CoverLetter.tsx：form + loading + result 展示
- api.ts 片段：一个 process 方法，POST 到 /{name}/process

你必须输出合法 JSON，格式如下:
{
  "agent_name": "extract-table",
  "class_name": "ExtractTableAgent",
  "agent_py": "完整 agent.py 内容（含 import + class + process + handlers）",
  "manifest_yaml": "完整 manifest.yaml 内容",
  "api_route_py": "完整 api/v1/{name}.py 内容（含 router + models + endpoint）",
  "frontend_page_tsx": "完整 pages/{Name}.tsx 内容（含 form + submit + result）",
  "frontend_api_ts": "api.ts 新增片段（export const xxxApi = { process: ... }）",
  "planner_entry": {
    "zh_keywords": ["提取", "表格", "实验参数"],
    "en_keywords": ["extract", "table", "experiment parameters"],
    "tasks": ["extract", "compare"],
    "description": "实验参数提取与对比表格生成"
  }
}

规则:
- agent_py 必须含 `from app.agents.base import BaseAgent`
- agent_py 的 class 必须继承 BaseAgent
- agent_py 的 __init__ 必须调 super().__init__(name="xxx", tools=[...])
- agent_py 的 process 必须是 async def process(self, request: dict) -> dict
- api_route_py 必须含 `from fastapi import APIRouter, Depends`
- api_route_py 必须含 `router = APIRouter(tags=["xxx"])`
- frontend_page_tsx 必须含 useState + handleSubmit + loading 状态
- 所有代码只生成骨架，不依赖未安装的第三方库
"""


class AgentGenerationResult:
    """生成结果"""

    def __init__(self, session_id: str, data: dict[str, Any], temp_dir: Path):
        self.session_id = session_id
        self.agent_name: str = data.get("agent_name", "")
        self.class_name: str = data.get("class_name", "")
        self.agent_py: str = data.get("agent_py", "")
        self.manifest_yaml: str = data.get("manifest_yaml", "")
        self.api_route_py: str = data.get("api_route_py", "")
        self.frontend_page_tsx: str = data.get("frontend_page_tsx", "")
        self.frontend_api_ts: str = data.get("frontend_api_ts", "")
        self.planner_entry: dict[str, Any] = data.get("planner_entry", {})
        self._temp_dir = temp_dir

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "agent_name": self.agent_name,
            "class_name": self.class_name,
            "agent_py": self.agent_py,
            "manifest_yaml": self.manifest_yaml,
            "api_route_py": self.api_route_py,
            "frontend_page_tsx": self.frontend_page_tsx,
            "frontend_api_ts": self.frontend_api_ts,
            "planner_entry": self.planner_entry,
        }


async def generate_agent(
    description: str,
    name_hint: str | None = None,
) -> AgentGenerationResult:
    """调用 LLM 生成 Agent 代码骨架

    1. 构建 prompt（含用户描述 + name hint）
    2. 调用 LLM 获取结构化 JSON
    3. 解析 + 存入临时目录
    4. 返回生成结果（待用户确认）
    """
    import uuid

    session_id = uuid.uuid4().hex[:12]

    # 检查 name_hint 是否已存在
    if name_hint:
        agents_dir = Path("app/agents") / name_hint
        if agents_dir.exists():
            raise ValueError(f"Agent 目录已存在: {name_hint}，请换一个名字")

    # 构建 prompt
    hint_line = f"\n建议的目录名: {name_hint}" if name_hint else ""
    user_prompt = f"请生成一个 Agent:\n{description}{hint_line}"

    # 调用 LLM
    llm = LLMClient()
    raw = await llm.generate(
        prompt=user_prompt,
        system_prompt=_SYSTEM_PROMPT,
        temperature=0.1,  # 低温度保证确定性
        max_tokens=8000,
    )

    # 解析 JSON（LLM 可能包裹在 ```json ... ``` 中）
    data = _extract_json(raw)
    if not data or "agent_name" not in data:
        raise ValueError(f"LLM 输出格式错误，无法解析为 JSON: {raw[:200]}")

    # 存入临时目录
    temp_dir = _GENERATED_DIR / session_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    (temp_dir / "generation.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    logger.info(
        f"Agent 生成完成: session={session_id}, agent_name={data.get('agent_name')}"
    )
    return AgentGenerationResult(session_id, data, temp_dir)


async def confirm_generation(session_id: str) -> dict[str, Any]:
    """用户确认后，将临时文件写入正式目录

    返回写入的文件列表。
    """
    temp_dir = _GENERATED_DIR / session_id
    gen_file = temp_dir / "generation.json"
    if not gen_file.exists():
        raise FileNotFoundError(f"生成会话不存在: {session_id}")

    data = json.loads(gen_file.read_text(encoding="utf-8"))
    result = AgentGenerationResult(session_id, data, temp_dir)
    agent_name = result.agent_name

    if not agent_name:
        raise ValueError("生成数据中缺少 agent_name")

    written_files: list[str] = []

    # 1. 写 agent.py
    agents_dir = Path("app/agents") / agent_name
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "agent.py").write_text(result.agent_py, encoding="utf-8")
    written_files.append(f"app/agents/{agent_name}/agent.py")

    # 2. 写 manifest.yaml
    if result.manifest_yaml:
        (agents_dir / "manifest.yaml").write_text(
            result.manifest_yaml, encoding="utf-8"
        )
        written_files.append(f"app/agents/{agent_name}/manifest.yaml")

    # 3. 写 prompts 占位目录
    prompts_dir = agents_dir / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    (prompts_dir / "__init__.py").write_text("", encoding="utf-8")

    # 4. 写 API 路由
    if result.api_route_py:
        api_file = Path("app/api/v1") / f"{agent_name.replace('-', '_')}.py"
        api_file.write_text(result.api_route_py, encoding="utf-8")
        written_files.append(f"app/api/v1/{agent_name.replace('-', '_')}.py")

        # 4a. 追加 __init__.py include
        _append_router_include(agent_name)

    # 5. 写前端页面
    if result.frontend_page_tsx:
        page_name = _to_pascal_case(agent_name) + ".tsx"
        page_file = Path("frontend/src/pages") / page_name
        page_file.write_text(result.frontend_page_tsx, encoding="utf-8")
        written_files.append(f"frontend/src/pages/{page_name}")

    # 6. 追加 planner 条目
    if result.planner_entry:
        _append_planner_entry(agent_name, result.planner_entry)

    # 7. 刷新注册表
    from app.agents.registry import refresh_registry

    refresh_registry()

    # 8. 清理临时目录
    shutil.rmtree(temp_dir, ignore_errors=True)

    logger.info(f"Agent 确认写入完成: {agent_name}, 文件: {written_files}")
    return {
        "status": "created",
        "agent_name": agent_name,
        "files": written_files,
    }


def _extract_json(raw: str) -> dict[str, Any] | None:
    """从 LLM 输出中提取 JSON（处理 ```json 包裹）"""
    # 尝试直接解析
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 块
    m = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试找第一个 { 到最后一个 }
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            pass

    return None


def _to_pascal_case(name: str) -> str:
    """连字符名转 PascalCase: extract-table → ExtractTable"""
    return "".join(word.capitalize() for word in name.split("-"))


def _append_router_include(agent_name: str) -> None:
    """在 api/v1/__init__.py 追加 router include（幂等）"""
    init_file = Path("app/api/v1/__init__.py")
    content = init_file.read_text(encoding="utf-8")
    module_name = agent_name.replace("-", "_")
    import_line = f"from app.api.v1.{module_name} import router as {module_name}_router"
    include_line = (
        f'router.include_router({module_name}_router, prefix="/{agent_name}", '
        f'tags=["{agent_name}"])'
    )

    if import_line in content:
        return  # 已存在，跳过

    # 追加 import（在最后一个 import router 行后）
    last_import_pos = content.rfind("import router as ")
    if last_import_pos != -1:
        line_end = content.find("\n", last_import_pos) + 1
        content = content[:line_end] + import_line + "\n" + content[line_end:]
    else:
        content += "\n" + import_line + "\n"

    # 追加 include（在最后一行）
    content += include_line + "\n"
    init_file.write_text(content, encoding="utf-8")


def _append_planner_entry(agent_name: str, entry: dict[str, Any]) -> None:
    """在 planner.py 追加关键词 + 能力地图条目（幂等）"""
    planner_file = Path("app/agents/coordinator/planner.py")
    content = planner_file.read_text(encoding="utf-8")

    if f'("{agent_name}"' in content:
        return  # 已存在，跳过

    zh_kw = entry.get("zh_keywords", [])
    en_kw = entry.get("en_keywords", [])
    tasks = entry.get("tasks", [])
    desc = entry.get("description", "")

    # 追加 SKILL_KEYWORD_MAP 条目
    kw_entry = f'    ("{agent_name}", {zh_kw}, {en_kw}),\n'
    # 找 SKILL_KEYWORD_MAP 最后一行
    marker = "SKILL_KEYWORD_MAP: list[tuple[str, list[str], list[str]]] = ["
    pos = content.find(marker)
    if pos != -1:
        # 找到列表末尾的 ]
        bracket_pos = content.find("]", pos)
        if bracket_pos != -1:
            # 在 ] 前插入
            content = content[:bracket_pos] + kw_entry + content[bracket_pos:]

    # 追加 CAPABILITY_MAP 条目
    cap_entry = (
        f'    "{agent_name}": {{"stage": "{agent_name}", "tasks": {tasks}, '
        f'"description": "{desc}"}},\n'
    )
    marker2 = "CAPABILITY_MAP: dict[str, dict[str, Any]] = {"
    pos2 = content.find(marker2)
    if pos2 != -1:
        bracket_pos2 = content.find("}", pos2)
        if bracket_pos2 != -1:
            content = content[:bracket_pos2] + cap_entry + content[bracket_pos2:]

    planner_file.write_text(content, encoding="utf-8")

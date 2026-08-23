"""E1: Agent 自动注册 — 扫描 agents/ 目录自动发现 Agent，替代硬编码 _AGENT_CLASSES

约定：
- 每个 Agent 子目录含 agent.py 且定义 class XxxAgent(BaseAgent)
- 目录名即 agent_name（如 literature/ → agent_name="literature"）
- coordinator 自身不注册（它是调度器，非业务 Agent）

新增 Agent 只需在 agents/ 下建目录 + agent.py（BaseAgent 子类），无需改本文件；
刻意不继承 BaseAgent 的独立 Agent（如不依赖 LLM 的 figure）加入 EXTRA_AGENTS。
"""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path

from app.agents.base import BaseAgent
from app.utils.logger import get_logger

logger = get_logger("agents.registry")

# 自动扫描结果缓存: {agent_name: (module_path, class_name)}
_AGENT_REGISTRY: dict[str, tuple[str, str]] | None = None

# 不继承 BaseAgent、需显式注册的独立 Agent 白名单。
# figure 不依赖 LLM（纯 matplotlib 工具），刻意不继承 BaseAgent，
# 但 planner 关键词表/工作流模板都引用它，必须可被 coordinator 加载。
EXTRA_AGENTS: dict[str, tuple[str, str]] = {
    "figure": ("app.agents.figure.agent", "FigureAgent"),
}


def _scan_agents() -> dict[str, tuple[str, str]]:
    """扫描 app/agents/ 下所有子目录，自动发现 Agent 类

    返回 {agent_name: (module_path, class_name)} 映射。
    agent_name 取目录名；module_path 为 app.agents.<dir>.agent；
    class_name 为该模块中 BaseAgent 的非抽象子类。
    """
    import app.agents as agents_pkg

    registry: dict[str, tuple[str, str]] = {}
    agents_dir = Path(agents_pkg.__file__).parent

    for entry in agents_dir.iterdir():
        if (
            not entry.is_dir()
            or entry.name.startswith("_")
            or entry.name == "coordinator"
        ):
            continue
        agent_py = entry / "agent.py"
        if not agent_py.exists():
            continue

        module_path = f"app.agents.{entry.name}.agent"
        try:
            module = importlib.import_module(module_path)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"自动注册：跳过 {entry.name}，import 失败: {e}")
            continue

        # 在模块中查找 BaseAgent 的子类（排除 BaseAgent 自身）
        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, BaseAgent)
                and obj is not BaseAgent
                and obj.__module__ == module_path
            ):
                registry[entry.name] = (module_path, obj.__name__)
                logger.debug(f"自动注册发现 Agent: {entry.name} → {obj.__name__}")
                break

    registry.update(EXTRA_AGENTS)
    logger.info(
        f"Agent 自动注册完成，发现 {len(registry)} 个 Agent: {list(registry.keys())}"
    )
    return registry


def get_agent_registry() -> dict[str, tuple[str, str]]:
    """获取 Agent 注册表（懒加载 + 缓存）"""
    global _AGENT_REGISTRY
    if _AGENT_REGISTRY is None:
        _AGENT_REGISTRY = _scan_agents()
    return _AGENT_REGISTRY


def refresh_registry() -> dict[str, tuple[str, str]]:
    """强制重新扫描（测试或热加载用）"""
    global _AGENT_REGISTRY
    _AGENT_REGISTRY = None
    return get_agent_registry()

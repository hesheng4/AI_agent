import asyncio
import json
from typing import Any

from app.agents.base import BaseAgent
from app.agents.coordinator.planner import UPSTREAM_FIELD_MAP, TaskPlanner
from app.agents.registry import get_agent_registry
from app.core.events import event_bus
from app.core.tracing import span, trace_context
from app.utils.exceptions import AgentException
from app.utils.logger import get_logger

logger = get_logger("agent.coordinator")

_ROUTING_SYSTEM_PROMPT = (
    "你是研究Agent平台的路由器。根据用户意图，从能力清单中选出真正需要执行的 Agent。"
    '只返回 JSON，格式：{"agents": ["agent_name"]}。'
    "规则：1) 只能使用清单中出现的 agent 名；2) 宁可少选，不要臆测；"
    '3) 无法判断时返回 {"agents": []}。'
)


class CoordinatorAgent(BaseAgent):
    """Nature-skills 协调器 — 自动发现全部 Agent（E1 插件化）"""

    def __init__(self):
        super().__init__(name="coordinator")
        # 懒加载：仅存实例缓存，首次 get_agent 时才 import + 实例化
        self._agent_instances: dict[str, Any] = {}
        self.planner = TaskPlanner(agents={})  # planner 不需 agent 实例，仅做关键词路由

    def get_agent(self, agent_name: str) -> Any:
        """懒加载获取子 agent 实例（E1: 从自动注册表查找）"""
        if agent_name in self._agent_instances:
            return self._agent_instances[agent_name]
        registry = get_agent_registry()
        spec = registry.get(agent_name)
        if not spec:
            raise AgentException(f"未知Agent: {agent_name}", self.name)
        module_path, class_name = spec
        import importlib

        try:
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            instance = cls()
            self._agent_instances[agent_name] = instance
            return instance
        except Exception as e:
            raise AgentException(f"加载 Agent {agent_name} 失败: {e}", self.name) from e

    @property
    def agents(self) -> dict[str, Any]:
        """仅用于 capability_map 等元数据查询时按需展开（一般不全调）"""
        return {name: self.get_agent(name) for name in get_agent_registry()}

    async def process(self, request: dict[str, Any]) -> dict[str, Any]:
        """处理请求 - 支持并行执行 + 实时事件推送 + O5 链路追踪"""
        task_id = request.get("_task_id") or event_bus.new_task_id()
        # O5: 若上层未设 trace_context，在此补建（单 Agent 调用时）
        tid = request.get("_trace_id") or task_id
        with trace_context(tid):
            logger.info(
                f"协调器收到请求: {request.get('task', 'unknown')}, task_id={task_id}"
            )

            await event_bus.publish(
                task_id, {"type": "start", "task_id": task_id, "trace_id": tid}
            )

            agents_needed = self.planner.identify_agents(request)
            if not agents_needed:
                agents_needed = await self._llm_route(request)
            # 补全缺失上游（静态依赖表闭包不完整会误报循环依赖）
            completed = self.planner.complete_upstream(agents_needed)
            if completed != agents_needed:
                logger.info(f"自动补全上游Agents: {agents_needed} -> {completed}")
                agents_needed = completed
            logger.info(f"需要的Agents: {agents_needed}")
            await event_bus.publish(
                task_id, {"type": "planned", "agents": agents_needed}
            )

            subtasks = self.planner.decompose_task(request, agents_needed)
            logger.info(f"分解为 {len(subtasks)} 个子任务")

            # 注入 task_id 供 _execute_single_task 发布事件 + trace
            for t in subtasks:
                t["_task_id"] = task_id
                t["_trace_id"] = tid

            execution_plan = self.planner.analyze_dependencies(subtasks)
            results = await self._execute_plan_parallel(execution_plan, task_id)
            final_result = self._integrate_results(results)
            final_result["task_id"] = task_id
            final_result["trace_id"] = tid

            await event_bus.publish(
                task_id, {"type": "done", "result": final_result, "trace_id": tid}
            )
            return final_result

    async def _execute_plan_parallel(
        self, execution_plan: list[dict], task_id: str = ""
    ) -> list[dict]:
        """并行执行计划，并将上游 Agent 结果注入下游任务请求"""
        results = []
        completed = set()
        context: dict[str, dict[str, Any]] = {}

        levels = self._group_by_level(execution_plan)

        for level_idx, level_tasks in enumerate(levels):
            logger.info(f"执行第 {level_idx + 1} 层，{len(level_tasks)} 个任务")

            prepared_tasks = [
                self._inject_upstream(task, context) for task in level_tasks
            ]

            if len(prepared_tasks) == 1:
                task = prepared_tasks[0]
                result = await self._execute_single_task(task)
                results.append(result)
                completed.add(task["agent"])
                if result.get("status") == "success":
                    context[task["agent"]] = result["result"]
            else:
                tasks = [self._execute_single_task(t) for t in prepared_tasks]
                level_results = await asyncio.gather(*tasks, return_exceptions=True)

                for i, result in enumerate(level_results):
                    task = prepared_tasks[i]
                    if isinstance(result, Exception):
                        logger.error(f"任务 {task['agent']} 失败: {result}")
                        results.append(
                            {
                                "agent": task["agent"],
                                "result": {"error": str(result)},
                                "status": "failed",
                            }
                        )
                    else:
                        results.append(result)
                        if result.get("status") == "success":
                            context[task["agent"]] = result["result"]
                    completed.add(task["agent"])

        return results

    def _inject_upstream(self, task: dict, context: dict[str, dict[str, Any]]) -> dict:
        """将上游 Agent 的成功结果注入当前任务请求

        字段级注入走声明式映射 UPSTREAM_FIELD_MAP（差距 #3）：
        {下游 agent: {目标字段: (上游 agent, 源字段)}}——新增数据流
        加一行表项即可，不再改 if 链。调用方显式传入的字段优先
        （目标字段不存在时才填充）。
        """
        deps = task.get("dependencies", [])
        if not deps:
            return task

        request = dict(task.get("request") or {})
        upstream: dict[str, Any] = {}
        for dep in deps:
            if dep in context:
                upstream[dep] = context[dep]

        if upstream:
            request["upstream_results"] = upstream
            for field, (up_agent, src_field) in UPSTREAM_FIELD_MAP.get(
                task["agent"], {}
            ).items():
                if request.get(field):
                    continue  # 调用方显式传入优先
                src = upstream.get(up_agent) or {}
                if src.get(src_field):
                    request[field] = src[src_field]

        task = dict(task)
        task["request"] = request
        return task

    def _group_by_level(self, execution_plan: list[dict]) -> list[list[dict]]:
        """按依赖层级分组任务"""
        levels = []
        completed = set()
        remaining = list(execution_plan)

        while remaining:
            current_level = []
            still_remaining = []

            for task in remaining:
                dependencies = task.get("dependencies", [])
                if all(dep in completed for dep in dependencies):
                    current_level.append(task)
                else:
                    still_remaining.append(task)

            if not current_level:
                cycle_agents = [t["agent"] for t in remaining]
                logger.error(f"检测到循环依赖，涉及Agent: {cycle_agents}")
                raise AgentException(
                    f"任务存在循环依赖，无法调度: {cycle_agents}", self.name
                )

            levels.append(current_level)
            for task in current_level:
                completed.add(task["agent"])
            remaining = still_remaining

        return levels

    async def _execute_single_task(self, task: dict) -> dict:
        """执行单个任务（O5: span 包裹记录 agent + 耗时）"""
        agent_name = task["agent"]
        agent = self.get_agent(agent_name)  # 懒加载

        logger.info(f"执行Agent: {agent_name}")
        task_id = task.get("_task_id", "")
        if task_id:
            await event_bus.publish(
                task_id,
                {
                    "type": "agent_start",
                    "agent": agent_name,
                    "trace_id": task.get("_trace_id", ""),
                },
            )
        try:
            with span(agent_name):
                result = await agent.process(task["request"])
            logger.info(f"Agent {agent_name} 执行成功")
            if task_id:
                await event_bus.publish(
                    task_id,
                    {"type": "agent_done", "agent": agent_name, "status": "success"},
                )
            return {"agent": agent_name, "result": result, "status": "success"}
        except Exception as e:
            logger.error(f"Agent {agent_name} 执行失败: {e}")
            if task_id:
                await event_bus.publish(
                    task_id,
                    {
                        "type": "agent_done",
                        "agent": agent_name,
                        "status": "failed",
                        "error": str(e),
                    },
                )
            raise

    def _integrate_results(self, results: list[dict]) -> dict[str, Any]:
        """整合结果"""
        integrated = {
            "agents_used": [],
            "results": {},
            "status": "success",
            "failed_agents": [],
        }

        for result in results:
            agent_name = result["agent"]
            integrated["agents_used"].append(agent_name)
            integrated["results"][agent_name] = result["result"]

            if result.get("status") == "failed":
                integrated["failed_agents"].append(agent_name)

        if integrated["failed_agents"]:
            integrated["status"] = "partial_failure"

        return integrated

    async def _llm_route(self, request: dict[str, Any]) -> list[str]:
        """兜底路由：关键词表零命中时，LLM 从能力清单中选择 Agent

        仅在 identify_agents 零命中时调用 — 关键词命中路径保持
        确定性（零成本、P1-7 回归锁定）。LLM 调用失败 / 非法 JSON /
        未知名一律返回 []，维持修复前行为：process() 空成功、
        process_simple() 抛"未知任务类型"。
        """
        agents = get_agent_registry()
        capability_lines = "\n".join(
            f"- {name}: {cap.get('description', '')}"
            f"（tasks: {', '.join(cap.get('tasks', []))}）"
            for name, cap in self.planner.get_capability_map().items()
            if name in agents
        )
        prompt = (
            f"用户请求：{request.get('task', '')}\n"
            f"附加内容：{str(request.get('content', ''))[:500]}\n\n"
            f"能力清单：\n{capability_lines}"
        )
        try:
            text = await self.call_llm(prompt, _ROUTING_SYSTEM_PROMPT, temperature=0.0)
            raw = text.strip()
            start, end = raw.find("{"), raw.rfind("}")
            if start == -1 or end <= start:
                logger.warning(f"LLM路由返回无法解析，回退零命中行为: {raw[:120]}")
                return []
            payload = json.loads(raw[start : end + 1])
            candidates = payload.get("agents", []) if isinstance(payload, dict) else []
            if not isinstance(candidates, list):
                logger.warning("LLM路由返回格式不符，回退零命中行为")
                return []
            valid = [a for a in candidates if isinstance(a, str) and a in agents]
            dropped = [a for a in candidates if a not in valid]
            if dropped:
                logger.warning(f"LLM路由含未知名已剔除: {dropped}")
            return valid
        except Exception as e:  # noqa: BLE001 兜底不得让主流程崩溃，一律回退零命中
            logger.warning(f"LLM路由调用失败，回退零命中行为: {e}")
            return []
        except json.JSONDecodeError:
            logger.warning("LLM路由返回非法JSON，回退零命中行为")
            return []

    async def process_simple(self, request: dict[str, Any]) -> dict[str, Any]:
        """简单处理 - 单Agent直接调用，覆盖全部 16 skill

        路由复用 planner 的 SKILL_KEYWORD_MAP（消除重复维护），不再本地建 agent_map。
        关键词零命中时走 _llm_route 兜底（仍为单 Agent 语义，取第一个）。
        """
        task = request.get("task", "")

        # 直接用 planner 关键词路由识别；零命中走 LLM 兜底（单 Agent 语义，取第一个）
        agents_needed = self.planner.identify_agents(request)
        if not agents_needed:
            agents_needed = await self._llm_route(request)
        if not agents_needed:
            raise AgentException(f"未知任务类型: {task}", self.name)

        agent_name = agents_needed[0]
        agent = self.get_agent(agent_name)  # 懒加载
        return await agent.process(request)

    def capability_map(self) -> dict[str, dict[str, Any]]:
        """返回能力地图"""
        return self.planner.get_capability_map()

    def workflow_templates(self) -> dict[str, dict[str, Any]]:
        """返回工作流模板"""
        return self.planner.get_workflow_templates()

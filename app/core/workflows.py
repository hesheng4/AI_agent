"""E5: 自定义工作流模型 — 用户可编排 Agent DAG，替代硬编码 WORKFLOW_TEMPLATES

存储: SQLite/PostgreSQL 的 JSON 字段（轻量，无需独立表）
格式: { id, name, nodes, edges, created_by, created_at }
- nodes: [{ id, agent, task, label }]
- edges: [{ source, target }]  (source → target = 数据依赖)
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.utils.logger import get_logger

logger = get_logger("core.workflows")

# 工作流存储目录（JSON 文件，轻量方案；生产可换 PostgreSQL JSONB）
_WORKFLOWS_DIR = Path("data/workflows")

# 安全约束: user_id 限 UUID hex / 安全字符；workflow_id 为 12 位 hex
# 防止 glob 模式注入与路径穿越（W1/W2）
_USER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_WORKFLOW_ID_RE = re.compile(r"^[0-9a-f]{12}$")

# update 允许覆盖的字段白名单（W3: 防字段污染，不可覆盖 id/created_by/created_at）
_UPDATABLE_FIELDS = {"name", "description", "nodes", "edges"}


def _validate_user_id(user_id: str) -> str:
    """校验 user_id 格式，阻断路径穿越与 glob 注入 (W1)"""
    if not user_id or not _USER_ID_RE.match(user_id):
        raise ValueError(f"非法 user_id: {user_id!r}")
    return user_id


def _validate_workflow_id(workflow_id: str) -> str:
    """校验 workflow_id 为 12 位 hex，阻断 glob 通配注入 (W2)"""
    if not workflow_id or not _WORKFLOW_ID_RE.match(workflow_id):
        raise ValueError(f"非法 workflow_id: {workflow_id!r}")
    return workflow_id


def _ensure_dir() -> None:
    _WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)


def _workflow_path(user_id: str, workflow_id: str) -> Path:
    """构造精确文件路径，避免 glob 跨用户匹配 (W2)"""
    return (
        _WORKFLOWS_DIR
        / f"{_validate_user_id(user_id)}_{_validate_workflow_id(workflow_id)}.json"
    )


def list_workflows(user_id: str) -> list[dict[str, Any]]:
    """列出用户的所有工作流
    (W1: 校验 user_id; T3: iterdir+startswith 替代 glob 风格统一)
    """
    _ensure_dir()
    uid = _validate_user_id(user_id)
    prefix = f"{uid}_"
    result = []
    for f in _WORKFLOWS_DIR.iterdir():
        if not f.name.startswith(prefix) or not f.name.endswith(".json"):
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            result.append(data)
        except Exception as e:
            logger.warning(f"工作流文件解析失败 (跳过): {f.name}, err={e}")
    return sorted(result, key=lambda x: x.get("updated_at", ""), reverse=True)


def get_workflow(user_id: str, workflow_id: str) -> dict[str, Any] | None:
    """获取单个工作流 (R3: 精确路径读取，不再 glob 跨用户)

    通过 (user_id, workflow_id) 双校验直接定位文件，消除越权读取风险。
    所有调用方均已传入 user_id。
    """
    _ensure_dir()
    path = _workflow_path(user_id, workflow_id)  # 内含双重格式校验
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"工作流文件解析失败: {path.name}, err={e}")
        return None


def create_workflow(user_id: str, data: dict[str, Any]) -> dict[str, Any]:
    """创建工作流 (W1: 校验 user_id)"""
    _ensure_dir()
    _validate_user_id(user_id)
    workflow_id = uuid.uuid4().hex[:12]
    now = datetime.now(UTC).isoformat()
    workflow = {
        "id": workflow_id,
        "name": data.get("name", "Untitled Workflow"),
        "description": data.get("description", ""),
        "nodes": data.get("nodes", []),
        "edges": data.get("edges", []),
        "created_by": user_id,
        "created_at": now,
        "updated_at": now,
    }
    _save_workflow(user_id, workflow_id, workflow)
    logger.info(f"工作流创建: id={workflow_id}, name={workflow['name']}")
    return workflow


def update_workflow(
    user_id: str, workflow_id: str, data: dict[str, Any]
) -> dict[str, Any] | None:
    """更新工作流 (W3: 仅白名单字段可覆盖，防 id/created_by/created_at 污染)"""
    existing = get_workflow(user_id, workflow_id)
    if not existing or existing.get("created_by") != user_id:
        return None
    # 白名单过滤: 仅允许 _UPDATABLE_FIELDS 中的键
    for key in _UPDATABLE_FIELDS:
        if key in data:
            existing[key] = data[key]
    existing["updated_at"] = datetime.now(UTC).isoformat()
    _save_workflow(user_id, workflow_id, existing)
    return existing


def delete_workflow(user_id: str, workflow_id: str) -> bool:
    """删除工作流 (W1: user_id 校验 + 精确路径，不再 glob 跨用户)"""
    _ensure_dir()
    uid = _validate_user_id(user_id)
    wid = _validate_workflow_id(workflow_id)
    path = _WORKFLOWS_DIR / f"{uid}_{wid}.json"
    if not path.exists():
        return False
    try:
        # 复核归属权，防同名文件误删
        wf = json.loads(path.read_text(encoding="utf-8"))
        if wf.get("created_by") != uid:
            logger.warning(f"删除拒绝: 文件归属不符, path={path.name}")
            return False
        path.unlink()
        return True
    except Exception as e:
        logger.error(f"删除工作流失败: {path.name}, err={e}")
        return False


def workflow_to_execution_plan(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    """将工作流 DAG 转换为 coordinator 的 execution_plan 格式

    execution_plan: [{ agent, request, dependencies }]
    W4: 检测自环/循环依赖，抛 ValueError 由 API 层返回 400。
    R2: 检测重复 agent 名（coordinator context 按 agent 名索引，重复会互相覆盖）。
    R4: 过滤空 id 节点，避免污染 deps_map 与 DFS。
    """
    raw_nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])

    # R4: 过滤无 id 或 id 为空的节点
    nodes = [n for n in raw_nodes if n.get("id")]
    if len(nodes) != len(raw_nodes):
        logger.warning(f"工作流含 {len(raw_nodes) - len(nodes)} 个无 id 节点，已忽略")

    node_ids = {n["id"] for n in nodes}

    # R2: 重复 agent 名检测 — coordinator 的 context[agent] 会被同名 agent 覆盖
    seen_agents: dict[str, str] = {}
    for n in nodes:
        agent = n.get("agent", "")
        if not agent:
            raise ValueError(f"节点 {n.get('id')} 缺少 agent 字段")
        if agent in seen_agents:
            raise ValueError(
                f"重复 agent 名 '{agent}'：节点 {seen_agents[agent]} 与 {n['id']}。"
                "coordinator 按(agent)名索引上游结果，同名节点会互相覆盖，"
                "请改用不同 agent 或合并节点。"
            )
        seen_agents[agent] = n["id"]

    # W4a: 自环检测
    for edge in edges:
        if edge.get("source") == edge.get("target") and edge.get("source"):
            raise ValueError(f"自环依赖: {edge.get('source')}")

    # 构建邻接表: target -> [sources]
    deps_map: dict[str, list[str]] = {}
    for edge in edges:
        target = edge.get("target", "")
        source = edge.get("source", "")
        if target and source:
            deps_map.setdefault(target, []).append(source)

    # W4b: 循环检测 (DFS 三色标记)
    # R1: color 默认值改 white，避免孤立 target 被误判为已访问而漏检循环
    white, gray, black = 0, 1, 2
    color: dict[str, int] = {nid: white for nid in node_ids}

    def dfs(node: str) -> None:
        color[node] = gray
        # 邻接: node -> 它作为 source 指向的 targets
        for tgt, srcs in deps_map.items():
            if node in srcs:
                tgt_color = color.get(tgt, white)  # R1: 未知节点视为 white
                if tgt_color == gray:
                    raise ValueError(f"循环依赖: {node} -> {tgt}")
                if tgt_color == white:
                    if tgt not in color:
                        # target 不在 node_ids 中（悬空边），跳过但不报错
                        continue
                    dfs(tgt)
        color[node] = black

    for nid in node_ids:
        if color[nid] == white:
            dfs(nid)

    # 转换为 execution_plan
    plan = []
    for node in nodes:
        node_id = node["id"]
        agent = node["agent"]
        task = node.get("task", "")
        # dependencies 用 agent 名（coordinator 约定，且 R2 已保证唯一）
        dep_agents = []
        for dep_id in deps_map.get(node_id, []):
            for n in nodes:
                if n["id"] == dep_id:
                    dep_agents.append(n["agent"])
                    break
        plan.append(
            {
                "agent": agent,
                "request": {"task": task},
                "dependencies": dep_agents,
            }
        )
    return plan


def _save_workflow(user_id: str, workflow_id: str, data: dict[str, Any]) -> None:
    """W5: 原子写入 — 先写临时文件再 rename，防中途崩溃产生半截 JSON
    R6: rename 失败时清理临时文件，避免垃圾累积
    """
    _validate_user_id(user_id)
    _validate_workflow_id(workflow_id)
    filename = f"{user_id}_{workflow_id}.json"
    final_path = _WORKFLOWS_DIR / filename
    tmp_path = _WORKFLOWS_DIR / f".{filename}.tmp"
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    tmp_path.write_text(payload, encoding="utf-8")
    try:
        # os.replace: Windows 上同卷原子替换，跨卷退化为非原子
        os.replace(tmp_path, final_path)
    except Exception:
        # R6: replace 失败时清理临时文件，避免残留
        try:
            tmp_path.unlink()
        except Exception:
            pass
        raise

"""AgentArtifactService — Agent 产出物持久化（credibility-convergence v1 步骤 6）

能力面：创建 → 列表（按 agent 筛选）→ 单条读取（重新导出 payload）→ 删除。
不做语义检索（Milvus 本机未必在跑，不引入新失败模式）。

服务层方法自行管理事务（commit），与 LibraryService 语义一致；
路由层只负责参数解析、鉴权与响应序列化。
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifacts import AgentArtifact
from app.utils.logger import get_logger

logger = get_logger("services.artifacts")


class ArtifactError(Exception):
    """Artifacts 服务层异常基类（保留 status_code 供路由层映射）"""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ArtifactNotFoundError(ArtifactError):
    def __init__(self, message: str = "产出物不存在"):
        super().__init__(message, status_code=404)


def artifact_to_dict(a: AgentArtifact) -> dict[str, Any]:
    """AgentArtifact -> 响应 dict（payload 以 JSON 透传）"""
    return {
        "id": a.id,
        "agent": a.agent,
        "title": a.title,
        "payload": a.payload,
        "created_at": str(a.created_at) if a.created_at else None,
    }


class ArtifactService:
    """Agent 产出物 CRUD"""

    async def create_artifact(
        self,
        db: AsyncSession,
        user_id: str,
        *,
        agent: str,
        title: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        artifact = AgentArtifact(
            id=str(uuid.uuid4()),
            user_id=user_id,
            agent=agent,
            title=title,
            payload=payload,
        )
        db.add(artifact)
        await db.commit()
        await db.refresh(artifact)
        logger.info(f"用户 {user_id} 保存产出物: agent={agent}, title={title[:50]}")
        return artifact_to_dict(artifact)

    async def list_artifacts(
        self,
        db: AsyncSession,
        user_id: str,
        *,
        agent: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """按创建时间倒序列出产出物，支持按 agent 筛选"""
        query = select(AgentArtifact).where(AgentArtifact.user_id == user_id)
        if agent:
            query = query.where(AgentArtifact.agent == agent)
        query = (
            query.order_by(AgentArtifact.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(query)
        return [artifact_to_dict(a) for a in result.scalars().all()]

    async def get_artifact(
        self, db: AsyncSession, user_id: str, artifact_id: str
    ) -> dict[str, Any]:
        """单条读取（重新导出用）；严格 user_id 隔离"""
        artifact = await self._find(db, user_id, artifact_id)
        if artifact is None:
            raise ArtifactNotFoundError()
        return artifact_to_dict(artifact)

    async def delete_artifact(
        self, db: AsyncSession, user_id: str, artifact_id: str
    ) -> None:
        artifact = await self._find(db, user_id, artifact_id)
        if artifact is None:
            raise ArtifactNotFoundError()
        await db.delete(artifact)
        await db.commit()
        logger.info(f"用户 {user_id} 删除产出物: {artifact_id}")

    async def _find(
        self, db: AsyncSession, user_id: str, artifact_id: str
    ) -> AgentArtifact | None:
        result = await db.execute(
            select(AgentArtifact).where(
                AgentArtifact.user_id == user_id,
                AgentArtifact.id == artifact_id,
            )
        )
        return result.scalar_one_or_none()

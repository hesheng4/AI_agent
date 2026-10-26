"""Agent 产出物持久化模型（credibility-convergence v1 步骤 6）

当前 8 张业务表没有任何一张存 Agent 产出，上周的审稿回复找不回来。
agent_artifacts 以通用 payload(JSON) 存各 Agent 的结构化产出，
能力面：创建 → 列表 → 按 agent/时间筛选 → 重新导出 → 删除。
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class AgentArtifact(Base):
    """Agent 产出物"""

    __tablename__ = "agent_artifacts"
    __table_args__ = (
        Index("ix_artifacts_user_agent_time", "user_id", "agent", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id"), nullable=False, index=True
    )
    agent: Mapped[str] = mapped_column(String, nullable=False)  # 产出该结果的 agent 名
    title: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

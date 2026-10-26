"""分享链接模型（credibility-convergence v1 步骤 7）

share_links 设计成通用 (resource_type, resource_id)，本轮只实现
library（整库分享）与 artifact（单产出物分享）两类。

安全纪律（对齐 refresh token）：
- DB 只存 sha256(token) 哈希，明文 token 仅在创建响应中返回一次
- TTL 默认 7 天，可空（永久）；显式撤销端点 DELETE /shares/{id}
- 接收方必须登录，不静默降级为公开
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class ShareLink(Base):
    """通用分享链接"""

    __tablename__ = "share_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id"), nullable=False, index=True
    )
    # library | artifact
    resource_type: Mapped[str] = mapped_column(String, nullable=False)
    # library 分享=owner_id；artifact 分享=artifact id
    resource_id: Mapped[str] = mapped_column(String, nullable=False)
    # sha256 hex
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # NULL = 永久
    revoked: Mapped[int] = mapped_column(Integer, default=0)  # 1 = 已撤销
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

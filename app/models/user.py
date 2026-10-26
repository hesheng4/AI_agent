import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.types import EncryptedString


class UserRole(enum.StrEnum):
    ADMIN = "admin"
    RESEARCHER = "researcher"
    STUDENT = "student"
    GUEST = "guest"


class User(Base):
    """用户表

    SQLAlchemy 2.0 Mapped[] 风格：实例属性类型由注解推导，
    消除 legacy Column 风格在 mypy strict 下的 Column[str] 连带错误
    （credibility-convergence 批次二）。列定义与原 legacy Column 等价
    （同名/同约束/同默认值；nullable 由 Mapped[...] 的 Optional 语义推导）。
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.GUEST)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    avatar: Mapped[str | None] = mapped_column(String, nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    institution: Mapped[str | None] = mapped_column(String, nullable=True)
    # 个人 API 配置（覆盖系统默认 LLM 配置）
    # api_key 使用 EncryptedString 透明加解密，数据库存储密文
    api_key: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    api_base_url: Mapped[str | None] = mapped_column(String, nullable=True)
    api_model: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

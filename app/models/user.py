import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, String, Text
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.types import EncryptedString


class UserRole(enum.StrEnum):
    ADMIN = "admin"
    RESEARCHER = "researcher"
    STUDENT = "student"
    GUEST = "guest"


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.GUEST)
    is_active = Column(Boolean, default=True)
    avatar = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    institution = Column(String, nullable=True)
    # 个人 API 配置（覆盖系统默认 LLM 配置）
    # api_key 使用 EncryptedString 透明加解密，数据库存储密文
    api_key = Column(EncryptedString, nullable=True)
    api_base_url = Column(String, nullable=True)
    api_model = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

import enum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.sql import func

from app.core.database import Base


class PlanType(enum.StrEnum):
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class UserAccount(Base):
    __tablename__ = "user_accounts"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), unique=True)
    plan = Column(Enum(PlanType), default=PlanType.FREE)
    balance = Column(Numeric(10, 2), default=0)
    api_calls_used = Column(Integer, default=0)
    tokens_used = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"))
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    api_calls = Column(Integer, default=0)
    tokens_used = Column(Integer, default=0)
    endpoint = Column(String)
    response_time = Column(Integer)

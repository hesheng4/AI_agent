import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import User
from app.utils.exceptions import ValidationException


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def authenticate_user(self, email: str, password: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        # 校验密码 + is_active 状态
        if not user or not verify_password(password, user.hashed_password):
            return None
        if not user.is_active:
            return None  # 被禁用的用户不能登录

        return user

    async def create_user(self, email: str, username: str, password: str) -> User:
        # 注册时校验用户名唯一性（业务层 + DB 兜底）
        existing = await self.db.execute(select(User).where(User.username == username))
        if existing.scalar_one_or_none():
            raise ValidationException("用户名已被占用")

        user = User(
            id=str(uuid.uuid4()),
            email=email,
            username=username,
            hashed_password=get_password_hash(password),
        )
        self.db.add(user)
        try:
            await self.db.commit()
        except IntegrityError as e:
            await self.db.rollback()
            # 并发场景下可能因 email 或 username 唯一约束失败
            raise ValidationException("邮箱或用户名已注册") from e
        await self.db.refresh(user)
        return user

    def create_token(self, user: User) -> str:
        return create_access_token(data={"sub": user.id, "email": user.email})

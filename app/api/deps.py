from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import check_rate_limit_middleware
from app.core.security import decode_access_token
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    inactive_exception = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Account is disabled",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    # 二次校验 is_active：防止用户被禁用后旧 token 仍可用
    if not user.is_active:
        raise inactive_exception

    return user


async def enforce_api_rate_limit(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """对 LLM 生成类端点按用户套餐限流（free=10/分钟 … enterprise=1000/分钟）

    依赖 get_current_user 的结果（同一请求内 FastAPI 会缓存，不会重复鉴权）。
    套餐查询失败不阻塞请求（按 free 档限流），限流本身由
    RATE_LIMIT_API_ENABLED 开关控制。
    """
    if not get_settings().RATE_LIMIT_API_ENABLED:
        return current_user

    plan = "free"
    try:
        from app.models.billing import UserAccount

        result = await db.execute(
            select(UserAccount.plan).where(UserAccount.user_id == current_user.id)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            plan = str(getattr(row, "value", row))
    except Exception:  # noqa: BLE001 — 套餐查询失败按 free 档，不阻塞业务
        pass

    await check_rate_limit_middleware(request, current_user.id, plan)
    return current_user

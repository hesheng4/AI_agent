import ipaddress
import secrets
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import get_settings
from app.core.cache import cache
from app.core.database import get_db
from app.core.rate_limit import rate_limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_password_hash,
    validate_password_complexity,
    verify_password,
)
from app.models.user import User
from app.services.auth import AuthService

router = APIRouter()
settings = get_settings()


# 允许的本地开发 host（DEBUG 模式下放行）
_DEV_ALLOWED_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _validate_api_base_url(
    base_url: str | None, *, allow_private: bool | None = None
) -> None:
    """校验用户提供的 OpenAI 兼容 API base_url，防 SSRF

    规则：
    - 必须是 http/https 且有 hostname
    - 默认拒绝私网/链路本地/环回/保留地址（防内网探测与云元数据 169.254.169.254）
    - allow_private=True 时放宽（仅用于 DEBUG 模式下的本地开发端点）
    - 不合法抛 HTTPException 400
    """
    if not base_url:
        return
    parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Base URL 格式非法，必须为 http(s)://<host>[:port]",
        )
    host = parsed.hostname
    relax = settings.DEBUG if allow_private is None else allow_private
    # DEBUG 模式下允许 localhost
    if relax and host in _DEV_ALLOWED_HOSTS:
        return
    try:
        # 同时按 IPv4/IPv6 解析；域名则尝试解析
        addr = ipaddress.ip_address(host)
    except ValueError:
        # 域名：解析后逐个 IP 校验
        import socket

        try:
            infos = socket.getaddrinfo(host, None)
        except socket.gaierror:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Base URL host 无法解析",
            )
        ips = {ipaddress.ip_address(info[4][0]) for info in infos}
        for addr in ips:
            if _is_disallowed_addr(addr, relax):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Base URL 指向内网/保留地址，禁止使用",
                )
        return
    if _is_disallowed_addr(addr, relax):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Base URL 指向内网/保留地址，禁止使用",
        )


def _is_disallowed_addr(addr: ipaddress._BaseAddress, allow_private: bool) -> bool:
    """是否为应拒绝的地址（非 DEBUG 模式下拒绝私网/环回/链路本地/保留段）"""
    if allow_private:
        # DEBUG 下仍拒绝链路本地（169.254.0.0/16 含云元数据）与未指定地址
        return addr.is_link_local or addr.is_unspecified
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_unspecified
        or addr.is_reserved
        or addr.is_multicast
    )


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)


def _login_fail_cache_key(email: str) -> str:
    return f"login_fail:{email.lower()}"


def _login_ip_cache_key(ip: str) -> str:
    return f"login_ip:{ip}"


async def _check_login_rate_limit(request: Request, email: str) -> None:
    """登录端点限流：IP 级速率 + 账户级失败锁定"""
    client_ip = request.client.host if request.client else "unknown"

    # IP 级限流：每分钟最多 LOGIN_IP_RATE_LIMIT 次
    ip_allowed = await rate_limiter.check_rate_limit(
        f"login_ip:{client_ip}",
        max_requests=settings.LOGIN_IP_RATE_LIMIT,
        window=60,
    )
    if not ip_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录请求过于频繁，请稍后再试",
        )

    # 账户级锁定：失败次数超过阈值则锁定
    fail_key = _login_fail_cache_key(email)
    fail_count_str = await cache.get(fail_key)
    fail_count = int(fail_count_str) if fail_count_str else 0
    if fail_count >= settings.LOGIN_MAX_FAILURES:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"登录失败次数过多，账户已锁定 "
                f"{settings.LOGIN_LOCKOUT_MINUTES} 分钟，请稍后再试"
            ),
        )


async def _record_login_failure(email: str) -> None:
    """记录登录失败，达到阈值时写入锁定 TTL"""
    fail_key = _login_fail_cache_key(email)
    fail_count_str = await cache.get(fail_key)
    fail_count = int(fail_count_str) if fail_count_str else 0
    fail_count += 1
    # 达到阈值时设置锁定 TTL；否则短 TTL 防止永久累积
    ttl = (
        settings.LOGIN_LOCKOUT_MINUTES * 60
        if fail_count >= settings.LOGIN_MAX_FAILURES
        else 3600
    )
    await cache.set(fail_key, fail_count, ttl=ttl)


async def _clear_login_failures(email: str) -> None:
    """登录成功后清除失败计数"""
    await cache.delete(_login_fail_cache_key(email))


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    role: str
    avatar: str | None = None
    bio: str | None = None
    institution: str | None = None
    api_key_configured: bool = False
    api_base_url: str | None = None
    api_model: str | None = None
    created_at: str | None = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_user(cls, user: User) -> "UserResponse":
        return cls(
            id=user.id,
            email=user.email,
            username=user.username,
            role=user.role.value if hasattr(user.role, "value") else str(user.role),
            avatar=user.avatar,
            bio=user.bio,
            institution=user.institution,
            api_key_configured=bool(user.api_key),
            api_base_url=user.api_base_url,
            api_model=user.api_model,
            created_at=user.created_at.isoformat() if user.created_at else None,
        )


class UpdateProfileRequest(BaseModel):
    username: str | None = None
    avatar: str | None = None
    bio: str | None = None
    institution: str | None = None


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


# 重置令牌缓存 key 前缀
_RESET_TOKEN_PREFIX = "pwd_reset:"
# 重置令牌有效期（秒）
_RESET_TOKEN_TTL = 30 * 60  # 30 分钟


def _reset_token_cache_key(token: str) -> str:
    return f"{_RESET_TOKEN_PREFIX}{token}"


class UpdateApiConfigRequest(BaseModel):
    api_key: str | None = None
    api_base_url: str | None = Field(None, description="OpenAI 兼容 API Base URL")
    api_model: str | None = Field(
        None, description="模型名称，如 gpt-4o、deepseek-chat"
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest, raw_request: Request, db: AsyncSession = Depends(get_db)
):
    # 限流与账户锁定检查
    await _check_login_rate_limit(raw_request, request.email)

    auth_service = AuthService(db)
    user = await auth_service.authenticate_user(request.email, request.password)

    if not user:
        await _record_login_failure(request.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
        )

    # 登录成功，清除失败计数
    await _clear_login_failures(request.email)

    access_token = auth_service.create_token(user)
    refresh_token = create_refresh_token(data={"sub": user.id, "email": user.email})
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/register", response_model=UserResponse)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    auth_service = AuthService(db)

    result = await db.execute(select(User).where(User.email == request.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="该邮箱已注册"
        )

    # S3/M4 — 密码复杂度校验
    try:
        validate_password_complexity(request.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    user = await auth_service.create_user(
        request.email, request.username, request.password
    )
    return UserResponse.from_user(user)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token_endpoint(
    request: RefreshRequest, db: AsyncSession = Depends(get_db)
):
    """以 refresh token 换取新 access token（S1/M2）

    refresh token 必须有效且 `type=refresh`；用户仍须存在且 is_active。
    换取后 issuing 新的 access + refresh 对，旧 refresh 由客户端丢弃。
    """
    payload = decode_refresh_token(request.refresh_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token 无效或已过期",
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token 缺少 subject",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已禁用",
        )

    new_access = create_access_token(data={"sub": user.id, "email": user.email})
    new_refresh = create_refresh_token(data={"sub": user.id, "email": user.email})
    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.from_user(current_user)


class PatchMeRequest(BaseModel):
    """PATCH /me 请求体：所有字段可选，支持部分更新（含 API 配置）"""

    username: str | None = None
    avatar: str | None = None
    bio: str | None = None
    institution: str | None = None
    api_key: str | None = None
    api_base_url: str | None = None
    api_model: str | None = None


@router.patch("/me", response_model=UserResponse)
async def patch_me(
    request: PatchMeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """部分更新当前用户资料（前端 PATCH /auth/me 对应此端点）"""
    if request.username is not None:
        result = await db.execute(
            select(User).where(
                User.username == request.username, User.id != current_user.id
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
            )
        current_user.username = request.username

    if request.avatar is not None:
        current_user.avatar = request.avatar
    if request.bio is not None:
        current_user.bio = request.bio
    if request.institution is not None:
        current_user.institution = request.institution
    if request.api_key is not None:
        current_user.api_key = request.api_key
    if request.api_base_url is not None:
        current_user.api_base_url = request.api_base_url
    if request.api_model is not None:
        current_user.api_model = request.api_model

    await db.commit()
    await db.refresh(current_user)
    return UserResponse.from_user(current_user)


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新个人资料"""
    if request.username is not None:
        # 检查用户名是否已被占用
        result = await db.execute(
            select(User).where(
                User.username == request.username, User.id != current_user.id
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken"
            )
        current_user.username = request.username

    if request.avatar is not None:
        current_user.avatar = request.avatar
    if request.bio is not None:
        current_user.bio = request.bio
    if request.institution is not None:
        current_user.institution = request.institution

    await db.commit()
    await db.refresh(current_user)
    return UserResponse.from_user(current_user)


@router.put("/password", response_model=dict)
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """修改密码"""
    if not verify_password(request.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    # S3/M4 — 密码复杂度校验
    try:
        validate_password_complexity(request.new_password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    current_user.hashed_password = get_password_hash(request.new_password)
    await db.commit()
    return {"message": "Password changed successfully"}


@router.post("/forgot-password", response_model=dict)
async def forgot_password(
    request: ForgotPasswordRequest,
    raw_request: Request,
    db: AsyncSession = Depends(get_db),
):
    """忘记密码 — 生成重置令牌

    无论邮箱是否注册，都返回相同响应（防止邮箱枚举）。
    DEBUG 模式下为本地/私有部署返回令牌；生产环境必须通过安全通道发送。
    """
    # 限流：每 IP 每分钟最多 5 次
    client_ip = raw_request.client.host if raw_request.client else "unknown"
    ip_allowed = await rate_limiter.check_rate_limit(
        f"forgot_pwd_ip:{client_ip}",
        max_requests=5,
        window=60,
    )
    if not ip_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="请求过于频繁，请稍后再试",
        )

    # 查找用户
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        # 不透露邮箱是否存在，直接返回成功
        return {"message": "如果该邮箱已注册，重置邮件已发送"}

    # 生成安全随机令牌
    token = secrets.token_urlsafe(32)
    # 存入缓存：token → user_id，30 分钟有效
    await cache.set(_reset_token_cache_key(token), user.id, ttl=_RESET_TOKEN_TTL)

    if settings.DEBUG:
        return {
            "message": "重置令牌已生成",
            "token": token,
            "expires_in": _RESET_TOKEN_TTL,
        }

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="生产环境请配置邮件服务发送重置链接",
    )


@router.post("/reset-password", response_model=dict)
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """重置密码 — 使用重置令牌设置新密码"""
    # 从缓存取出 user_id
    user_id = await cache.get(_reset_token_cache_key(request.token))
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="重置令牌无效或已过期，请重新申请",
        )

    # 查找用户
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户不存在",
        )

    # 更新密码
    # S3/M4 — 密码复杂度校验
    try:
        validate_password_complexity(request.new_password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    user.hashed_password = get_password_hash(request.new_password)
    await db.commit()

    # 删除已使用的令牌（一次性）
    await cache.delete(_reset_token_cache_key(request.token))

    # 清除该用户的登录失败计数
    await _clear_login_failures(user.email)

    return {"message": "密码重置成功，请使用新密码登录"}


@router.put("/api-config", response_model=UserResponse)
async def update_api_config(
    request: UpdateApiConfigRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """配置个人 API 密钥（接入自己的 LLM API）"""
    # SSRF 防护：校验 base_url 不指向内网/保留地址
    _validate_api_base_url(request.api_base_url)
    if request.api_key is not None:
        current_user.api_key = request.api_key
    if request.api_base_url is not None:
        current_user.api_base_url = request.api_base_url
    if request.api_model is not None:
        current_user.api_model = request.api_model

    await db.commit()
    await db.refresh(current_user)
    return UserResponse.from_user(current_user)


@router.post("/test-api-config", response_model=dict)
async def test_api_config(
    request: UpdateApiConfigRequest,
    current_user: User = Depends(get_current_user),
):
    """测试个人 API 配置是否可用"""
    from openai import AsyncOpenAI

    api_key = request.api_key or current_user.api_key
    base_url = request.api_base_url or current_user.api_base_url
    model = request.api_model or current_user.api_model

    if not api_key or not base_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please configure API Key and Base URL first",
        )

    # SSRF 防护：统一走 _validate_api_base_url（含内网/保留地址拒绝）
    _validate_api_base_url(base_url)

    try:
        async with AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=15.0,
        ) as client:
            response = await client.chat.completions.create(
                model=model or "gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5,
            )
        return {
            "success": True,
            "message": "API connection successful",
            "model": response.model,
            "response_preview": (
                response.choices[0].message.content[:50] if response.choices else ""
            ),
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"API connection failed: {str(e)}",
            "model": model,
            "response_preview": "",
        }


@router.get("/health")
async def health_check():
    return {"status": "healthy"}

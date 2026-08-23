import hashlib
import re
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _prehash_password(password: str) -> str:
    """对长密码做 SHA-256 预哈希，规避 bcrypt 72 字节限制

    bcrypt 截断超长密码会静默弱化安全性；先用 SHA-256 把任意长度密码
    压缩为 64 字符十六进制串（小于 72 字节），再交给 bcrypt。
    """
    if not isinstance(password, str):
        raise ValueError("密码必须是字符串")
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(_prehash_password(plain_password), hashed_password)
    except (ValueError, TypeError):
        return False


def get_password_hash(password: str) -> str:
    return pwd_context.hash(_prehash_password(password))


# S3/M4 — 密码复杂度策略
# 规则：至少 8 字符（已在 Field 层强制），且至少包含以下三类中的两类：
#   小写字母 / 大写字母 / 数字 / 特殊字符。
# 不强制四类全有，避免可用性下降；二类门槛抵御纯字母/纯数字弱口令。
_PASSWORD_CATEGORY_RE = [
    re.compile(r"[a-z]"),
    re.compile(r"[A-Z]"),
    re.compile(r"[0-9]"),
    re.compile(r"[^a-zA-Z0-9]"),
]


def validate_password_complexity(password: str) -> None:
    """校验密码复杂度；不达标抛 ValueError，由调用端转 HTTP 400。

    规则：≥ 4 类字符中至少出现 2 类。空串或非字符串显式拒绝。
    """
    if not isinstance(password, str) or not password:
        raise ValueError("密码不能为空")
    matched = sum(1 for rx in _PASSWORD_CATEGORY_RE if rx.search(password))
    if matched < 2:
        raise ValueError(
            "密码复杂度不足：需至少包含以下四类字符中的两类 "
            "（小写字母、大写字母、数字、特殊字符）"
        )


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """生成长效 refresh token（S1/M2）。

    与 access token 共用 SECRET_KEY，但通过 `type=refresh` 声明区分，
    防止两类令牌互换使用。默认有效期 REFRESH_TOKEN_EXPIRE_DAYS。
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """解码并校验 access token；返回 payload 或 None（非法/过期）。

    严格校验 `type=access` 声明，拒绝 refresh token 被用作 access。
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


def decode_refresh_token(token: str) -> dict | None:
    """解码并校验 refresh token；返回 payload 或 None。

    严格校验 `type=refresh` 声明，拒绝 access token 被用作 refresh。
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        if payload.get("type") != "refresh":
            return None
        return payload
    except JWTError:
        return None

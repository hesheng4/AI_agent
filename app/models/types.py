"""SQLAlchemy 自定义类型：敏感字段透明加解密

使用 Fernet (AES-128-CBC + HMAC) 对称加密。
- 写入数据库时自动加密
- 读取时自动解密返回明文
- 加密密钥缺失时（开发环境）退化为明文存储，并发出警告

这样上层业务代码无需感知加密逻辑。
"""

from typing import TYPE_CHECKING, Any

from sqlalchemy import String, TypeDecorator
from sqlalchemy.engine.interfaces import Dialect

from app.utils.logger import get_logger

if TYPE_CHECKING:
    from cryptography.fernet import Fernet

logger = get_logger("encrypted_type")

_fernet_cache: Fernet | None = None
_fernet_inited: bool = False


def _get_fernet() -> Fernet | None:
    """懒初始化 Fernet 客户端。无密钥时返回 None（明文模式）"""
    global _fernet_cache, _fernet_inited
    if _fernet_inited:
        return _fernet_cache
    _fernet_inited = True
    try:
        from app.config import get_settings

        key = get_settings().API_KEY_ENCRYPTION_KEY
        if not key:
            logger.warning("API_KEY_ENCRYPTION_KEY 未配置，敏感字段将以明文存储")
            return None
        from cryptography.fernet import Fernet

        _fernet_cache = Fernet(key.encode())
    except Exception as e:
        logger.error(f"初始化 Fernet 失败，敏感字段退化为明文: {e}")
        _fernet_cache = None
    return _fernet_cache


class EncryptedString(TypeDecorator[str]):
    """透明加解密的字符串类型

    数据库存储密文（含 "enc:" 前缀以区分明文），Python 层拿到明文。
    兼容旧明文数据：读取时若无 "enc:" 前缀则原样返回。
    """

    impl = String
    cache_ok = True

    def __init__(self, *args: Any, length: int = 512, **kwargs: Any) -> None:
        # 数据库列长度需容纳密文（明文长度 + ~100 字节 Fernet 开销）
        super().__init__(length=length, *args, **kwargs)

    def process_bind_param(
        self, value: str | None, dialect: Dialect
    ) -> str | None:
        if value is None or value == "":
            return value
        # 已经是密文格式则不重复加密
        if isinstance(value, str) and value.startswith("enc:"):
            return value
        fernet = _get_fernet()
        if fernet is None:
            return value  # 明文模式
        try:
            token = fernet.encrypt(value.encode("utf-8")).decode("ascii")
            return f"enc:{token}"
        except Exception as e:
            logger.error(f"加密失败，事务已回滚: {e}")
            raise

    def process_result_value(
        self, value: str | None, dialect: Dialect
    ) -> str | None:
        if value is None or value == "":
            return value
        if not (isinstance(value, str) and value.startswith("enc:")):
            return value  # 旧明文数据兼容
        fernet = _get_fernet()
        if fernet is None:
            # 密钥被撤回但库里有密文，无法解密
            logger.error("数据库存在密文但未配置加密密钥，无法解密")
            return None
        try:
            return fernet.decrypt(value[4:].encode("ascii")).decode("utf-8")
        except Exception as e:
            logger.error(f"解密失败: {e}")
            return None

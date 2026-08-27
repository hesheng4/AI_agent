"""差距 #6 回归：生产环境 Fernet 密钥校验 fail-fast

EncryptedString 在密钥缺失/畸形时会静默降级为明文落库
（`app/models/types.py:33,39`）。生产环境（非 DEBUG）的防线：
1. 空密钥 → validate_security 拒绝启动（原有检查）；
2. 非空但畸形密钥（Fernet 无法构造）→ 同样拒绝启动（本次新增），
   堵住「配置了但写错」绕过空检查、敏感字段明文落库的缺口；
3. 有效密钥 → 校验通过；
4. DEBUG 模式 → 不拦截（明文降级是开发态已知行为，仅 warn）。
"""

import pytest
from cryptography.fernet import Fernet

from app.config import Settings


def _prod_settings(**overrides) -> Settings:
    """构造非 DEBUG Settings 基线（绕过 .env，显式给全必填项）"""
    base = {
        "DEBUG": False,
        "SECRET_KEY": "test-secret-key-32-chars-long!!",
        "CORS_ORIGINS": ["https://example.com"],
    }
    base.update(overrides)
    return Settings(**base)


def test_prod_empty_fernet_key_rejected():
    """空密钥 → RuntimeError（原有检查，防回归）"""
    s = _prod_settings(API_KEY_ENCRYPTION_KEY="")
    with pytest.raises(RuntimeError, match="API_KEY_ENCRYPTION_KEY"):
        s.validate_security()


def test_prod_malformed_fernet_key_rejected():
    """非空但畸形的密钥（base64 合法但 Fernet 构造失败）→ RuntimeError"""
    import base64

    bad_key = base64.urlsafe_b64encode(b"0123456789abcdef")  # 非 32 字节 → 构造失败
    s = _prod_settings(API_KEY_ENCRYPTION_KEY=bad_key.decode())
    with pytest.raises(RuntimeError, match="有效的 Fernet 密钥"):
        s.validate_security()


def test_prod_garbage_fernet_key_rejected():
    """完全无效的字符串 → RuntimeError"""
    s = _prod_settings(API_KEY_ENCRYPTION_KEY="not-a-fernet-key")
    with pytest.raises(RuntimeError, match="有效的 Fernet 密钥"):
        s.validate_security()


def test_prod_valid_fernet_key_accepted():
    """有效 Fernet 密钥 → 校验通过"""
    key = Fernet.generate_key().decode()
    s = _prod_settings(API_KEY_ENCRYPTION_KEY=key)
    s.validate_security()  # 不抛异常即通过
    assert s.API_KEY_ENCRYPTION_KEY == key


def test_debug_mode_skips_fernet_checks():
    """DEBUG 模式空/畸形密钥都不拦截（开发态明文降级是已知行为）"""
    for bad in ("", "not-a-fernet-key"):
        s = _prod_settings(DEBUG=True, API_KEY_ENCRYPTION_KEY=bad)
        s.validate_security()  # 不抛异常

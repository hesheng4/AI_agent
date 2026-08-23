from functools import lru_cache

from pydantic import ConfigDict
from pydantic_settings import BaseSettings

# 视为未修改的默认 SECRET_KEY，生产环境必须替换
_INSECURE_SECRET_PREFIX = "your-secret-key"


class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "Research Agent Platform"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # 数据库配置
    DATABASE_URL: str = "sqlite+aiosqlite:///./research_agent.db"

    # ========== 数据库迁移配置 ==========
    # 启动时是否自动执行 `alembic upgrade head`
    # 默认 False（生产安全）：部署流程应显式执行 `alembic upgrade head`，便于审查与回滚
    # 开发环境可在 .env 中设为 True 方便自动迁移
    MIGRATION_ON_STARTUP: bool = False

    # Redis配置
    REDIS_URL: str = "redis://localhost:6379/0"

    # ========== 缓存后端配置 ==========
    # 后端选择: "memory" (进程内，单实例) / "redis" (分布式，多实例)
    CACHE_BACKEND: str = "memory"
    CACHE_KEY_PREFIX: str = "rap:"
    CACHE_DEFAULT_TTL: int = 1800
    # 仅 memory 后端生效：最大条目数
    CACHE_MAX_SIZE: int = 10000
    # LLM 调用结果缓存 TTL（秒），仅缓存 temperature=0 的确定性调用
    LLM_CACHE_TTL: int = 600

    # ========== 限流后端配置 ==========
    # 后端选择: "memory" / "redis"
    RATE_LIMIT_BACKEND: str = "memory"
    # Redis 不可用时限流降级策略: "allow" (放行，保证可用性) / "deny" (拒绝，保证安全)
    RATE_LIMIT_FALLBACK: str = "allow"
    # 是否对科研域（LLM 生成类）API 启用按用户套餐限流（RATE_LIMITS 表）
    RATE_LIMIT_API_ENABLED: bool = True

    # ========== 请求体大小限制（S2）==========
    # 全局 HTTP 请求体上限（字节）：超限直接 413，避免内存被恶意大 payload 耗尽
    MAX_REQUEST_BODY_BYTES: int = 2_000_000  # 2MB，覆盖论文全文+元数据
    # 单个内容字段字符上限：用于 Pydantic Field(max_length=...)
    # 论文全文通常 50k-200k 字符，500k 上限覆盖完整论文+图表说明，拒绝 MB 级恶意输入
    MAX_CONTENT_LENGTH: int = 500_000

    # JWT配置
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    # Refresh token（S1/M2）：长效刷新令牌，换取新 access token
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ========== 敏感数据加密 ==========
    # 用于加密用户 API Key 等敏感字段（Fernet），生产环境必须配置
    # 生成命令: python -c "from cryptography.fernet import Fernet;
    # print(Fernet.generate_key().decode())"
    API_KEY_ENCRYPTION_KEY: str = ""

    # ========== 登录防护 ==========
    # 登录失败锁定阈值：N 次失败后锁定账号 LOGIN_LOCKOUT_MINUTES 分钟
    LOGIN_MAX_FAILURES: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15
    # 登录 IP 限流：每个 IP 每分钟最多 LOGIN_IP_RATE_LIMIT 次
    LOGIN_IP_RATE_LIMIT: int = 20

    # ========== LLM 配置 ==========
    # 模式选择: "remote" (远程API) / "ascend" (本地昇腾NPU)
    LLM_MODE: str = "remote"

    # 远程 LLM 配置（LLM_MODE=remote 时使用）
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.xiaomimimo.com/v1"
    OPENAI_MODEL: str = "mimo-v2.5"

    # P1-O3: Agent 级模型覆盖 — 不同 Agent 用不同模型（质量/成本权衡）
    # JSON 格式: {"writing": "gpt-4o", "data": "claude-3.5-sonnet",
    #             "polishing": "mimo-v2.5"}
    # 为空时全部 Agent 共用 OPENAI_MODEL
    AGENT_MODEL_OVERRIDES: dict[str, str] = {}

    # P1-O3: Agent 级 token 预算上限（防止失控消耗）
    # 例: {"writing": 8000, "reviewer": 12000}；未声明的 Agent 用全局 max_tokens
    AGENT_TOKEN_BUDGETS: dict[str, int] = {}

    # E2: Agent 级 API 凭证隔离 — 不同 Agent 用不同 API Key + base_url + model
    # 用于多团队/多项目配额隔离，或不同 Agent 走不同供应商
    # 格式: {"writing": {"api_key": "sk-xxx", "base_url": "https://...",
    #                    "model": "gpt-4o"}}
    # 缺省字段回退到全局 OPENAI_API_KEY / OPENAI_BASE_URL / AGENT_MODEL_OVERRIDES
    AGENT_CREDENTIAL_OVERRIDES: dict[str, dict[str, str]] = {}

    # 昇腾 NPU LLM 配置（LLM_MODE=ascend 时使用）
    ASCEND_VLLM_BASE_URL: str = "http://127.0.0.1:8001/v1"
    ASCEND_LLM_MODEL: str = "Qwen/Qwen2.5-72B-Instruct"
    ASCEND_VLLM_TIMEOUT: float = 120.0
    # 张量并行度，根据 NPU 卡数设置（1/2/4/8）
    ASCEND_TP_SIZE: int = 4
    # vLLM-Ascend 最大模型长度
    ASCEND_MAX_MODEL_LEN: int = 8192

    # ========== Embedding 配置 ==========
    # 模式选择: "remote" (远程API) / "ascend_api" (vLLM-Ascend端点)
    # / "ascend_local" (torch_npu本地)
    EMBEDDING_MODE: str = "remote"

    # 远程 Embedding 配置
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_BASE_URL: str = ""
    EMBEDDING_MODEL: str = "text-embedding-ada-002"

    # 昇腾 Embedding 配置（EMBEDDING_MODE=ascend_api/ascend_local 时使用）
    ASCEND_EMBEDDING_MODEL: str = "BAAI/bge-large-zh-v1.5"
    ASCEND_EMBEDDING_LOCAL: bool = False  # 是否使用 torch_npu 本地推理
    ASCEND_EMBEDDING_DEVICE: int = 0  # NPU 设备编号

    # ========== 昇腾 NPU 高级配置 ==========
    # 可见 NPU 设备（逗号分隔，如 "0,1,2,3"）
    ASCEND_RT_VISIBLE_DEVICES: str = ""
    # 是否启用 ACL Graph 加速（推荐开启）
    ASCEND_ENABLE_ACL_GRAPH: bool = True
    # Task Queue 并行下发（推荐开启）
    ASCEND_TASK_QUEUE_ENABLE: int = 1
    # CPU 绑核优化
    ASCEND_CPU_AFFINITY: int = 0
    # 内存分配策略: "off" / "expandable_segments"
    ASCEND_ALLOC_CONF: str = "expandable_segments"

    # Milvus配置
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530

    # 计费配置
    BILLING_API_KEY: str = ""

    # CORS配置（生产环境必须显式配置允许来源）
    CORS_ORIGINS: list[str] = []

    # ========== 引用验证外部实查配置（P0-1）==========
    # CrossRef/OpenAlex 礼貌池 mailto（两者均免费无 key，建议填真实邮箱进入礼貌池）
    CROSSREF_MAILTO: str = "nature-skills@users.noreply.github.com"
    OPENALEX_MAILTO: str = "nature-skills@users.noreply.github.com"
    # 单次外部请求超时（秒）
    CITATION_VERIFY_TIMEOUT: float = 15.0
    # 验证结果缓存 TTL（秒，默认 24h；仅缓存 verified/not_found 确定性结果）
    CITATION_VERIFY_CACHE_TTL: int = 86400
    # 批量验证并发上限（礼貌池约束）
    CITATION_VERIFY_CONCURRENCY: int = 4

    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True,
    )

    def validate_security(self) -> None:
        """启动期安全校验：非 DEBUG 模式下必须满足的安全基线"""
        if not self.DEBUG and self.SECRET_KEY.startswith(_INSECURE_SECRET_PREFIX):
            raise RuntimeError(
                "SECRET_KEY 仍为默认值，生产环境必须在 .env 中设置一个安全的随机值"
            )
        if not self.DEBUG and len(self.SECRET_KEY) < 16:
            raise RuntimeError("SECRET_KEY 长度不足，至少需要 16 个字符")
        # DEBUG 模式下若使用默认 SECRET_KEY，自动生成随机值并警告
        import logging

        _logger = logging.getLogger("app.config")
        if self.DEBUG and self.SECRET_KEY.startswith(_INSECURE_SECRET_PREFIX):
            import secrets

            self.SECRET_KEY = secrets.token_hex(32)
            _logger.warning(
                "DEBUG 模式下已自动生成随机 SECRET_KEY，重启后失效；"
                "生产环境请在 .env 中设置 SECRET_KEY"
            )
        if not self.DEBUG and (not self.CORS_ORIGINS or "*" in self.CORS_ORIGINS):
            raise RuntimeError(
                "生产环境 CORS_ORIGINS 不能为空或包含 '*'，请显式配置允许的前端域名"
            )
        # 非调试模式下必须配置 API Key 加密密钥
        if not self.DEBUG and not self.API_KEY_ENCRYPTION_KEY:
            raise RuntimeError(
                "生产环境必须配置 API_KEY_ENCRYPTION_KEY，"
                "运行 python -c 'from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())' 生成"
            )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    # 实例化时立即校验，避免带病启动
    settings.validate_security()
    return settings

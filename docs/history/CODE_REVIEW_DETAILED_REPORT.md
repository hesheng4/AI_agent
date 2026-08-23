# 🔍 工业级代码审查报告

## 整体质量评分：7.2 / 10

**总评**：项目架构清晰，安全基础设施（JWT/bcrypt预哈希/Fernet加密/限流/登录锁定）已具备生产级意识，但存在**敏感信息硬编码泄露**、**CORS全开**、**密码重置令牌直接返回响应体**等高危问题，以及若干逻辑缺陷与可维护性隐患需整改。

---

## 🔴 严重问题

### 1. `.env` 文件硬编码真实 API Key 并提交至版本库

- **位置**：`.env` 第4行
- **问题**：`OPENAI_API_KEY=sk-cefjb1b5s2vtr2p7xswh8hnk51s6ee77i91jgairss84d6e7` — 真实密钥明文写入 `.env`，若该文件被提交到 Git 则密钥已泄露。攻击者可凭此调用 API 产生费用或窃取数据。
- **修复**：
  1. 立即轮换该 API Key（在服务商后台作废旧 Key、生成新 Key）
  2. 确认 `.env` 在 `.gitignore` 中（当前已有，但需检查历史提交是否已泄露）
  3. `.env` 中替换为占位符，真实值仅通过环境变量注入：
  ```bash
  # .env
  OPENAI_API_KEY=  # 通过环境变量注入，勿在此填写
  ```

### 2. CORS 配置 `allow_origins=["*"]` + `allow_credentials=True`

- **位置**：`app/config.py` 第113行 + `app/main.py` 第190-196行
- **问题**：`CORS_ORIGINS = ["*"]` 配合 `allow_credentials=True` 违反浏览器安全规范。任意恶意网站可携带用户 Cookie/Token 发起跨域请求，实现 CSRF 攻击，窃取用户数据或执行敏感操作。
- **修复**：
  ```python
  # app/config.py
  CORS_ORIGINS: list[str] = []  # 生产环境必须显式配置

  # app/config.py validate_security() 中追加
  if not self.DEBUG and (not self.CORS_ORIGINS or "*" in self.CORS_ORIGINS):
      raise RuntimeError(
          "生产环境 CORS_ORIGINS 不能为空或包含 '*'，请显式配置允许的前端域名"
      )
  ```

### 3. 密码重置令牌直接返回响应体

- **位置**：`app/api/v1/auth.py` 第344-348行
- **问题**：`forgot_password` 端点将重置令牌通过 HTTP 响应体直接返回（`"token": token`）。任何能截获响应的中间人或日志系统均可获取令牌，直接重置用户密码。正常流程应通过邮件/短信等安全通道投递。
- **修复**：
  ```python
  # 方案一（推荐）：通过邮件发送，响应体不返回 token
  # await send_reset_email(user.email, token)
  return {"message": "如果该邮箱已注册，重置邮件已发送"}

  # 方案二（私有部署无邮件服务时）：至少在非 DEBUG 模式下禁止返回
  if settings.DEBUG:
      return {"message": "重置令牌已生成", "token": token, "expires_in": _RESET_TOKEN_TTL}
  else:
      # 生产环境必须走邮件通道
      raise HTTPException(
          status_code=status.HTTP_501_NOT_IMPLEMENTED,
          detail="生产环境请配置邮件服务发送重置链接",
      )
  ```

### 4. 健康检查端点泄露内部错误详情

- **位置**：`app/main.py` 第305-373行
- **问题**：`/health` 端点将数据库/Redis/Milvus 连接失败的异常信息（`str(e)`）直接返回给调用方，可能泄露内部网络拓扑、连接串、版本等敏感信息。且该端点**无认证保护**，任何人可访问。
- **修复**：
  ```python
  except Exception as e:
      health["db_healthy"] = False
      health["db_error"] = "connection failed"  # 不暴露 str(e)
      logger.debug(f"DB health check failed: {e}")  # 仅日志记录详情
  ```

---

## 🟡 重要问题

### 5. `MemoryRateLimiter` 无过期清理机制，存在内存泄漏

- **位置**：`app/core/rate_limit.py` 第43-84行
- **问题**：`_requests` 字典只在使用时清理当前用户的过期条目，但**已不再请求的用户条目永远不会被清除**。长期运行后，大量僵尸用户 key 累积导致内存持续增长。
- **修复**：增加定期全局清理或 LRU 淘汰：
  ```python
  class MemoryRateLimiter(RateLimiterBackend):
      def __init__(self, max_users: int = 100_000):
          self._requests: dict[str, dict] = {}
          self._max_users = max_users

      async def check_rate_limit(self, user_id: str, max_requests: int = 60, window: int = 60) -> bool:
          # 超过容量时淘汰过期用户
          if len(self._requests) > self._max_users:
              self._global_cleanup(window)
          # ... 原有逻辑 ...

      def _global_cleanup(self, window: int):
          now = time.time()
          expired = [uid for uid, data in self._requests.items()
                     if not data["requests"] or now - data["requests"][-1] > window]
          for uid in expired:
              del self._requests[uid]
  ```

### 6. `reset_engine` 中 `asyncio.run(engine.dispose())` 在已有事件循环时不可靠

- **位置**：`app/core/database.py` 第46-56行
- **问题**：`asyncio.run()` 在事件循环已运行时抛出 `RuntimeError`，降级为 `loop.create_task()` 是 fire-and-forget，旧 engine 的连接可能短暂泄漏。且 `create_task` 返回的 task 未被 await，异常会被静默吞掉。
- **修复**：
  ```python
  async def reset_engine(new_url: str | None = None) -> None:
      global engine, async_session
      import logging
      logger = logging.getLogger("app.core.database")

      try:
          await engine.dispose()  # 直接 await，调用方应在 async 上下文中
      except Exception as e:
          logger.warning(f"reset_engine: 关闭旧 engine 失败: {e}")

      url = new_url or settings.DATABASE_URL
      engine = create_async_engine(url, echo=settings.DEBUG, pool_pre_ping=True, pool_recycle=3600)
      async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
  ```

### 7. `ChangePasswordRequest` 缺少 `old_password` 长度校验

- **位置**：`app/api/v1/auth.py` 第131-133行
- **问题**：`old_password: str` 无 `min_length`/`max_length` 约束。虽然 `verify_password` 内部有预哈希处理不会崩溃，但缺少长度校验意味着可提交超长字符串（DoS）或空字符串（无意义请求）。
- **修复**：
  ```python
  class ChangePasswordRequest(BaseModel):
      old_password: str = Field(min_length=1, max_length=128)
      new_password: str = Field(min_length=8, max_length=128)
  ```

### 8. `test_api_config` 端点用用户提供的 `api_key` 直接创建 OpenAI 客户端且未关闭

- **位置**：`app/api/v1/auth.py` 第424-445行
- **问题**：
  1. `AsyncOpenAI(api_key=api_key, ...)` 创建的客户端未用 `async with` 或显式 `close()`，httpx 连接泄漏。
  2. 用户提供的 `api_key` 未经校验直接传入，若为恶意 URL 可触发 SSRF。
- **修复**：
  ```python
  @router.post("/test-api-config", response_model=dict)
  async def test_api_config(request: UpdateApiConfigRequest, current_user: User = Depends(get_current_user)):
      from openai import AsyncOpenAI
      from urllib.parse import urlparse

      api_key = request.api_key or current_user.api_key
      base_url = request.api_base_url or current_user.api_base_url
      model = request.api_model or current_user.api_model

      if not api_key or not base_url:
          raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please configure API Key and Base URL first")

      # SSRF 防护：校验 base_url 合法性
      parsed = urlparse(base_url)
      if parsed.scheme not in ("http", "https") or not parsed.hostname:
          raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Base URL")

      try:
          async with AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=15.0) as client:
              response = await client.chat.completions.create(
                  model=model or "gpt-3.5-turbo",
                  messages=[{"role": "user", "content": "Hi"}],
                  max_tokens=5,
              )
              return {"success": True, "message": "API connection successful", "model": response.model}
      except Exception as e:
          return {"success": False, "message": f"API connection failed: {str(e)}", "model": model}
  ```

### 9. `User.id` 使用 `uuid4()` 但数据库主键列无长度约束

- **位置**：`app/models/user.py` 第20行
- **问题**：`id = Column(String, primary_key=True)` — `String` 无 `length` 约束。SQLite 不限制长度，但 PostgreSQL/MYSQL 下默认长度为空或不定，可能导致迁移兼容问题。同理 `billing.py` 的 `UserAccount.id`、`UsageRecord.id`。
- **修复**：
  ```python
  id = Column(String(36), primary_key=True)  # UUID4 标准格式为 36 字符
  ```

### 10. `BillingService.record_usage` 中 `UsageRecord` 缺少必填字段 `endpoint` 和 `response_time`

- **位置**：`app/core/billing.py` 第87-93行
- **问题**：`UsageRecord` 模型定义 `endpoint = Column(String)` 和 `response_time = Column(Integer)` 为非 nullable 列（无 `nullable=True`），但 `record_usage` 创建实例时未提供这两个字段，插入数据库时会触发 NOT NULL 约束错误。
- **修复**：
  ```python
  record = UsageRecord(
      id=str(uuid.uuid4()),
      user_id=user_id,
      api_calls=api_calls,
      tokens_used=tokens,
      endpoint="",          # 补充必填字段
      response_time=0,      # 补充必填字段
  )
  ```
  或在模型层标记 `nullable=True`。

---

## 🟢 优化建议

### 11. `verify_password` 异常捕获范围过宽

- **位置**：`app/core/security.py` 第24-28行
- **问题**：`except Exception` 吞掉所有异常（含 `TypeError`、`ValueError` 等编程错误），返回 `False` 可能掩盖 bug。应仅捕获密码校验相关的预期异常。
- **修复**：
  ```python
  def verify_password(plain_password: str, hashed_password: str) -> bool:
      try:
          return pwd_context.verify(_prehash_password(plain_password), hashed_password)
      except (ValueError, TypeError):
          return False
  ```

### 12. `UserResponse.from_user` 中 `created_at` 转为字符串丢失时区信息

- **位置**：`app/api/v1/auth.py` 第120行
- **问题**：`str(user.created_at)` 对 datetime 对象的序列化格式不可控，且丢失时区语义。应使用 ISO 8601 格式。
- **修复**：
  ```python
  created_at=user.created_at.isoformat() if user.created_at else None,
  ```

### 13. `EncryptedString.process_bind_param` 加密失败时返回 `None`

- **位置**：`app/models/types.py` 第70-72行
- **问题**：加密失败返回 `None` 会导致数据库写入 `NULL`，**原始值丢失且无报错**，用户 API Key 静默丢失是严重业务事故。
- **修复**：
  ```python
  except Exception as e:
      logger.error(f"加密失败: {e}")
      raise  # 让上层事务回滚，避免静默丢数据
  ```

### 14. `VectorStore._connect_lock` 在模块级实例中可能跨事件循环失效

- **位置**：`app/core/vector_store.py` 第41行
- **问题**：`asyncio.Lock()` 绑定到创建时的事件循环。在测试或热重载场景中，若新事件循环启动，旧 Lock 会抛 `RuntimeError`。
- **修复**：懒初始化 Lock：
  ```python
  def __init__(self):
      self._connect_lock: asyncio.Lock | None = None

  async def connect(self):
      if self._connected:
          return True
      if self._connect_lock is None:
          self._connect_lock = asyncio.Lock()
      async with self._connect_lock:
          # ...
  ```

### 15. `general_exception_handler` 中 DEBUG 模式下暴露完整异常信息

- **位置**：`app/main.py` 第240行
- **问题**：`str(exc)` 可能包含 SQL 语句、文件路径、内部堆栈等敏感信息。即使是 DEBUG 模式，对外暴露也有风险。
- **修复**：限制返回长度，或仅在 `localhost` 请求时返回详情：
  ```python
  "message": "服务器内部错误" if not settings.DEBUG else str(exc)[:500],
  ```

---

## 📋 整改优先级与落地建议

| 优先级 | 问题编号 | 行动项 | 预估工时 |
|--------|---------|--------|---------|
| P0 立即 | #1 | 轮换泄露的 API Key，清理 Git 历史 | 0.5h |
| P0 立即 | #2 | 收紧 CORS 配置，增加启动校验 | 0.5h |
| P0 立即 | #3 | 移除密码重置令牌的响应体返回，走安全通道 | 1h |
| P1 本迭代 | #4 | 健康检查脱敏，移除 `str(e)` | 0.5h |
| P1 本迭代 | #8 | test_api_config 修复连接泄漏 + SSRF 防护 | 1h |
| P1 本迭代 | #10 | 修复 UsageRecord 必填字段缺失 | 0.5h |
| P1 本迭代 | #13 | EncryptedString 加密失败改为抛异常 | 0.5h |
| P2 下迭代 | #5 | MemoryRateLimiter 增加全局清理 | 1h |
| P2 下迭代 | #6 | reset_engine 改为纯 async | 0.5h |
| P2 下迭代 | #7, #9 | 补充字段校验与列长度约束 | 0.5h |
| P3 可选 | #11, #12, #14, #15 | 异常范围收窄、时间格式、Lock 懒初始化、异常信息截断 | 1h |

**关键路径**：先解决 P0 安全问题（#1→#2→#3），再修复 P1 数据正确性问题（#10→#13→#8→#4），最后迭代优化 P2/P3。

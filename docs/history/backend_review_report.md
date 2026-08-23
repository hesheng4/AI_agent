# 后端代码审查与安全审计报告

> 审查时间：2026-06-19  
> 审查范围：app/main.py、app/core/database.py、app/services/auth.py、app/core/security.py、app/config.py、requirements.txt

---

## 一、代码问题

### P0 - 必须修复

#### 1. `database.py:43` — `engine.dispose()` fire-and-forget 可能导致连接泄漏

**文件**：`D:\AI_agent\app\core\database.py`  
**行号**：第43行  
**问题**：
```python
loop.create_task(engine.dispose())
```
`create_task` 是 fire-and-forget 调用，`engine.dispose()` 是异步操作，若事件循环在任务完成前结束，数据库连接可能未正确关闭，导致连接泄漏。

**修复建议**：
```python
# 方案1：直接 await（推荐）
try:
    engine = get_async_engine()
    await engine.dispose()
except RuntimeError:
    pass

# 方案2：确保任务完成
task = loop.create_task(engine.dispose())
loop.run_until_complete(task)  # 仅在同步上下文中
```

---

#### 2. `database.py:47` — `reset_engine()` 新建 engine 丢失连接池配置

**文件**：`D:\AI_agent\app\core\database.py`  
**行号**：第47行  
**问题**：
```python
engine = create_async_engine(url, echo=settings.DEBUG)
```
原 `engine`（第12-17行）配置了 `pool_pre_ping=True` 和 `pool_recycle=3600`，但 `reset_engine()` 新建的 `engine` 丢失了这两个关键配置，测试环境中可能导致数据库断开后无法自动重连。

**修复建议**：
```python
engine = create_async_engine(
    url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_recycle=3600,
)
```

---

### P1 - 建议修复

#### 3. `services/auth.py:32,48` — Service 层直接抛出 `HTTPException`

**文件**：`D:\AI_agent\app\services\auth.py`  
**行号**：第32行、第48行  
**问题**：
```python
raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已被占用")
```
Service 层应只抛出业务异常（`AppException`），由 API 层负责转换为 HTTP 响应。`HTTPException` 是 FastAPI 的 Web 层异常，泄漏到 Service 层导致层次混乱，且无法被 `AppException` 的全局异常处理器统一处理。

**修复建议**：
```python
from app.utils.exceptions import ValidationException

# 第32行
raise ValidationException("用户名已被占用")

# 第48行
raise ValidationException("邮箱或用户名已注册")
```

---

#### 4. `main.py:138-177` — 关闭逻辑 `except Exception: pass` 静默吞异常

**文件**：`D:\AI_agent\app\main.py`  
**行号**：第138行、第145行、第152行、第172行  
**问题**：
```python
try:
    ...
except Exception:
    pass
```
关闭 Redis、httpx、Milvus 时的异常被静默忽略，若关闭失败（如连接已断开），运维无法感知，可能导致资源泄漏排查困难。

**修复建议**：
```python
try:
    ...
except Exception as e:
    logger.warning(f"关闭 XXX 失败: {e}")
```

---

### P2 - 可选优化

#### 5. `database.py:6` — 模块顶层创建 `settings` 和 `engine`

**文件**：`D:\AI_agent\app\core\database.py`  
**行号**：第6行、第12-18行  
**问题**：模块导入时立即创建 `settings` 和 `engine`，若 `.env` 文件不存在或 `DATABASE_URL` 格式错误，会导致导入失败，不利于测试隔离。

**修复建议**：使用懒加载模式，将 `engine` 的创建延迟到首次使用时。

---

## 二、安全审计

### P0 - 安全高风险

#### 6. `config.py:45` — `SECRET_KEY` 默认值为弱密钥

**文件**：`D:\AI_agent\app\config.py`  
**行号**：第45行  
**问题**：
```
SECRET_KEY: str = "your-secret-key-change-in-production"
```
虽然 `validate_security()` 在非 DEBUG 模式下会拒绝默认值，但若开发者在 DEBUG=True 时部署，JWT 可被轻易伪造。

**现状**：`validate_security()` 已在 DEBUG 模式下自动生成随机 `SECRET_KEY`（第132-139行），这是正确的。但重启后 `SECRET_KEY` 会变化，导致所有已签发 JWT 失效。

**建议**：在文档中明确说明 DEBUG 模式下重启会导致 JWT 失效，生产环境必须设置 `SECRET_KEY`。

---

#### 7. `security.py:4` — 使用 `python-jose` 而非 `PyJWT`

**文件**：`D:\AI_agent\app\core\security.py`  
**行号**：第4行  
**问题**：`python-jose` 的安全记录不如 `PyJWT` 好，且 `jwt.encode()` 在 `python-jose` 中不会验证 `SECRET_KEY` 的长度和强度。

**建议**：考虑迁移到 `PyJWT`，或确保 `SECRET_KEY` 长度 ≥ 32 字符（当前已有 `validate_security()` 检查）。

---

### P1 - 安全中风险

#### 8. CORS 配置依赖 `.env` 正确性

**文件**：`D:\AI_agent\app\config.py`  
**行号**：第113行  
**问题**：
```python
CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]
```
默认允许本地开发域名，若生产环境 `.env` 文件未正确配置 `CORS_ORIGINS`，仍会使用默认值。虽然 `validate_security()` 第141行会检查，但仅检查 `*"` 和空列表，若 `.env` 中设置了 `CORS_ORIGINS=["*"]` 会通过检查（字符串 `"*"` 在列表中）。

**修复建议**：修改检查逻辑：
```python
if not self.DEBUG and any(origin == "*" for origin in self.CORS_ORIGINS):
    raise RuntimeError("生产环境 CORS_ORIGINS 不能包含通配符 *")
```

---

## 三、依赖管理

### P1 - 依赖问题

#### 9. 双重依赖管理：`requirements.txt` + `pyproject.toml`

**问题**：项目同时存在 `requirements.txt` 和 `pyproject.toml`，两者内容可能漂移。

**建议**：统一到 `pyproject.toml`（使用 poetry 或 pip-tools），删除 `requirements.txt`，或明确两者的分工（如 `pyproject.toml` 用于开发，`requirements.txt` 用于生产）。

---

#### 10. `celery` 依赖可能未使用

**文件**：`D:\AI_agent\requirements.txt` 第16行  
**问题**：`celery>=5.3.6` 在 `requirements.txt` 中，但全局搜索未发现 `from celery import ...` 的导入。

**建议**：确认是否需要 Celery，若不需要则从 `requirements.txt` 中移除。

---

#### 11. 依赖版本下限无上限锁定

**问题**：所有依赖均使用 `>=` 下限（如 `fastapi>=0.104.0`），无上限锁定，可能因依赖升级引入破坏性变更。

**建议**：使用 `pyproject.toml` 的 `poetry.lock` 或 `pip-tools` 锁定依赖版本。

---

## 四、总结

| 严重程度 | 数量 | 需立即修复 |
|---------|------|-----------|
| P0 | 3 | 是 |
| P1 | 4 | 建议 |
| P2 | 1 | 可选 |

**优先修复顺序**：
1. `database.py:43` — `engine.dispose()` fire-and-forget
2. `database.py:47` — 丢失连接池配置
3. `services/auth.py:32,48` — `HTTPException` 泄漏
4. `main.py:138-177` — 静默吞异常
5. 移除未使用的 `celery` 依赖

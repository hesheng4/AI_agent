# 🔒 FastAPI 项目安全审计报告

**审计日期**: 2026-06-19  
**审计范围**: D:\AI_agent  
**项目类型**: FastAPI + Python 科研助手平台

---

## 📋 执行摘要

| 风险等级 | 数量 |
|---------|------|
| 🔴 High | 5    |
| 🟡 Medium | 8   |
| 🔵 Low  | 4    |

---

## 🔴 High Risk（高风险）

### H1. 硬编码 OpenAI API Key 泄露
- **文件**: `D:\AI_agent\.env` (第4行)
- **问题**: OpenAI API Key 以明文存储在 `.env` 文件中
- **风险**: API Key 泄露可导致恶意调用，产生高额费用
- **修复建议**:
  1. 立即轮换此 API Key
  2. 确认 `.gitignore` 包含 `.env`
  3. 使用环境变量注入，不要提交到代码仓库

### H2. 默认 SECRET_KEY 暴露
- **文件**: `D:\AI_agent\app\config.py` (第44行)
- **问题**: 代码中硬编码了默认 `SECRET_KEY`
- **代码**: `SECRET_KEY: str = "your-secret-key-change-in-production"`
- **风险**: 攻击者可使用此密钥伪造 JWT Token
- **修复建议**: 生产环境必须在 `.env` 中设置强随机密钥，使用 `secrets.token_hex(32)` 生成

### H3. CORS 配置过于宽松
- **文件**: `D:\AI_agent\app\main.py` (第172-178行)
- **问题**: `allow_credentials=True` 且 `allow_methods` 和 `allow_headers` 使用通配符 `*`
- **风险**: CSRF 攻击风险
- **修复建议**: 生产环境明确指定允许的 origins，限制 methods 和 headers

### H4. SQLite 查询字符串拼接（SQL 注入风险）
- **文件**: `D:\AI_agent\app\core\history_to_skill.py`
- **问题**: 使用字符串格式化拼接 SQL 查询：`cursor.execute("PRAGMA table_info({})".format(table))`
- **风险**: SQL 注入攻击
- **修复建议**: 使用参数化查询或 ORM

### H5. Docker 镜像以 root 用户运行风险
- **文件**: `D:\AI_agent\Dockerfile`
- **问题**: 使用 `python:3.11-slim` 基础镜像，默认以 root 运行
- **风险**: 容器逃逸后可获得宿主机 root 权限
- **修复建议**: 确保 `USER appuser` 切换在全部安装步骤之后执行

---

## 🟡 Medium Risk（中风险）

### M1. 依赖版本过于宽松
- **文件**: `requirements.txt`
- **问题**: 使用 `>=` 版本约束，可能引入存在漏洞的新版本
- **修复建议**: 使用 `pip freeze` 或 `poetry.lock` 锁定版本

### M2. JWT 无刷新机制
- **文件**: `app/core/security.py` (第34-42行)
- **问题**: Token 过期时间仅 30 分钟，无 Refresh Token 机制
- **修复建议**: 实现 Refresh Token 机制

### M3. 文件上传无大小限制
- **文件**: `app/api/v1/data.py` (upload 端点)
- **问题**: 未限制上传文件大小，存在 DoS 风险
- **修复建议**: 添加 `MAX_UPLOAD_SIZE` 配置

### M4. 密码策略过于简单
- **文件**: `app/api/v1/auth.py` (第27-28行)
- **问题**: 仅要求最小长度 8 字符，无复杂度要求
- **修复建议**: 要求包含大小写字母、数字、特殊字符

### M5. 敏感信息可能记入日志
- **文件**: `app/main.py` (第254-256行)
- **问题**: 请求日志可能记录 Authorization 头等敏感信息
- **修复建议**: 过滤敏感请求头后再记录日志

### M6. Redis 未启用认证
- **文件**: `docker-compose.yml` (第78-92行)
- **问题**: Redis 容器未设置密码
- **修复建议**: 设置 `REDIS_PASSWORD`

### M7. PostgreSQL 使用默认凭据
- **文件**: `docker-compose.yml` (第58-75行)
- **问题**: `POSTGRES_USER=postgres` / `POSTGRES_PASSWORD=postgres`
- **修复建议**: 使用强密码

### M8. 依赖已知漏洞
- `python-jose 3.3.0`: CVE-2024-33664，建议升级到 3.4.0+
- `bcrypt 4.0.x`: 多个漏洞，建议升级到 4.2.1+

---

## 🔵 Low Risk（低风险）

### L1. 调试模式信息泄露
- **文件**: `.env` (第1行) `DEBUG=true`
- **修复建议**: 生产环境设为 `false`

### L2. 缺少安全响应头
- **文件**: `app/main.py`
- **问题**: 未设置 HSTS、X-Content-Type-Options 等安全头
- **修复建议**: 添加安全头中间件

### L3. API 文档未保护
- **文件**: `app/main.py` (第167-168行)
- **问题**: 生产环境虽禁用了 `/docs`，但未设置认证
- **修复建议**: 生产环境完全禁用或添加认证

### L4. 缺少注册速率限制
- **文件**: `app/api/v1/auth.py`
- **修复建议**: 添加注册速率限制

---

## ✅ 修复优先级路线图

### 立即修复（24小时内）
1. 轮换泄露的 OpenAI API Key
2. 修改默认 `SECRET_KEY`
3. 确认 `.env` 在 `.gitignore` 中
4. 修复 `history_to_skill.py` 中的 SQL 拼接

### 短期修复（1周内）
1. 锁定依赖版本 (`pip freeze > requirements.txt`)
2. 强化密码策略
3. 添加文件上传大小限制
4. 配置 Redis/PostgreSQL 认证
5. 升级有漏洞的依赖

### 中期修复（1个月内）
1. 实现 Refresh Token 机制
2. 添加 MFA 支持
3. 设置安全响应头
4. 为 API 文档添加认证

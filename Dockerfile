# ========== 阶段1：构建前端 ==========
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# 安装依赖（利用层缓存）
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --only=production

# 复制前端源码并构建
COPY frontend/ ./
RUN npm run build

# ========== 阶段2：构建后端依赖 ==========
FROM python:3.11-slim AS builder

WORKDIR /app

# 安装系统构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY pyproject.toml poetry.lock* ./
RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev --no-interaction

# ========== 阶段3：生产镜像 ==========
FROM python:3.11-slim

WORKDIR /app

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 从后端 builder 复制依赖
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 从前端 builder 复制构建产物
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# 复制应用代码
COPY app/ ./app/

# 创建非root用户
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/logs /app/uploads && \
    chown -R appuser:appuser /app

USER appuser

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.v1 import router as api_router
from app.config import get_settings
from app.utils.exceptions import AppException, ValidationException
from app.utils.logger import get_logger

# 前端目录（Vite 构建输出到 dist/）
FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"

logger = get_logger("main")
settings = get_settings()


async def _run_alembic_upgrade() -> None:
    """在独立线程中执行 Alembic `upgrade head`

    command.upgrade 内部会调用 env.py 的 run_migrations_online()，后者用
    asyncio.run() 创建事件循环。若在 lifespan 的 async 上下文里直接同步调用，
    会触发"事件循环已运行"错误。用 asyncio.to_thread 把它放到独立线程，
    其内部的 asyncio.run 在线程自己的事件循环里执行，互不冲突。
    """
    import asyncio

    from alembic import command
    from alembic.config import Config

    alembic_ini_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    if not alembic_ini_path.exists():
        raise FileNotFoundError(f"未找到 alembic.ini: {alembic_ini_path}")

    def _sync_upgrade():
        cfg = Config(str(alembic_ini_path))
        cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
        command.upgrade(cfg, "head")

    await asyncio.to_thread(_sync_upgrade)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"启动 {settings.APP_NAME}")
    logger.info(f"调试模式: {settings.DEBUG}")

    # 昇腾 NPU 环境初始化（仅 ascend 模式）
    if settings.LLM_MODE == "ascend":
        try:
            from app.core.ascend import AscendNPUManager

            npu_info = AscendNPUManager.check_environment()
            if npu_info["npu_available"]:
                logger.info(
                    f"昇腾 NPU 就绪: {npu_info['device_count']} 卡, "
                    f"CANN {npu_info['cann_version']}, "
                    f"PyTorch {npu_info['torch_version']}"
                )
                # 设置可见设备
                if settings.ASCEND_RT_VISIBLE_DEVICES:
                    from app.core.ascend import AscendNPUManager

                    device_ids = [
                        int(d) for d in settings.ASCEND_RT_VISIBLE_DEVICES.split(",")
                    ]
                    AscendNPUManager.set_visible_devices(device_ids)
                    logger.info(f"NPU 可见设备: {device_ids}")
            else:
                logger.warning("LLM_MODE=ascend 但 NPU 不可用，将回退到远程模式")
        except Exception as e:
            logger.warning(f"昇腾 NPU 初始化失败: {e}，将回退到远程模式")

        logger.info(f"LLM模式: ascend, 模型: {settings.ASCEND_LLM_MODEL}")
        logger.info(f"vLLM-Ascend 地址: {settings.ASCEND_VLLM_BASE_URL}")
    else:
        logger.info(f"LLM模式: remote, 模型: {settings.OPENAI_MODEL}")

    if settings.EMBEDDING_MODE in ("ascend_api", "ascend_local"):
        logger.info(
            f"Embedding模式: {settings.EMBEDDING_MODE}, "
            f"模型: {settings.ASCEND_EMBEDDING_MODEL}"
        )
    else:
        logger.info(f"Embedding模式: remote, 模型: {settings.EMBEDDING_MODEL}")

    # 初始化 Redis（缓存/限流后端为 redis 时需要）
    if settings.CACHE_BACKEND == "redis" or settings.RATE_LIMIT_BACKEND == "redis":
        from app.core.redis_client import init_redis

        await init_redis(settings.REDIS_URL)
        logger.info(
            f"缓存后端: {settings.CACHE_BACKEND}, "
            f"限流后端: {settings.RATE_LIMIT_BACKEND}"
        )
    else:
        logger.info(
            f"缓存后端: {settings.CACHE_BACKEND}, "
            f"限流后端: {settings.RATE_LIMIT_BACKEND}"
        )

    # 数据库迁移（必须在 Milvus 等其他组件之前，确保元数据就绪）
    if settings.MIGRATION_ON_STARTUP:
        try:
            await _run_alembic_upgrade()
            logger.info("Alembic 迁移已执行至 head")
        except Exception:
            # 迁移失败必须启动失败：create_all 兜底会绕过迁移链，
            # 造成两套 schema 永久漂移（体检报告 P1-9）
            logger.error("Alembic 迁移失败，拒绝启动", exc_info=True)
            raise
    else:
        # 未启用迁移时用 create_all 保证开发可用
        from app.core.database import Base, engine

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("数据库表已通过 create_all 创建（未启用 Alembic 迁移）")

    # 初始化 Milvus 向量库连接（懒连接，DB 迁移完成后再连接，失败不阻塞启动）
    try:
        from app.core.vector_store import vector_store

        await vector_store.connect()
    except Exception as e:
        logger.warning(f"Milvus 连接初始化失败，向量检索功能不可用: {e}")

    yield
    # Shutdown
    # 关闭 Redis 连接池
    try:
        from app.core.redis_client import close_redis

        await close_redis()
    except Exception as e:
        logger.warning(f"关闭 Redis 连接池失败: {e}")
    # 关闭文献工具的 httpx 连接池
    try:
        from app.agents.literature.tools import close_http_client

        await close_http_client()
    except Exception as e:
        logger.warning(f"关闭文献工具 httpx 连接池失败: {e}")
    # 关闭昇腾客户端（LLM 或 Embedding 任一为 ascend 模式时关闭）
    if settings.LLM_MODE == "ascend" or settings.EMBEDDING_MODE in (
        "ascend_api",
        "ascend_local",
    ):
        try:
            from app.core.ascend import get_npu_embedding, get_vllm_client

            try:
                await get_vllm_client().close()
            except Exception as e:
                logger.warning(f"关闭 vLLM 客户端失败: {e}")
            try:
                npu_emb = get_npu_embedding()
                if npu_emb is not None:
                    await npu_emb.close()
            except Exception as e:
                logger.warning(f"关闭 NPU Embedding 失败: {e}")
        except Exception as e:
            logger.warning(f"关闭昇腾客户端失败: {e}")
    # 关闭 OpenAI 兼容客户端连接池
    try:
        from app.utils.embedding import close_embedding_client
        from app.utils.llm import close_user_llm_clients

        await close_user_llm_clients()
        await close_embedding_client()
    except Exception as e:
        logger.warning(f"关闭 OpenAI 客户端失败: {e}")
    # 关闭 Milvus 连接
    try:
        from app.core.vector_store import vector_store

        await vector_store.close()
    except Exception as e:
        logger.warning(f"关闭 Milvus 连接失败: {e}")
    logger.info("关闭应用")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        lifespan=lifespan,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )

    # CORS
    # allow_credentials=True 时浏览器拒绝通配符 "*"，必须显式列出 methods/headers
    # DEBUG 下补充本地开发常用 origin，避免凭据跨域被浏览器屏蔽
    origins = list(settings.CORS_ORIGINS)
    if settings.DEBUG:
        for dev_origin in (
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
        ):
            if dev_origin not in origins:
                origins.append(dev_origin)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    )

    # 全局异常处理
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        logger.warning(f"应用异常: {exc.code} - {exc.message}")
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(ValidationException)
    async def validation_exception_handler(request: Request, exc: ValidationException):
        logger.warning(f"验证异常: {exc.message}")
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "VALIDATION_ERROR", "message": exc.message}},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        # 兼容未继承 AppException 但携带 status_code/message 属性的业务异常
        # （如 LibraryError 及其子类），按其声明的状态码返回
        if (
            hasattr(exc, "status_code")
            and hasattr(exc, "message")
            and isinstance(exc.status_code, int)
        ):
            logger.warning(f"业务异常: {exc.__class__.__name__} - {exc.message}")
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": {
                        "code": exc.__class__.__name__.upper(),
                        "message": exc.message,
                    }
                },
            )
        logger.error(f"未处理异常: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": (
                        "服务器内部错误" if not settings.DEBUG else str(exc)[:500]
                    ),
                }
            },
        )

    # 请求体大小限制中间件（S2）：超限直接 413，避免内存被恶意大 payload 耗尽
    # 必须早于日志中间件，让拒绝在缓冲 body 之前发生
    max_body = settings.MAX_REQUEST_BODY_BYTES

    @app.middleware("http")
    async def limit_request_body(request: Request, call_next):
        cl = request.headers.get("Content-Length")
        if cl is not None:
            try:
                if int(cl) > max_body:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": f"请求体过大（上限 {max_body} 字节）。"
                            "请缩减输入内容或拆分请求。"
                        },
                    )
            except ValueError:
                pass  # 非法 Content-Length 交由下游处理
        return await call_next(request)

    # 请求日志中间件
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        # 请求ID：优先复用客户端传入，否则生成
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        # 透传到下游（日志/LLM/外部调用可关联）
        request.state.request_id = request_id
        start = time.perf_counter()
        method = request.method
        path = request.url.path

        # O5: 用 trace_context 包裹整个请求，日志自动带 trace_id
        from app.core.tracing import trace_context

        try:
            with trace_context(request_id):
                response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                f"{request_id} {method} {path} 500 {duration_ms:.0f}ms 未处理异常"
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(f"{method} {path} {response.status_code} {duration_ms:.0f}ms")
        response.headers["X-Request-ID"] = request_id
        return response

    # Routes
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # 静态文件
    if FRONTEND_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

        # 前端 SPA 入口 — 所有非 /api 路径都返回 index.html，由前端路由处理
        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str, request: Request):
            # 排除 API 路径（已被上面的 router 处理，这里兜底）
            api_prefix = settings.API_V1_PREFIX.lstrip("/")
            if full_path.startswith(api_prefix + "/") or full_path == api_prefix:
                raise HTTPException(status_code=404, detail="Not Found")
            # 排除文档路径
            if (
                full_path.startswith("docs")
                or full_path.startswith("openapi")
                or full_path.startswith("redoc")
            ):
                raise HTTPException(status_code=404, detail="Not Found")
            # 尝试返回静态文件（如 favicon）
            # 必须先 resolve 并确认仍在 FRONTEND_DIR 内，否则 ../%2F.. 类
            # 编码路径可穿越到任意可读文件（如 .env）
            file_path = (FRONTEND_DIR / full_path).resolve()
            if (
                full_path
                and file_path.is_file()
                and file_path.is_relative_to(FRONTEND_DIR.resolve())
            ):
                return FileResponse(str(file_path))
            # 否则返回 SPA 入口
            return FileResponse(str(FRONTEND_DIR / "index.html"))
    else:
        logger.warning(f"前端 dist 目录不存在，跳过 SPA 静态文件挂载: {FRONTEND_DIR}")

    return app


app = create_app()


@app.get("/health")
async def health_check():
    """健康检查 - 包含数据库、Milvus、Redis、昇腾 NPU 状态"""
    health = {
        "status": "ok",
        "app": settings.APP_NAME,
        "llm_mode": settings.LLM_MODE,
        "embedding_mode": settings.EMBEDDING_MODE,
    }

    # 数据库连通性检查
    try:
        from app.core.database import get_async_engine

        engine = get_async_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        health["db_healthy"] = True
    except Exception as e:
        health["db_healthy"] = False
        health["db_error"] = "connection failed"
        logger.debug(f"DB health check failed: {e}")

    # Redis 连通性检查
    try:
        from app.core.redis_client import get_redis_client

        redis_client = await get_redis_client()
        await redis_client.ping()
        health["redis_healthy"] = True
    except Exception as e:
        health["redis_healthy"] = False
        health["redis_error"] = "connection failed"
        logger.debug(f"Redis health check failed: {e}")

    # Milvus 连通性检查
    try:
        from app.core.vector_store import get_vector_store

        vs = get_vector_store()
        await vs.list_collections()  # 轻量操作，验证连接
        health["milvus_healthy"] = True
    except Exception as e:
        health["milvus_healthy"] = False
        health["milvus_error"] = "connection failed"
        logger.debug(f"Milvus health check failed: {e}")

    # 昇腾 NPU 状态（仅在 ascend 模式下检查）
    if settings.LLM_MODE == "ascend" or settings.EMBEDDING_MODE in (
        "ascend_api",
        "ascend_local",
    ):
        try:
            from app.core.ascend import AscendNPUManager, get_vllm_client

            npu_info = AscendNPUManager.check_environment()
            health["npu_available"] = npu_info["npu_available"]
            health["npu_device_count"] = npu_info["device_count"]
            health["cann_version"] = npu_info.get("cann_version")

            # vLLM-Ascend 连通性
            if settings.LLM_MODE == "ascend":
                client = get_vllm_client()
                health["vllm_healthy"] = await client.check_health()
        except Exception as e:
            health["ascend_error"] = "health check failed"
            logger.debug(f"Ascend health check failed: {e}")

    # 总体状态：任意关键服务异常则 status=degraded
    if not health.get("db_healthy", True) or not health.get("redis_healthy", True):
        health["status"] = "degraded"

    return health

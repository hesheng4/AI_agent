"""平台域路由聚合 — 认证/计费/Agent生成/工作流/WebSocket"""

from fastapi import APIRouter

from app.api.v1.agents import router as agents_router
from app.api.v1.auth import router as auth_router
from app.api.v1.billing import router as billing_router
from app.api.v1.workflows import router as workflows_router
from app.api.v1.ws import router as ws_router

router = APIRouter()
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(billing_router, prefix="/billing", tags=["billing"])
router.include_router(agents_router, prefix="/agents", tags=["agents"])
router.include_router(workflows_router, prefix="/workflows", tags=["workflows"])
router.include_router(ws_router, prefix="/ws", tags=["websocket"])

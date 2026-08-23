"""文献库域路由聚合 — 文献/分类/标签/笔记/统计"""

from fastapi import APIRouter

from app.api.v1.library import router as library_router

router = APIRouter()
router.include_router(library_router, prefix="/library", tags=["library"])

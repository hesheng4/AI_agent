"""API v1 路由 — 按领域聚合（O7）

4 个域:
- research:   科研工作台（19 个路由）
- library:    文献库（1 个路由，含 6 子端点）
- platform:   平台基础设施（5 个路由）
- ascend:     昇腾工作台（9 个路由）
"""

from fastapi import APIRouter

from app.api.v1.ascend_domain import router as ascend_router
from app.api.v1.library_domain import router as library_router
from app.api.v1.platform import router as platform_router
from app.api.v1.research import router as research_router

router = APIRouter()
router.include_router(research_router)
router.include_router(library_router)
router.include_router(platform_router)
router.include_router(ascend_router)

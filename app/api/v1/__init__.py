"""API v1 路由 — 按领域聚合（O7）

4 个域:
- research:   科研工作台（21 个路由）
- library:    文献库（1 个路由，含 6 子端点）
- platform:   平台基础设施（5 个路由）
- ascend:     昇腾工作台（9 个路由）
"""

from fastapi import APIRouter, Depends

from app.api.deps import enforce_api_rate_limit
from app.api.v1.ascend_domain import router as ascend_router
from app.api.v1.library_domain import router as library_router
from app.api.v1.platform import router as platform_router
from app.api.v1.research import router as research_router

router = APIRouter()
# 科研域 = LLM 生成类端点（21 个路由），统一挂按用户套餐限流
router.include_router(
    research_router, dependencies=[Depends(enforce_api_rate_limit)]
)
router.include_router(library_router)
router.include_router(platform_router)
router.include_router(ascend_router)

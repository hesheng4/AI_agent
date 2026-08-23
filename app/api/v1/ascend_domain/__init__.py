"""昇腾域路由聚合 — NPU环境/适配/对齐/采集/调优/工具链/验证/调试/历史转技能"""

from fastapi import APIRouter

from app.api.v1.adaptation import router as adaptation_router
from app.api.v1.alignment import router as alignment_router
from app.api.v1.ascend import router as ascend_router
from app.api.v1.debugging import router as debugging_router
from app.api.v1.history_to_skill import router as history_to_skill_router
from app.api.v1.perf_tuning import router as perf_tuning_router
from app.api.v1.profiling import router as profiling_router
from app.api.v1.toolchain import router as toolchain_router
from app.api.v1.validator import router as validator_router

router = APIRouter()
router.include_router(ascend_router, prefix="/ascend", tags=["ascend"])
router.include_router(adaptation_router, prefix="/adaptation", tags=["adaptation"])
router.include_router(alignment_router, prefix="/alignment", tags=["alignment"])
router.include_router(profiling_router, prefix="/profiling", tags=["profiling"])
router.include_router(perf_tuning_router, prefix="/perf-tuning", tags=["perf-tuning"])
router.include_router(toolchain_router, prefix="/toolchain", tags=["toolchain"])
router.include_router(validator_router, prefix="/validator", tags=["validator"])
router.include_router(
    history_to_skill_router, prefix="/history-to-skill", tags=["history-to-skill"]
)
router.include_router(debugging_router, prefix="/debugging", tags=["debugging"])

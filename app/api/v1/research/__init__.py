"""科研域路由聚合 — 文献/写作/审稿/实验/转化等"""

from fastapi import APIRouter

from app.api.v1.citation import router as citation_router
from app.api.v1.coordinator import router as coordinator_router
from app.api.v1.cover import router as cover_router
from app.api.v1.data import router as data_router
from app.api.v1.data_availability import router as data_availability_router
from app.api.v1.experiment import router as experiment_router
from app.api.v1.export import router as export_router
from app.api.v1.figure import router as figure_router
from app.api.v1.literature import router as literature_router
from app.api.v1.methods import router as methods_router
from app.api.v1.paper2ppt import router as paper2ppt_router
from app.api.v1.paper_to_patent import router as paper_to_patent_router
from app.api.v1.polishing import router as polishing_router
from app.api.v1.reader import router as reader_router
from app.api.v1.response_api import router as response_router
from app.api.v1.review_loop import router as review_loop_router
from app.api.v1.reviewer import router as reviewer_router
from app.api.v1.stats import router as stats_router
from app.api.v1.submission_package import router as submission_package_router
from app.api.v1.writing import router as writing_router

router = APIRouter()
router.include_router(literature_router, prefix="/literature", tags=["literature"])
router.include_router(citation_router, prefix="/citation", tags=["citation"])
router.include_router(reader_router, prefix="/reader", tags=["reader"])
router.include_router(writing_router, prefix="/writing", tags=["writing"])
router.include_router(polishing_router, prefix="/polishing", tags=["polishing"])
router.include_router(stats_router, prefix="/stats", tags=["stats"])
router.include_router(methods_router, prefix="/methods", tags=["methods"])
router.include_router(figure_router, prefix="/figure", tags=["figure"])
router.include_router(data_router, prefix="/data", tags=["data"])
router.include_router(reviewer_router, prefix="/reviewer", tags=["reviewer"])
router.include_router(response_router, prefix="/response", tags=["response"])
router.include_router(review_loop_router, prefix="/review-loop", tags=["review-loop"])
router.include_router(cover_router, prefix="/cover", tags=["cover"])
router.include_router(
    submission_package_router, prefix="/submission-package", tags=["submission-package"]
)
router.include_router(paper2ppt_router, prefix="/paper2ppt", tags=["paper2ppt"])
router.include_router(
    paper_to_patent_router, prefix="/paper-to-patent", tags=["paper-to-patent"]
)
router.include_router(experiment_router, prefix="/experiment", tags=["experiment"])
router.include_router(
    data_availability_router, prefix="/data-availability", tags=["data-availability"]
)
router.include_router(export_router, prefix="/export", tags=["export"])
router.include_router(coordinator_router, prefix="/coordinator", tags=["coordinator"])

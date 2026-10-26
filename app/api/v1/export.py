"""数据导出API"""

from typing import Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.models.user import User
from app.utils.export import DataExporter
from app.utils.logger import get_logger

logger = get_logger("api.export")
router = APIRouter()


class ExportRequest(BaseModel):
    data: list[dict[str, Any]] = Field(..., description="数据")
    filename: str = Field(default="export", description="文件名")


class PapersExportRequest(BaseModel):
    papers: list[dict[str, Any]] = Field(..., description="文献列表")
    filename: str = Field(default="papers", description="文件名")


@router.post("/csv")
async def export_csv(
    request: ExportRequest, current_user: User = Depends(get_current_user)
) -> Response:
    """导出CSV"""
    logger.info(f"用户 {current_user.id} 导出CSV")

    csv_data = DataExporter.to_csv(request.data)

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{request.filename}.csv"'
        },
    )


@router.post("/json")
async def export_json(
    request: ExportRequest, current_user: User = Depends(get_current_user)
) -> Response:
    """导出JSON"""
    logger.info(f"用户 {current_user.id} 导出JSON")

    json_data = DataExporter.to_json(request.data)

    return Response(
        content=json_data,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{request.filename}.json"'
        },
    )


@router.post("/bibtex")
async def export_bibtex(
    request: PapersExportRequest, current_user: User = Depends(get_current_user)
) -> Response:
    """导出BibTeX"""
    logger.info(f"用户 {current_user.id} 导出BibTeX")

    bibtex_data = DataExporter.papers_to_bibtex(request.papers)

    return Response(
        content=bibtex_data.encode("utf-8"),
        media_type="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="{request.filename}.bib"'
        },
    )


@router.post("/ris")
async def export_ris(
    request: PapersExportRequest, current_user: User = Depends(get_current_user)
) -> Response:
    """导出RIS"""
    logger.info(f"用户 {current_user.id} 导出RIS")

    ris_data = DataExporter.papers_to_ris(request.papers)

    return Response(
        content=ris_data.encode("utf-8"),
        media_type="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="{request.filename}.ris"'
        },
    )


@router.post("/markdown")
async def export_markdown(
    request: ExportRequest, current_user: User = Depends(get_current_user)
) -> Response:
    """导出Markdown表格"""
    logger.info(f"用户 {current_user.id} 导出Markdown")

    md_data = DataExporter.to_markdown_table(request.data)

    return Response(
        content=md_data.encode("utf-8"),
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="{request.filename}.md"'
        },
    )

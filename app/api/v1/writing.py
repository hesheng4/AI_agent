from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.agents.writing import get_writing_agent
from app.agents.writing.tools import WritingTools
from app.api.deps import get_current_user
from app.config import get_settings
from app.models.user import User
from app.utils.logger import get_logger

logger = get_logger("api.writing")
router = APIRouter()
settings = get_settings()


def _user_llm_config(user: User) -> dict[str, Any]:
    """从用户模型提取 LLM 配置，优先用户级 > 系统级"""
    api_key = user.api_key or settings.OPENAI_API_KEY
    base_url = user.api_base_url or settings.OPENAI_BASE_URL
    model = user.api_model or settings.OPENAI_MODEL
    return {
        "_user_api_key": api_key,
        "_user_api_base_url": base_url,
        "_user_api_model": model,
    }


def _require_api_key(api_key: str | None) -> None:
    """当系统级和用户级 API key 都为空时，返回 400 提示配置"""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "LLM API Key 未配置。请在个人设置中配置 API Key，"
                "或设置环境变量 OPENAI_API_KEY"
            ),
        )


# ─────────────────────────────────────────────
# 请求模型
# ─────────────────────────────────────────────


class OutlineRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=500, description="研究主题")
    paper_type: str = Field(
        default="research",
        description="论文类型: research/methods/hypothesis/algorithmic/review/auto",
    )
    journal: str = Field(default="standard", description="期刊格式: standard/nat-comms")


class GenerateRequest(BaseModel):
    outline: dict[str, Any] = Field(..., description="论文大纲")
    section: str = Field(default="introduction", description="章节名称")
    paper_type: str = Field(default="research", description="论文类型")
    terminology_ledger: dict[str, Any] | None = Field(
        default=None, description="术语账本"
    )


class PolishRequest(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        max_length=settings.MAX_CONTENT_LENGTH,
        description="需要润色的文本",
    )
    paper_type: str = Field(default="research", description="论文类型")


class CheckRequest(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        max_length=settings.MAX_CONTENT_LENGTH,
        description="需要检查的文本",
    )


class StructureRequest(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        max_length=settings.MAX_CONTENT_LENGTH,
        description="论文内容",
    )
    paper_type: str | None = Field(default=None, description="论文类型(留空自动检测)")


class TerminologyRequest(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        max_length=settings.MAX_CONTENT_LENGTH,
        description="论文内容",
    )


class EvidenceRequest(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        max_length=settings.MAX_CONTENT_LENGTH,
        description="论文内容",
    )


class DetectTypeRequest(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        max_length=settings.MAX_CONTENT_LENGTH,
        description="论文内容或主题描述",
    )


# ─────────────────────────────────────────────
# 响应模型
# ─────────────────────────────────────────────


class OutlineResponse(BaseModel):
    status: str
    template: dict[str, Any]
    optimized_outline: str
    paper_type: str
    core_chain: str
    drafting_order: list[str]


class GenerateResponse(BaseModel):
    status: str
    section: str
    content: str
    paper_type: str


class PolishResponse(BaseModel):
    status: str
    original: str
    polished: str
    terminology_ledger: dict[str, Any] | None = None


class CheckResponse(BaseModel):
    status: str
    issues: list[dict[str, str]]
    total_issues: int


class WordCountResponse(BaseModel):
    status: str
    stats: dict[str, Any]


class StructureResponse(BaseModel):
    status: str
    tool_analysis: dict[str, Any]
    llm_analysis: str
    paper_type: str
    overall_score: int


class TerminologyResponse(BaseModel):
    status: str
    ledger: dict[str, Any]
    total_terms: int
    rules: list[str]


class EvidenceResponse(BaseModel):
    status: str
    naked_claims: list[dict[str, str]]
    llm_analysis: str
    total_naked_claims: int


class DetectTypeResponse(BaseModel):
    status: str
    detected_type: str
    scores: dict[str, int]
    confidence: float
    type_info: dict[str, Any]


# ─────────────────────────────────────────────
# API 路由
# ─────────────────────────────────────────────


@router.post("/outline", response_model=OutlineResponse)
async def create_outline(
    request: OutlineRequest, current_user: User = Depends(get_current_user)
) -> OutlineResponse:
    """生成论文大纲（Nature-skills 论文类型分类学驱动）"""
    llm_config = _user_llm_config(current_user)
    _require_api_key(llm_config["_user_api_key"])
    logger.info(
        f"用户 {current_user.id} 生成大纲: {request.topic}, 类型={request.paper_type}"
    )

    agent = get_writing_agent()
    result = await agent.process(
        {
            "task": "outline",
            "topic": request.topic,
            "paper_type": request.paper_type,
            "journal": request.journal,
            **llm_config,
        }
    )

    return OutlineResponse(
        status="success",
        template=result.get("template", {}),
        optimized_outline=result.get("optimized_outline", ""),
        paper_type=result.get("paper_type", "research"),
        core_chain=result.get("core_chain", ""),
        drafting_order=result.get("drafting_order", []),
    )


@router.post("/generate", response_model=GenerateResponse)
async def generate_content(
    request: GenerateRequest, current_user: User = Depends(get_current_user)
) -> GenerateResponse:
    """生成章节内容（遵循论证链和术语账本）"""
    llm_config = _user_llm_config(current_user)
    _require_api_key(llm_config["_user_api_key"])
    logger.info(f"用户 {current_user.id} 生成内容: {request.section}")

    agent = get_writing_agent()
    result = await agent.process(
        {
            "task": "generate",
            "outline": request.outline,
            "section": request.section,
            "paper_type": request.paper_type,
            "terminology_ledger": request.terminology_ledger or {},
            **llm_config,
        }
    )

    return GenerateResponse(
        status="success",
        section=str(result.get("section") or ""),
        content=str(result.get("content") or ""),
        paper_type=str(result.get("paper_type") or "research"),
    )


@router.post("/polish", response_model=PolishResponse)
async def polish_text(
    request: PolishRequest, current_user: User = Depends(get_current_user)
) -> PolishResponse:
    """AI润色文本（服务读者工作流，不改变论证结构）"""
    llm_config = _user_llm_config(current_user)
    _require_api_key(llm_config["_user_api_key"])
    logger.info(f"用户 {current_user.id} 润色文本")

    agent = get_writing_agent()
    result = await agent.process(
        {
            "task": "polish",
            "content": request.content,
            "paper_type": request.paper_type,
            **llm_config,
        }
    )

    return PolishResponse(
        status="success",
        original=str(result.get("original") or ""),
        polished=str(result.get("polished") or ""),
        terminology_ledger=result.get("terminology_ledger"),
    )


@router.post("/check", response_model=CheckResponse)
async def check_grammar(
    request: CheckRequest, current_user: User = Depends(get_current_user)
) -> CheckResponse:
    """语法检查（含裸论断检测）"""
    logger.info(f"用户 {current_user.id} 检查语法")

    tools = WritingTools()
    issues = tools.check_grammar(request.content)

    return CheckResponse(status="success", issues=issues, total_issues=len(issues))


@router.post("/word-count", response_model=WordCountResponse)
async def count_words(
    request: CheckRequest, current_user: User = Depends(get_current_user)
) -> WordCountResponse:
    """字数统计"""
    logger.info(f"用户 {current_user.id} 统计字数")

    tools = WritingTools()
    stats = tools.count_words(request.content)

    return WordCountResponse(status="success", stats=stats)


@router.post("/structure", response_model=StructureResponse)
async def analyze_structure(
    request: StructureRequest, current_user: User = Depends(get_current_user)
) -> StructureResponse:
    """分析论文论证结构（Nature-skills 读者工作流驱动）"""
    llm_config = _user_llm_config(current_user)
    _require_api_key(llm_config["_user_api_key"])
    logger.info(f"用户 {current_user.id} 分析论证结构")

    agent = get_writing_agent()
    result = await agent.process(
        {
            "task": "structure",
            "content": request.content,
            "paper_type": request.paper_type,
            **llm_config,
        }
    )

    return StructureResponse(
        status="success",
        tool_analysis=result.get("tool_analysis", {}),
        llm_analysis=result.get("llm_analysis", ""),
        paper_type=result.get("paper_type", "research"),
        overall_score=result.get("overall_score", 0),
    )


@router.post("/terminology", response_model=TerminologyResponse)
async def build_terminology(
    request: TerminologyRequest, current_user: User = Depends(get_current_user)
) -> TerminologyResponse:
    """构建术语账本（Nature-skills 术语一致性规则）"""
    llm_config = _user_llm_config(current_user)
    _require_api_key(llm_config["_user_api_key"])
    logger.info(f"用户 {current_user.id} 构建术语账本")

    agent = get_writing_agent()
    result = await agent.process(
        {
            "task": "terminology",
            "content": request.content,
            **llm_config,
        }
    )

    return TerminologyResponse(
        status="success",
        ledger=result.get("ledger", {}),
        total_terms=result.get("total_terms", 0),
        rules=result.get("rules", []),
    )


@router.post("/evidence", response_model=EvidenceResponse)
async def analyze_evidence(
    request: EvidenceRequest, current_user: User = Depends(get_current_user)
) -> EvidenceResponse:
    """分析证据链完整性（裸论断检测）"""
    llm_config = _user_llm_config(current_user)
    _require_api_key(llm_config["_user_api_key"])
    logger.info(f"用户 {current_user.id} 分析证据链")

    agent = get_writing_agent()
    result = await agent.process(
        {
            "task": "evidence",
            "content": request.content,
            **llm_config,
        }
    )

    return EvidenceResponse(
        status="success",
        naked_claims=result.get("naked_claims", []),
        llm_analysis=result.get("llm_analysis", ""),
        total_naked_claims=result.get("total_naked_claims", 0),
    )


@router.post("/detect-type", response_model=DetectTypeResponse)
async def detect_paper_type(
    request: DetectTypeRequest, current_user: User = Depends(get_current_user)
) -> DetectTypeResponse:
    """检测论文类型"""
    logger.info(f"用户 {current_user.id} 检测论文类型")

    tools = WritingTools()
    result = tools.detect_paper_type(request.content)

    return DetectTypeResponse(
        status="success",
        detected_type=result["detected_type"],
        scores=result["scores"],
        confidence=result["confidence"],
        type_info=result["type_info"],
    )


# ─────────────────────────────────────────────
# LaTeX 导出
# ─────────────────────────────────────────────


class LaTeXExportRequest(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        max_length=settings.MAX_CONTENT_LENGTH,
        description="论文内容",
    )
    title: str = Field(default="Untitled", description="论文标题")
    authors: str = Field(default="", description="作者列表，逗号分隔")
    abstract: str = Field(default="", description="摘要")
    keywords: str = Field(default="", description="关键词，逗号分隔")
    outline: dict[str, Any] | None = Field(default=None, description="论文大纲（可选）")
    paper_type: str = Field(default="research", description="论文类型")
    journal: str = Field(default="standard", description="期刊格式: standard/nat-comms")


@router.post("/export-latex")
async def export_latex(
    request: LaTeXExportRequest, current_user: User = Depends(get_current_user)
) -> Response:
    """导出论文为 LaTeX 源码"""
    logger.info(f"用户 {current_user.id} 导出 LaTeX, 标题={request.title}")

    from app.utils.latex_export import LaTeXExporter

    latex_code = LaTeXExporter.export_paper(
        content=request.content,
        title=request.title,
        authors=request.authors,
        abstract=request.abstract,
        keywords=[k.strip() for k in request.keywords.split(",") if k.strip()],
        outline=request.outline,
        paper_type=request.paper_type,
        journal=request.journal,
    )

    filename = request.title.replace(" ", "_").replace("/", "_") or "paper"

    return Response(
        content=latex_code.encode("utf-8"),
        media_type="application/x-latex",
        headers={"Content-Disposition": f'attachment; filename="{filename}.tex"'},
    )

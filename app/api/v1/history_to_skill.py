"""昇腾历史转 Skill API 端点

遵循 ascend-history-to-skill skill 规范：
1. 明确目标模型和范围
2. 搜索历史记录
3. 只保留高价值证据
4. 整理成 skill 素材
5. 生成模型 skill
6. 生成后验证
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.history_to_skill import (
    EvidenceLevel,
    HistorySource,
    discover_history_roots,
    extract_skill_material,
    filter_high_value_hits,
    history_to_skill,
    normalize_model_name,
    search_history,
    validate_skill,
)

router = APIRouter(dependencies=[Depends(get_current_user)])


# ========== Request Models ==========


class SearchHistoryRequest(BaseModel):
    """搜索历史记录请求"""

    model_name: str = Field(description="目标模型名，如 esm2、DiffSBDD、Boltz2")
    stages: list[str] | None = Field(
        default=None, description="阶段过滤: adapt, optimize"
    )
    keywords: list[str] | None = Field(default=None, description="额外搜索关键词")
    sources: list[str] | None = Field(
        default=None, description="限制来源: codex, claude-code, opencode, cursor"
    )
    extra_roots: list[str] | None = Field(default=None, description="额外搜索路径")
    exclude_terms: list[str] | None = Field(default=None, description="排除关键词")
    max_hits: int = Field(default=100, ge=1, le=500, description="最大命中数")
    filter_low_value: bool = Field(default=True, description="过滤低价值记录")


class GenerateSkillRequest(BaseModel):
    """生成 Skill 请求"""

    model_name: str = Field(description="目标模型名")
    stages: list[str] | None = Field(default=None, description="阶段: adapt, optimize")
    keywords: list[str] | None = Field(default=None, description="额外搜索关键词")
    sources: list[str] | None = Field(
        default=None, description="限制来源: codex, claude-code, opencode, cursor"
    )
    extra_roots: list[str] | None = Field(default=None, description="额外搜索路径")
    exclude_terms: list[str] | None = Field(default=None, description="排除关键词")
    output_dir: str | None = Field(
        default=None, description="输出目录，默认 ~/.codex/skills/<model>/"
    )
    max_hits: int = Field(default=100, ge=1, le=500)


class ValidateSkillRequest(BaseModel):
    """验证 Skill 请求"""

    skill_dir: str = Field(description="Skill 目录路径")


# ========== API Endpoints ==========


@router.get("/status")
async def history_to_skill_status() -> dict[str, Any]:
    """模块状态"""
    return {
        "module": "ascend_history_to_skill",
        "status": "active",
        "description": "从历史记录提取昇腾适配经验，生成可复用 Skill",
        "workflow": [
            "1. 明确目标: GET /history-to-skill/variants/{model_name}",
            "2. 发现根目录: GET /history-to-skill/roots",
            "3. 搜索历史: POST /history-to-skill/search",
            "4. 生成 Skill: POST /history-to-skill/generate",
            "5. 一键执行: POST /history-to-skill/run",
            "6. 验证 Skill: POST /history-to-skill/validate",
        ],
        "supported_sources": ["codex", "claude-code", "opencode", "cursor"],
    }


@router.get("/variants/{model_name}")
async def get_model_variants(model_name: str) -> dict[str, Any]:
    """Step 1: 获取模型名变体

    用于扩大搜索范围，覆盖连字符/下划线/大小写变体
    """
    variants = normalize_model_name(model_name)
    return {
        "model_name": model_name,
        "variants": variants,
        "search_tip": "所有变体将用于搜索历史记录",
    }


@router.get("/roots")
async def discover_roots(
    sources: str | None = None,
    extra_root: list[str] | None = None,
) -> dict[str, Any]:
    """Step 2: 发现可用历史记录根目录

    检测本地 Codex / Claude Code / OpenCode / Cursor 历史存储路径
    """
    src_list = None
    if sources:
        src_list = [HistorySource(s.strip()) for s in sources.split(",")]

    roots = discover_history_roots(src_list, extra_root)

    result = {}
    for src, paths in roots.items():
        result[src.value] = paths

    return {
        "discovered_roots": result,
        "total_paths": sum(len(v) for v in roots.values()),
        "tip": "如果没有找到路径，可使用 extra_root 参数手动指定",
    }


@router.post("/search")
async def search_history_endpoint(req: SearchHistoryRequest) -> dict[str, Any]:
    """Step 2-3: 搜索历史记录并过滤

    搜索后自动过滤低价值证据，保留已验证命令、代码修改、
    benchmark 结果、报错修复
    """
    sources = None
    if req.sources:
        try:
            sources = [HistorySource(s) for s in req.sources]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"无效来源: {str(e)}")

    try:
        hits = search_history(
            model_name=req.model_name,
            stages=req.stages,
            keywords=req.keywords,
            sources=sources,
            extra_roots=req.extra_roots,
            exclude_terms=req.exclude_terms,
            max_hits=req.max_hits,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if req.filter_low_value:
        hits = filter_high_value_hits(hits)

    # 同时提取素材概要
    material = extract_skill_material(req.model_name, hits)

    return {
        "model_name": req.model_name,
        "total_hits": len(hits),
        "verified_hits": len(
            [h for h in hits if h.evidence_level == EvidenceLevel.VERIFIED]
        ),
        "hits": [h.to_dict() for h in hits[:50]],
        "material_summary": {
            "has_env_info": bool(material.python_version or material.torch_version),
            "has_adapt_steps": bool(material.cuda_replacements or material.adapt_steps),
            "has_optimize_steps": bool(
                material.runtime_env_vars or material.optimize_steps
            ),
            "has_verify_commands": bool(material.verify_commands),
            "has_common_issues": bool(material.common_issues),
        },
    }


@router.post("/generate")
async def generate_skill_endpoint(req: GenerateSkillRequest) -> dict[str, Any]:
    """Step 5: 从历史记录生成模型 Skill

    完整流程：搜索 → 过滤 → 整理 → 生成
    """
    sources = None
    if req.sources:
        try:
            sources = [HistorySource(s) for s in req.sources]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"无效来源: {str(e)}")

    try:
        result = history_to_skill(
            model_name=req.model_name,
            stages=req.stages,
            keywords=req.keywords,
            sources=sources,
            extra_roots=req.extra_roots,
            exclude_terms=req.exclude_terms,
            output_dir=req.output_dir,
            max_hits=req.max_hits,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result.to_dict()


@router.post("/run")
async def run_full_pipeline(req: GenerateSkillRequest) -> dict[str, Any]:
    """一键执行完整流程 (Step 1-6)

    明确目标 → 搜索 → 过滤 → 整理 → 生成 → 验证
    """
    sources = None
    if req.sources:
        try:
            sources = [HistorySource(s) for s in req.sources]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"无效来源: {str(e)}")

    try:
        result = history_to_skill(
            model_name=req.model_name,
            stages=req.stages,
            keywords=req.keywords,
            sources=sources,
            extra_roots=req.extra_roots,
            exclude_terms=req.exclude_terms,
            output_dir=req.output_dir,
            max_hits=req.max_hits,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result.to_dict()


@router.post("/validate")
async def validate_skill_endpoint(req: ValidateSkillRequest) -> dict[str, Any]:
    """Step 6: 验证已生成的 Skill

    结构验证 + 内容验证
    """
    import os

    if not os.path.exists(req.skill_dir):
        raise HTTPException(
            status_code=404, detail=f"Skill 目录不存在: {req.skill_dir}"
        )

    passed, errors = validate_skill(req.skill_dir)

    return {
        "skill_dir": req.skill_dir,
        "validation_passed": passed,
        "errors": errors,
        "summary": (
            "验证通过" if passed else "验证失败: {}".format("; ".join(errors[:3]))
        ),
    }


@router.get("/quick-reference")
async def quick_reference() -> dict[str, Any]:
    """快速参考"""
    return {
        "workflow": [
            "1. 明确目标: GET /history-to-skill/variants/{model_name}",
            "2. 发现根目录: GET /history-to-skill/roots",
            "3. 搜索历史: POST /history-to-skill/search",
            "4. 一键生成: POST /history-to-skill/run",
            "5. 验证 Skill: POST /history-to-skill/validate",
        ],
        "cli_usage": (
            "python scripts/search_history.py --model esm2 --stage adapt,optimize\n"
            "python scripts/search_history.py --model esm2 --keyword torch_npu"
        ),
        "evidence_levels": {
            "verified": "已验证，有运行输出",
            "likely": "有代码修改，无明确输出",
            "discussion": "仅讨论",
            "unverified": "未验证",
        },
        "filter_rules": {
            "优先保留": [
                "明确的环境创建与依赖安装命令",
                "已落地的代码修改点、脚本路径、关键参数",
                "真实跑通的验证命令和输出产物",
                "有数字的性能对比、精度对比、benchmark 结论",
                "真实报错及对应修复",
            ],
            "降权/丢弃": [
                "只有用户提问、没有执行结果的片段",
                "纯 brainstorming、没有落地命令的讨论",
                "与目标模型无关的记录",
                "被后续记录推翻的旧方案",
            ],
        },
    }

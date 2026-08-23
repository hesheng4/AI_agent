"""精度对齐 API - 触发对比、查看结果、生成报告"""

import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.config import get_settings
from app.utils.logger import get_logger

router = APIRouter(dependencies=[Depends(get_current_user)])
logger = get_logger("alignment_api")
settings = get_settings()


class AlignmentRequest(BaseModel):
    """精度对齐请求"""

    baseline_url: str = ""  # 基线服务 URL（GPU），空则使用远程 API
    npu_url: str = ""  # NPU 服务 URL，空则使用 ASCEND_VLLM_BASE_URL
    model: str = ""  # 模型名称，空则使用配置默认值
    baseline_source: str = "user_gpu_result"  # 基线来源
    temperature: float = 0.0
    max_tokens: int = 128
    compare_embedding: bool = True
    embedding_model: str = ""


class AlignmentStatus(BaseModel):
    """精度对齐状态"""

    running: bool = False
    last_result: dict | None = None
    error: str | None = None


# 全局状态
_alignment_status = AlignmentStatus()


@router.get("/status")
async def alignment_status():
    """获取当前精度对齐状态"""
    return _alignment_status.dict()


@router.post("/run")
async def run_alignment(request: AlignmentRequest, background_tasks: BackgroundTasks):
    """触发精度对齐（后台执行）"""
    if _alignment_status.running:
        raise HTTPException(status_code=409, detail="精度对齐正在运行中，请等待完成")

    _alignment_status.running = True
    _alignment_status.error = None

    background_tasks.add_task(_execute_alignment, request)

    return {"message": "精度对齐已启动", "baseline_source": request.baseline_source}


async def _execute_alignment(request: AlignmentRequest):
    """执行精度对齐（后台任务）"""
    try:
        import os
        from datetime import datetime

        # 确定 URL
        baseline_url = request.baseline_url or f"{settings.OPENAI_BASE_URL}"
        npu_url = request.npu_url or settings.ASCEND_VLLM_BASE_URL
        model = request.model or settings.ASCEND_LLM_MODEL
        embedding_model = request.embedding_model or settings.ASCEND_EMBEDDING_MODEL

        # 构建命令
        test_file = "tests/alignment/test_prompts.jsonl"
        emb_test_file = "tests/alignment/test_embeddings.txt"
        output_file = (
            f"reports/alignment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        # 使用 compare_inference 脚本的核心逻辑
        from scripts.compare_inference import (
            compare_embedding_inference,
            compare_llm_inference,
            generate_report,
        )

        # 加载测试 prompts
        test_prompts = []
        if os.path.exists(test_file):
            with open(test_file, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        import json as _json

                        test_prompts.append(_json.loads(line))
        else:
            test_prompts = [
                {
                    "label": "default",
                    "messages": [{"role": "user", "content": "Hello, this is a test."}],
                },
            ]

        # LLM 对比
        llm_result = await compare_llm_inference(
            baseline_url=baseline_url,
            npu_url=npu_url,
            model=model,
            test_prompts=test_prompts,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            baseline_source=request.baseline_source,
        )

        results = [llm_result]

        # Embedding 对比
        if request.compare_embedding:
            test_texts = []
            if os.path.exists(emb_test_file):
                with open(emb_test_file, encoding="utf-8") as f:
                    test_texts = [line.strip() for line in f if line.strip()]
            else:
                test_texts = ["测试文本"]

            emb_result = await compare_embedding_inference(
                baseline_url=baseline_url,
                npu_url=npu_url,
                model=embedding_model,
                test_texts=test_texts,
                baseline_source=request.baseline_source,
            )
            results.append(emb_result)

        # 生成报告
        generate_report(
            results=results,
            output_path=output_file,
            metadata={
                "model": model,
                "baseline_source": request.baseline_source,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
            },
        )

        _alignment_status.running = False
        _alignment_status.last_result = {
            "output_file": output_file,
            "results": results,
            "overall_passed": all(r.get("passed", False) for r in results),
        }

        logger.info(f"精度对齐完成: {output_file}")

    except Exception as e:
        _alignment_status.running = False
        _alignment_status.error = str(e)
        logger.error(f"精度对齐失败: {e}")


@router.get("/report")
async def get_latest_report():
    """获取最新的精度对齐报告"""
    import glob

    reports = sorted(glob.glob("reports/alignment_*.json"))
    if not reports:
        return {"message": "暂无报告，请先运行精度对齐"}

    latest = reports[-1]
    with open(latest, encoding="utf-8") as f:
        return json.load(f)


@router.get("/thresholds")
async def get_thresholds():
    """获取当前精度对齐阈值（预声明）"""
    from app.core.alignment import DEFAULT_THRESHOLDS

    return DEFAULT_THRESHOLDS.to_dict()


@router.get("/constraints")
async def get_default_constraints():
    """获取默认对比约束"""
    from app.core.alignment import BGE_LARGE_ZH_CONSTRAINTS, QWEN25_72B_CONSTRAINTS

    return {
        "llm": QWEN25_72B_CONSTRAINTS.to_dict(),
        "embedding": BGE_LARGE_ZH_CONSTRAINTS.to_dict(),
    }

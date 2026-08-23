"""昇腾 NPU 模型适配 API 端点

端点:
    GET  /adaptation/status              — 模块状态
    POST /adaptation/sessions            — 创建适配会话（Step 1）
    GET  /adaptation/sessions            — 列出所有会话
    GET  /adaptation/sessions/{id}       — 获取会话详情
    POST /adaptation/sessions/{id}/step2 — 分析模型
    POST /adaptation/sessions/{id}/step3 — 算子兼容性门控
    POST /adaptation/sessions/{id}/step4 — 框架侧代码分析
    POST /adaptation/sessions/{id}/step5 — 选择适配策略
    POST /adaptation/sessions/{id}/step6 — 实现最小代码改动
    POST /adaptation/sessions/{id}/step7-dummy  — Dummy 验证
    POST /adaptation/sessions/{id}/step7-real    — Real-weight 验证
    POST /adaptation/sessions/{id}/step8 — 验证推理和功能
    POST /adaptation/sessions/{id}/step9 — 生成产物
    POST /adaptation/sessions/{id}/step10 — 交接产物
    GET  /adaptation/quick-reference     — 快速参考
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.adaptation import (
    create_session,
    get_quick_reference,
    get_session,
    list_sessions,
    step1_collect_context,
    step2_analyze_model,
    step3_operator_gate,
    step4_framework_analysis,
    step5_choose_strategy,
    step6_implement,
    step7_validate_dummy,
    step7_validate_real,
    step8_validate_inference,
    step9_generate_artifacts,
    step10_handoff,
)
from app.core.profiling import _validate_path_safety

router = APIRouter(dependencies=[Depends(get_current_user)])


# ========== 请求模型 ==========


class CreateSessionRequest(BaseModel):
    """创建适配会话请求（Step 1）"""

    model_path: str = Field(description="模型权重路径（本地路径或 HuggingFace ID）")
    model_name: str = Field(description="模型名称标识")
    delivery_repo: str = Field(default="", description="交付仓库路径")
    features: list[str] = Field(
        default=["generate", "chat"],
        description="默认功能集",
    )


class Step1ContextRequest(BaseModel):
    """Step 1 上下文信息请求"""

    model_path: str | None = Field(default=None, description="模型路径（覆盖）")
    implementation_root: str | None = Field(default=None, description="实现根目录")
    delivery_repo: str | None = Field(default=None, description="交付仓库")
    features: list[str] | None = Field(default=None, description="功能集")
    vllm_path: str | None = Field(default=None, description="vLLM 安装路径")
    transformers_version: str | None = Field(
        default=None, description="transformers 版本"
    )


class Step3OperatorGateRequest(BaseModel):
    """Step 3 算子兼容性门控请求"""

    model_code: str = Field(
        default="",
        description="模型实现代码（Python 源码字符串）",
    )


class Step4FrameworkAnalysisRequest(BaseModel):
    """Step 4 框架侧代码分析请求"""

    vllm_path: str = Field(
        default="",
        description="vLLM 安装路径",
    )


class Step6ImplementRequest(BaseModel):
    """Step 6 实现最小代码改动请求"""

    implementation_details: dict[str, Any] | None = Field(
        default=None,
        description="实现细节（可选覆盖）",
    )


class Step7DummyRequest(BaseModel):
    """Step 7a Dummy 验证请求"""

    model_path: str | None = Field(default=None, description="模型路径（覆盖）")
    tensor_parallel_size: int = Field(default=1, ge=1, description="张量并行度")
    host: str = Field(default="0.0.0.0", description="服务监听地址")
    port: int = Field(default=8000, ge=1024, le=65535, description="服务端口")
    max_model_len: int = Field(default=4096, description="最大序列长度")


class Step7RealRequest(BaseModel):
    """Step 7b Real-weight 验证请求"""

    model_path: str | None = Field(default=None, description="模型路径（覆盖）")
    tensor_parallel_size: int = Field(default=1, ge=1, description="张量并行度")
    host: str = Field(default="0.0.0.0", description="服务监听地址")
    port: int = Field(default=8000, ge=1024, le=65535, description="服务端口")
    max_model_len: int = Field(default=8192, description="最大序列长度")
    gpu_memory_utilization: float = Field(
        default=0.90,
        ge=0.1,
        le=0.99,
        description="显存利用率",
    )


class Step8InferenceRequest(BaseModel):
    """Step 8 验证推理和功能请求"""

    host: str = Field(default="0.0.0.0", description="服务地址")
    port: int = Field(default=8000, ge=1024, le=65535, description="服务端口")


# ========== 端点 ==========


@router.get("/status")
async def get_adaptation_status():
    """查看模型适配模块状态"""
    sessions = list_sessions()
    return {
        "module": "ascend_adaptation",
        "status": "active",
        "description": "昇腾 NPU 模型适配（adapt-agent 10 步 playbook）",
        "playbook_steps": 10,
        "sessions_count": len(sessions),
        "workflow": [
            "1. 收集上下文: POST /adaptation/sessions",
            "2. 分析模型: POST /adaptation/sessions/{id}/step2",
            "3. 算子兼容性门控: POST /adaptation/sessions/{id}/step3",
            "4. 框架侧代码分析: POST /adaptation/sessions/{id}/step4",
            "5. 选择适配策略: POST /adaptation/sessions/{id}/step5",
            "6. 实现最小代码改动: POST /adaptation/sessions/{id}/step6",
            "7. 两阶段验证: POST /adaptation/sessions/{id}/step7-dummy | step7-real",
            "8. 验证推理和功能: POST /adaptation/sessions/{id}/step8",
            "9. 生成产物: POST /adaptation/sessions/{id}/step9",
            "10. 交接产物: POST /adaptation/sessions/{id}/step10",
        ],
    }


@router.post("/sessions")
async def create_adaptation_session(req: CreateSessionRequest):
    """创建适配会话（Step 1: 收集上下文）

    创建新的适配会话并初始化 10 步流程。
    """
    # 路径安全校验
    _validate_path_safety(req.model_path, "model_path")
    if req.delivery_repo:
        _validate_path_safety(req.delivery_repo, "delivery_repo")

    session = create_session(
        model_path=req.model_path,
        model_name=req.model_name,
        delivery_repo=req.delivery_repo,
        features=req.features,
    )
    return session.to_dict()


@router.get("/sessions")
async def list_adaptation_sessions():
    """列出所有适配会话"""
    return {
        "count": len(list_sessions()),
        "sessions": list_sessions(),
    }


@router.get("/sessions/{session_id}")
async def get_adaptation_session(session_id: str):
    """获取会话详情"""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
    return session.to_dict()


@router.post("/sessions/{session_id}/step1")
async def run_step1(session_id: str, req: Step1ContextRequest):
    """Step 1: 收集上下文信息

    补充或更新上下文信息（模型路径、实现根目录、交付仓库等）。
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")

    # 路径安全校验
    if req.model_path:
        _validate_path_safety(req.model_path, "model_path")
    if req.implementation_root:
        _validate_path_safety(req.implementation_root, "implementation_root")
    if req.delivery_repo:
        _validate_path_safety(req.delivery_repo, "delivery_repo")
    if req.vllm_path:
        _validate_path_safety(req.vllm_path, "vllm_path")

    context = {}
    if req.model_path:
        context["model_path"] = req.model_path
    if req.implementation_root:
        context["implementation_root"] = req.implementation_root
    if req.delivery_repo:
        context["delivery_repo"] = req.delivery_repo
    if req.features:
        context["features"] = req.features
    if req.vllm_path:
        context["vllm_path"] = req.vllm_path
    if req.transformers_version:
        context["transformers_version"] = req.transformers_version

    step = step1_collect_context(session_id, context)
    return step.to_dict()


@router.post("/sessions/{session_id}/step2")
async def run_step2(session_id: str):
    """Step 2: 分析模型

    读取 config.json，推断架构类型、注意力变体、量化类型、key prefix。
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")

    step = step2_analyze_model(session_id)
    return step.to_dict()


@router.post("/sessions/{session_id}/step3")
async def run_step3(session_id: str, req: Step3OperatorGateRequest):
    """Step 3: 算子兼容性门控

    扫描代码中的算子类型，分类为 Torch/Triton/CUDA。
    CUDA without fallback → BLOCKED。
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")

    step = step3_operator_gate(session_id, req.model_code)
    return step.to_dict()


@router.post("/sessions/{session_id}/step4")
async def run_step4(session_id: str, req: Step4FrameworkAnalysisRequest):
    """Step 4: 框架侧代码分析

    检查 vLLM registry.py 中是否已有架构注册，检查 vllm-ascend 补丁。
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")

    if req.vllm_path:
        _validate_path_safety(req.vllm_path, "vllm_path")

    step = step4_framework_analysis(session_id, req.vllm_path)
    return step.to_dict()


@router.post("/sessions/{session_id}/step5")
async def run_step5(session_id: str):
    """Step 5: 选择适配策略

    基于 step 2-4 结果自动判断策略：reuse/patch/new_adapter/blocked。
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")

    step = step5_choose_strategy(session_id)
    return step.to_dict()


@router.post("/sessions/{session_id}/step6")
async def run_step6(session_id: str, req: Step6ImplementRequest):
    """Step 6: 实现最小代码改动

    根据适配策略生成适配器代码模板。
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")

    step = step6_implement(session_id, req.implementation_details)
    return step.to_dict()


@router.post("/sessions/{session_id}/step7-dummy")
async def run_step7_dummy(session_id: str, req: Step7DummyRequest):
    """Step 7a: Dummy Fast Gate

    生成 vllm serve --load-format dummy 命令，快速验证模型加载流程。
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")

    config = {
        "model_path": req.model_path or session.model_path,
        "tensor_parallel_size": req.tensor_parallel_size,
        "host": req.host,
        "port": req.port,
        "max_model_len": req.max_model_len,
    }

    step = step7_validate_dummy(session_id, config)
    return step.to_dict()


@router.post("/sessions/{session_id}/step7-real")
async def run_step7_real(session_id: str, req: Step7RealRequest):
    """Step 7b: Real-Weight Mandatory Gate

    使用实际权重验证模型加载和推理。
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")

    config = {
        "model_path": req.model_path or session.model_path,
        "tensor_parallel_size": req.tensor_parallel_size,
        "host": req.host,
        "port": req.port,
        "max_model_len": req.max_model_len,
        "gpu_memory_utilization": req.gpu_memory_utilization,
    }

    step = step7_validate_real(session_id, config)
    return step.to_dict()


@router.post("/sessions/{session_id}/step8")
async def run_step8(session_id: str, req: Step8InferenceRequest):
    """Step 8: 验证推理和功能

    生成 curl 测试命令，验证模型推理能力。
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")

    step = step8_validate_inference(session_id, req.host, req.port)
    return step.to_dict()


@router.post("/sessions/{session_id}/step9")
async def run_step9(session_id: str):
    """Step 9: 生成产物

    生成 YAML 配置、文档、提交命令。
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")

    step = step9_generate_artifacts(session_id)
    return step.to_dict()


@router.post("/sessions/{session_id}/step10")
async def run_step10(session_id: str):
    """Step 10: 交接产物

    汇总所有步骤结果，生成交接报告。
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")

    step = step10_handoff(session_id)
    return step.to_dict()


@router.get("/quick-reference")
async def adaptation_quick_reference():
    """获取 adapt-agent 快速参考"""
    return get_quick_reference()

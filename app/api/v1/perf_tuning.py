"""昇腾 NPU 性能调优 API 端点

遵循 ascend-ai4s-perf-tuning skill 规范：
- 渐进式调优：逐项开启，负优化回退
- 编译优化为进阶手段：需用户确认后才执行
- 配合 Profiling 使用：调优前后各采集一次 L0 Profiling
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.perf_tuning import (
    AffinityMode,
    AllocStrategy,
    ProgressiveTuningExecutor,
    TaskQueueMode,
    TuningConfig,
    analyze_launch_script,
    detect_numa_topology,
    detect_tcmalloc,
    diagnose_bottleneck,
    generate_launch_command,
    generate_python_compile_script,
    generate_pytorch_compile_script,
    generate_torch_npu_compile_script,
    get_recommended_configs,
    install_tcmalloc_instructions,
    suggest_code_optimizations,
)

router = APIRouter(dependencies=[Depends(get_current_user)])


# ========== Request Models ==========


class TuningConfigRequest(BaseModel):
    """调优配置请求"""

    task_queue_enable: int = Field(
        default=2, ge=0, le=2, description="流水优化模式: 0=关闭, 1=开启, 2=增强(推荐)"
    )
    cpu_affinity_mode: int = Field(
        default=0, ge=0, le=2, description="CPU 绑核模式: 0=不启用, 1=粗粒度, 2=细粒度"
    )
    cpu_affinity_custom: str = Field(
        default="", description="自定义绑核范围，如 'npu0:0-1,npu1:2-5'"
    )
    tcmalloc_enabled: bool = Field(
        default=False, description="是否启用 tcmalloc 内存库替换"
    )
    tcmalloc_path: str = Field(
        default="", description="libtcmalloc.so 路径（留空自动检测）"
    )
    alloc_strategy: str = Field(
        default="expandable_segments",
        description="内存分配策略: off / expandable_segments",
    )
    enable_acl_graph: bool = Field(default=True, description="是否启用 ACL Graph 加速")
    omp_proc_bind: bool = Field(
        default=False, description="OMP_PROC_BIND（编译优化后设为 false）"
    )


class LaunchCommandRequest(BaseModel):
    """启动命令生成请求"""

    config: TuningConfigRequest
    script_path: str = Field(default="train.py", description="启动脚本路径")
    extra_env: dict[str, str] | None = Field(default=None, description="额外环境变量")


class CompileScriptRequest(BaseModel):
    """编译优化脚本生成请求"""

    # Python 编译
    python_version: str = Field(default="3.8.17", description="Python 版本")
    install_dir: str = Field(default="/opt/python-ascend", description="安装目录")
    # PyTorch 编译
    pytorch_version: str = Field(default="2.1.0", description="PyTorch 版本")
    profile_dir: str = Field(
        default="/tmp/pytorch_profile", description="PGO Profile 目录"
    )
    # torch_npu 编译
    torch_npu_version: str = Field(default="2.1.0", description="torch_npu 版本")
    torch_npu_profile_dir: str = Field(
        default="/tmp/torch_npu_profile", description="torch_npu PGO Profile 目录"
    )
    # 通用
    pgo: bool = Field(default=False, description="是否启用 PGO（需两次编译）")


class ScriptAnalysisRequest(BaseModel):
    """脚本分析请求（optimizer-agent-plus Phase 2）"""

    script: str = Field(..., description="vLLM 启动脚本内容")


class BottleneckDiagnosisRequest(BaseModel):
    """瓶颈诊断请求（ascend-optimization skill）"""

    npu_utilization_pct: float = Field(
        default=0, ge=0, le=100, description="NPU 利用率"
    )
    cube_operator_ratio: float = Field(
        default=0, ge=0, le=100, description="Cube 算子占比"
    )
    communication_ratio: float = Field(
        default=0, ge=0, le=100, description="通信算子占比"
    )
    free_time_ratio: float = Field(
        default=0, ge=0, le=100, description="Free Time 占比"
    )
    cpu_operator_ratio: float = Field(
        default=0, ge=0, le=100, description="CPU 算子占比"
    )
    memory_peak_pct: float = Field(default=0, ge=0, le=100, description="内存峰值占比")
    dequeue_blocking_ratio: float = Field(
        default=0, ge=0, le=100, description="Dequeue 阻塞占比"
    )
    malloc_free_ratio: float = Field(
        default=0, ge=0, le=100, description="malloc/free 占比"
    )


class CodeOptimizationRequest(BaseModel):
    """代码层优化建议请求（ascend-optimization skill）"""

    model_code: str = Field(
        default="", description="模型代码内容（可选，用于检测可优化路径）"
    )


# ========== Helper ==========


def _request_to_config(req: TuningConfigRequest) -> TuningConfig:
    """将请求模型转换为 TuningConfig"""
    return TuningConfig(
        task_queue_enable=TaskQueueMode(req.task_queue_enable),
        cpu_affinity_mode=AffinityMode(req.cpu_affinity_mode),
        cpu_affinity_custom=req.cpu_affinity_custom,
        tcmalloc_enabled=req.tcmalloc_enabled,
        tcmalloc_path=req.tcmalloc_path,
        alloc_strategy=AllocStrategy(req.alloc_strategy),
        enable_acl_graph=req.enable_acl_graph,
        omp_proc_bind=req.omp_proc_bind,
    )


# ========== API Endpoints ==========


@router.get("/status")
async def tuning_status():
    """性能调优模块状态"""
    return {
        "module": "ascend_perf_tuning",
        "status": "active",
        "description": "昇腾 NPU 通用性能调优",
        "tuning_levels": [
            {"level": "pipeline", "name": "流水优化", "env_var": "TASK_QUEUE_ENABLE"},
            {
                "level": "cpu_affinity",
                "name": "CPU 绑核",
                "env_var": "CPU_AFFINITY_CONF",
            },
            {"level": "tcmalloc", "name": "高性能内存库替换", "env_var": "LD_PRELOAD"},
            {
                "level": "alloc_conf",
                "name": "内存分配策略",
                "env_var": "PYTORCH_NPU_ALLOC_CONF",
            },
            {
                "level": "compile_python",
                "name": "Python 编译优化（进阶）",
                "env_var": "CC/CXX + --with-lto",
            },
            {
                "level": "compile_torch",
                "name": "PyTorch 编译优化（进阶）",
                "env_var": "CMAKE_C_FLAGS + -flto",
            },
            {
                "level": "compile_torch_npu",
                "name": "torch_npu 编译优化（进阶）",
                "env_var": "ci/build.sh --enable_lto",
            },
        ],
        "principle": "渐进式调优：逐项开启，负优化回退",
    }


@router.get("/recommended-configs")
async def recommended_configs():
    """获取不同场景的推荐调优配置"""
    configs = get_recommended_configs()
    return {
        "configs": {name: config.to_dict() for name, config in configs.items()},
        "descriptions": {
            "training_default": "训练场景默认（流水+绑核+tcmalloc全开）",
            "training_conservative": "训练场景保守（仅流水优化，适合调试）",
            "inference_vllm": "vLLM 推理场景（绑核可能负优化，不启用）",
            "inference_embedding": "Embedding 推理场景（绑核+流水优化）",
        },
        "warning": "推荐配置仅供参考，建议逐项测试确认每项优化的实际收益",
    }


@router.post("/apply")
async def apply_tuning(req: TuningConfigRequest):
    """应用调优配置（渐进式执行）

    按"流水优化 → 绑核优化 → tcmalloc 替换 → 内存分配策略"顺序逐项执行。
    返回每项的执行结果和整体建议。
    """
    config = _request_to_config(req)
    executor = ProgressiveTuningExecutor(config)
    report = executor.run_all_basic()

    return {
        "report": report.to_dict(),
        "applied_env": executor.applied_env,
        "next_steps": [
            "1. 运行模型验证调优效果，记录性能指标",
            "2. 如果某项优化叠加后性能不升反降，将其去掉重新测试",
            "3. 建议调优前后各采集一次 L0 Profiling 量化收益",
            "4. 如需进一步优化，可使用 "
            "/perf-tuning/generate-compile-script 生成编译优化脚本",
        ],
    }


@router.post("/launch-command")
async def launch_command(req: LaunchCommandRequest):
    """生成带调优环境变量的启动命令"""
    config = _request_to_config(req.config)
    command = generate_launch_command(
        config=config,
        script_path=req.script_path,
        extra_env=req.extra_env,
    )
    return {
        "command": command,
        "config": config.to_dict(),
    }


@router.get("/detect-tcmalloc")
async def check_tcmalloc():
    """检测 tcmalloc 是否已安装"""
    result = detect_tcmalloc()
    if not result["installed"]:
        result["install_instructions"] = install_tcmalloc_instructions()
    return result


@router.get("/detect-numa")
async def check_numa():
    """检测 NUMA 拓扑（用于 CPU 绑核配置参考）"""
    result = detect_numa_topology()
    return result


@router.get("/quick-reference")
async def quick_reference():
    """调优快速参考"""
    return {
        "optimizations": [
            {
                "name": "流水优化",
                "env_var": "TASK_QUEUE_ENABLE=2",
                "applicable": "host-bound 网络",
                "risk": "内存峰值上升",
            },
            {
                "name": "粗粒度绑核",
                "env_var": "CPU_AFFINITY_CONF=1",
                "applicable": "CPU 瓶颈模型",
                "risk": "vLLM 等推理框架可能负优化",
            },
            {
                "name": "细粒度绑核",
                "env_var": "CPU_AFFINITY_CONF=2",
                "applicable": "CPU 瓶颈 + 核间切换",
                "risk": "同上",
            },
            {
                "name": "tcmalloc",
                "env_var": "LD_PRELOAD=...libtcmalloc.so",
                "applicable": "频繁内存分配",
                "risk": "需安装 gperftools",
            },
            {
                "name": "Python 编译优化",
                "env_var": "毕昇编译器 + --with-lto --enable-optimizations",
                "applicable": "所有场景",
                "risk": "需从源码重编 Python",
            },
            {
                "name": "PyTorch 编译优化",
                "env_var": "毕昇编译器 + LTO + PGO",
                "applicable": "Torch 模型",
                "risk": "需从源码重编，耗时长",
            },
            {
                "name": "torch_npu 编译优化",
                "env_var": "毕昇编译器 + LTO + PGO",
                "applicable": "Torch 模型",
                "risk": "依赖重编后的 PyTorch",
            },
        ],
        "progressive_order": [
            "1. 流水优化（TASK_QUEUE_ENABLE=2）— 通常有正向收益",
            "2. CPU 绑核（CPU_AFFINITY_CONF=1）— 需先单独验证效果",
            "3. tcmalloc（LD_PRELOAD）— 频繁内存分配场景",
            "4. [进阶] Python 编译优化 — 需用户确认",
            "5. [进阶] PyTorch 编译优化 — 需用户确认",
            "6. [进阶] torch_npu 编译优化 — 需用户确认",
        ],
        "negative_optimization_note": (
            "如果某项优化叠加后性能不升反降，应将其去掉，"
            "用剩余项的组合重新测试，找到最优子集"
        ),
        "references": [
            "https://www.hiascend.com/document/detail/zh/Pytorch/600/ptmoddevg/trainingmigrguide/performance_tuning_0058.html",
            "https://www.hiascend.com/document/detail/zh/Pytorch/600/ptmoddevg/trainingmigrguide/performance_tuning_0059.html",
            "https://www.hiascend.com/document/detail/zh/Pytorch/600/ptmoddevg/trainingmigrguide/performance_tuning_0067.html",
            "https://www.hiascend.com/document/detail/zh/Pytorch/600/ptmoddevg/trainingmigrguide/performance_tuning_0063.html",
            "https://www.hiascend.com/document/detail/zh/Pytorch/600/ptmoddevg/trainingmigrguide/performance_tuning_0064.html",
            "https://www.hiascend.com/document/detail/zh/Pytorch/600/ptmoddevg/trainingmigrguide/performance_tuning_0065.html",
        ],
    }


@router.post("/generate-compile-script/python")
async def generate_python_compile(req: CompileScriptRequest):
    """生成 Python 编译优化脚本（进阶）

    需要毕昇编译器环境。使用 LTO + PGO 从源码重编 Python。
    耗时较长，请确认后再执行。
    """
    script = generate_python_compile_script(
        python_version=req.python_version,
        install_dir=req.install_dir,
    )
    return {
        "script": script,
        "type": "python_compile",
        "version": req.python_version,
        "note": (
            "编译优化为进阶手段，需从源码重编 Python"
            "（使用毕昇编译器 + LTO + PGO），耗时较长但可提升 "
            "Python 解释器本身的执行效率。"
        ),
        "prerequisites": [
            "毕昇编译器已安装并配置 CC=clang, CXX=clang++",
            "编译依赖已安装（gcc, openssl-devel, readline-devel, zlib-devel 等）",
        ],
    }


@router.post("/generate-compile-script/pytorch")
async def generate_pytorch_compile(req: CompileScriptRequest):
    """生成 PyTorch 编译优化脚本（进阶）

    仅当项目基于 PyTorch 时使用。必须按 PyTorch → torch_npu 的顺序执行。
    """
    script = generate_pytorch_compile_script(
        pytorch_version=req.pytorch_version,
        profile_dir=req.profile_dir,
        pgo=req.pgo,
    )
    return {
        "script": script,
        "type": "pytorch_compile",
        "version": req.pytorch_version,
        "pgo_enabled": req.pgo,
        "note": (
            "PyTorch 编译优化为进阶手段，需从源码重编 PyTorch，"
            "耗时较长，推荐在容器中进行。"
        ),
        "prerequisites": [
            "毕昇编译器已安装并配置 CC=clang, CXX=clang++",
            "PyTorch 源码已获取（脚本会自动 clone）",
        ],
        "order_warning": "必须按 PyTorch → torch_npu 的顺序执行编译优化",
    }


@router.post("/generate-compile-script/torch-npu")
async def generate_torch_npu_compile(req: CompileScriptRequest):
    """生成 torch_npu 编译优化脚本（进阶）

    必须先完成 PyTorch 编译优化并安装。
    """
    script = generate_torch_npu_compile_script(
        torch_npu_version=req.torch_npu_version,
        profile_dir=req.torch_npu_profile_dir,
        pgo=req.pgo,
    )
    return {
        "script": script,
        "type": "torch_npu_compile",
        "version": req.torch_npu_version,
        "pgo_enabled": req.pgo,
        "note": "torch_npu 编译优化为进阶手段，必须先完成 PyTorch 编译优化并安装。",
        "prerequisites": [
            "毕昇编译器已安装并配置 CC=clang, CXX=clang++",
            "PyTorch 已用毕昇编译器重编并安装（第 6 节）",
            "torch_npu 源码已获取（脚本会自动 clone）",
        ],
    }


@router.get("/verify-env")
async def verify_tuning_env():
    """验证当前调优环境变量设置"""
    env_checks = {
        "TASK_QUEUE_ENABLE": {
            "value": None,
            "description": "流水优化",
            "recommended": "2",
        },
        "CPU_AFFINITY_CONF": {
            "value": None,
            "description": "CPU 绑核",
            "recommended": "1 (训练) / 0 (vLLM推理)",
        },
        "LD_PRELOAD": {
            "value": None,
            "description": "tcmalloc 内存库",
            "recommended": "包含 libtcmalloc.so 路径",
        },
        "PYTORCH_NPU_ALLOC_CONF": {
            "value": None,
            "description": "内存分配策略",
            "recommended": "expandable_segments",
        },
        "ASCEND_ENABLE_ACL_GRAPH": {
            "value": None,
            "description": "ACL Graph 加速",
            "recommended": "1",
        },
        "OMP_PROC_BIND": {
            "value": None,
            "description": "OMP 绑定（编译优化后）",
            "recommended": "false",
        },
        "ASCEND_LAUNCH_BLOCKING": {
            "value": None,
            "description": "同步模式（调试用）",
            "recommended": "不设置（设为1时task_queue不生效）",
        },
    }

    import os

    warnings = []

    for key, info in env_checks.items():
        info["value"] = os.environ.get(key)

    # 特殊检查
    if os.environ.get("ASCEND_LAUNCH_BLOCKING") == "1":
        warnings.append(
            "ASCEND_LAUNCH_BLOCKING=1 时 task_queue 算子队列关闭，"
            "TASK_QUEUE_ENABLE 设置不生效"
        )

    if os.environ.get("TASK_QUEUE_ENABLE") == "2":
        warnings.append(
            "TASK_QUEUE_ENABLE=2 增强模式可能导致 NPU 内存峰值上升，"
            "如遇 OOM 请减小 batch_size 或回退到 TASK_QUEUE_ENABLE=1"
        )

    return {
        "env_vars": env_checks,
        "warnings": warnings,
    }


# ========== 脚本分析与瓶颈诊断（optimizer-agent-plus + ascend-optimization） ==========


@router.post("/analyze-script")
async def analyze_script(req: ScriptAnalysisRequest):
    """分析 vLLM 启动脚本，匹配优化案例库

    遵循 optimizer-agent-plus Phase 2 规范：
    1. 检测已应用的优化 → 标记为 implemented
    2. 检测适用但缺失的优化 → 加入建议
    3. 标记潜在问题配置
    4. 输出 Top 3 高影响建议
    """
    result = analyze_launch_script(req.script)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/diagnose-bottleneck")
async def diagnose_bottleneck_api(req: BottleneckDiagnosisRequest):
    """基于 Profiling 结果判断瓶颈类型

    遵循 ascend-optimization skill 规范：
    - compute-bound: 算子耗时高、NPU 忙
    - host-bound: Free Time 明显、Dequeue 阻塞、CPU 调度开销
    - memory-bound: 内存峰值高、malloc/free 频繁
    - communication-bound: 通信算子占比高
    """
    profiling_summary = {
        "npu_utilization_pct": req.npu_utilization_pct,
        "cube_operator_ratio": req.cube_operator_ratio,
        "communication_ratio": req.communication_ratio,
        "free_time_ratio": req.free_time_ratio,
        "cpu_operator_ratio": req.cpu_operator_ratio,
        "memory_peak_pct": req.memory_peak_pct,
        "dequeue_blocking_ratio": req.dequeue_blocking_ratio,
        "malloc_free_ratio": req.malloc_free_ratio,
    }
    return diagnose_bottleneck(profiling_summary)


@router.post("/suggest-code-optimizations")
async def suggest_code_optimizations_api(req: CodeOptimizationRequest):
    """生成代码层优化建议（torch_npu 亲和算子替换）

    遵循 ascend-optimization skill 规范：
    - 优先改热点路径，不要全模型盲目替换
    - 只有满足 dtype/shape/layout 约束时才替换
    - 保留 fallback 分支
    """
    return suggest_code_optimizations(req.model_code)

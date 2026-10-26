"""系统化调试 API 端点

遵循 systematic-debugging skill 规范四阶段流程：
Phase 1: Root Cause Investigation
Phase 2: Pattern Analysis
Phase 3: Hypothesis and Testing
Phase 4: Implementation
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.debugging import (
    DebugSession,
    DebugSessionManager,
    FixImplementer,
    HypothesisTester,
    PatternAnalyzer,
    RootCauseInvestigator,
    generate_debug_report,
    quick_diagnose,
)

router = APIRouter(dependencies=[Depends(get_current_user)])

# 全局会话管理器
_session_manager = DebugSessionManager()


# ========== Request Models ==========


class CreateSessionRequest(BaseModel):
    title: str = Field(default="", description="调试会话标题")


class ReadErrorRequest(BaseModel):
    session_id: str = Field(description="会话 ID")
    error_text: str = Field(description="错误信息文本")


class ParseTraceRequest(BaseModel):
    session_id: str = Field(description="会话 ID")
    trace_text: str = Field(description="堆栈跟踪文本")


class AddReproStepsRequest(BaseModel):
    session_id: str = Field(description="会话 ID")
    steps: list[str] = Field(description="复现步骤列表")


class CheckRecentChangesRequest(BaseModel):
    session_id: str = Field(description="会话 ID")
    repo_path: str = Field(default=".", description="仓库路径")


class GatherBoundaryEvidenceRequest(BaseModel):
    session_id: str = Field(description="会话 ID")
    component_name: str = Field(description="组件名称")
    input_data: str | None = Field(default=None, description="输入数据")
    output_data: str | None = Field(default=None, description="输出数据")
    config: dict[str, Any] | None = Field(default=None, description="配置")


class TraceRootCauseRequest(BaseModel):
    session_id: str = Field(description="会话 ID")
    error_point: str = Field(description="错误发生位置")
    bad_value: str = Field(description="错误值")
    expected_value: str = Field(description="期望值")
    trace_chain: list[dict[str, str]] = Field(description="追溯链")


class SummarizeRootCauseRequest(BaseModel):
    session_id: str = Field(description="会话 ID")
    summary: str = Field(description="根因总结")


class AddWorkingExampleRequest(BaseModel):
    session_id: str = Field(description="会话 ID")
    description: str = Field(description="工作示例描述")
    code_path: str = Field(default="", description="代码路径")
    key_difference: str = Field(default="", description="关键差异")


class CompareBrokenWorkingRequest(BaseModel):
    session_id: str = Field(description="会话 ID")
    broken_path: str = Field(description="损坏代码路径")
    working_path: str = Field(description="工作代码路径")
    diff_description: str = Field(default="", description="差异描述")


class AnalyzeDependenciesRequest(BaseModel):
    session_id: str = Field(description="会话 ID")
    target_file: str = Field(description="目标文件")
    project_root: str = Field(default=".", description="项目根目录")


class FormHypothesisRequest(BaseModel):
    session_id: str = Field(description="会话 ID")
    statement: str = Field(description="假设陈述: '我认为 X 是根因'")
    because: str = Field(default="", description="原因: '因为 Y'")


class TestHypothesisRequest(BaseModel):
    session_id: str = Field(description="会话 ID")
    hypothesis_id: int = Field(description="假设 ID")
    test_description: str = Field(description="测试描述")
    minimal_change: str = Field(description="最小变更")
    result: str = Field(description="结果: confirmed / rejected / inconclusive")


class CreateFailingTestRequest(BaseModel):
    session_id: str = Field(description="会话 ID")
    test_description: str = Field(description="测试描述")
    test_code: str = Field(default="", description="测试代码")


class ApplyFixRequest(BaseModel):
    session_id: str = Field(description="会话 ID")
    root_cause_addressed: str = Field(description="针对的根因")
    description: str = Field(description="修复描述")
    test_passed_after: bool = Field(default=False, description="修复后测试是否通过")
    other_tests_broken: bool = Field(default=False, description="是否破坏其他测试")


class QuestionArchitectureRequest(BaseModel):
    session_id: str = Field(description="会话 ID")
    discussion: str = Field(description="架构质疑讨论")


class QuickDiagnoseRequest(BaseModel):
    error_text: str = Field(description="错误信息文本")


# ========== Helper ==========


def _get_session(session_id: str) -> DebugSession:
    session = _session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
    return session


# ========== API Endpoints ==========


@router.get("/status")
async def debugging_status() -> dict[str, Any]:
    """模块状态"""
    return {
        "module": "systematic_debugging",
        "status": "active",
        "description": "系统化调试 — 四阶段流程，铁律: NO FIXES WITHOUT ROOT CAUSE",
        "phases": [
            "1. Root Cause Investigation",
            "2. Pattern Analysis",
            "3. Hypothesis and Testing",
            "4. Implementation",
        ],
        "iron_law": "NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST",
        "endpoints": {
            "sessions": "GET /debugging/sessions",
            "create": "POST /debugging/sessions",
            "phase1_read_error": "POST /debugging/phase1/read-error",
            "phase1_parse_trace": "POST /debugging/phase1/parse-trace",
            "phase1_repro_steps": "POST /debugging/phase1/repro-steps",
            "phase1_recent_changes": "POST /debugging/phase1/recent-changes",
            "phase1_boundary": "POST /debugging/phase1/boundary-evidence",
            "phase1_trace_root": "POST /debugging/phase1/trace-root-cause",
            "phase1_summarize": "POST /debugging/phase1/summarize-root-cause",
            "phase2_working_example": "POST /debugging/phase2/working-example",
            "phase2_compare": "POST /debugging/phase2/compare",
            "phase2_dependencies": "POST /debugging/phase2/dependencies",
            "phase3_hypothesis": "POST /debugging/phase3/hypothesis",
            "phase3_test": "POST /debugging/phase3/test-hypothesis",
            "phase3_next_action": "GET /debugging/phase3/next-action/{session_id}",
            "phase4_failing_test": "POST /debugging/phase4/failing-test",
            "phase4_apply_fix": "POST /debugging/phase4/apply-fix",
            "phase4_question_arch": "POST /debugging/phase4/question-architecture",
            "diagnose": "POST /debugging/quick-diagnose",
            "report": "GET /debugging/report/{session_id}",
            "red_flags": "GET /debugging/red-flags/{session_id}",
        },
    }


@router.get("/sessions")
async def list_sessions() -> dict[str, Any]:
    """列出所有调试会话"""
    return {
        "sessions": _session_manager.list_sessions(),
        "total": len(_session_manager._sessions),
    }


@router.post("/sessions")
async def create_session(req: CreateSessionRequest) -> dict[str, Any]:
    """创建新调试会话"""
    session = _session_manager.create_session(req.title)
    return session.to_dict()


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    """获取会话详情"""
    session = _get_session(session_id)
    return session.to_dict()


# ========== Phase 1: Root Cause Investigation ==========


@router.post("/phase1/read-error")
async def read_error(req: ReadErrorRequest) -> dict[str, Any]:
    """Phase 1: 仔细阅读错误信息

    不要跳过任何错误或警告，它们往往包含精确解决方案
    """
    session = _get_session(req.session_id)
    investigator = RootCauseInvestigator(session)
    evidence = investigator.read_error_message(req.error_text)
    return evidence.to_dict()


@router.post("/phase1/parse-trace")
async def parse_trace(req: ParseTraceRequest) -> dict[str, Any]:
    """Phase 1: 完整阅读堆栈跟踪"""
    session = _get_session(req.session_id)
    investigator = RootCauseInvestigator(session)
    evidence = investigator.parse_stack_trace(req.trace_text)
    return evidence.to_dict()


@router.post("/phase1/repro-steps")
async def add_repro_steps(req: AddReproStepsRequest) -> dict[str, Any]:
    """Phase 1: 记录复现步骤

    能可靠触发吗？精确步骤是什么？每次都发生吗？
    """
    session = _get_session(req.session_id)
    investigator = RootCauseInvestigator(session)
    investigator.add_reproduction_steps(req.steps)
    return {
        "session_id": req.session_id,
        "repro_steps": req.steps,
        "step_count": len(req.steps),
    }


@router.post("/phase1/recent-changes")
async def check_recent_changes(req: CheckRecentChangesRequest) -> dict[str, Any]:
    """Phase 1: 检查最近变更

    什么变更可能导致这个问题？
    """
    session = _get_session(req.session_id)
    investigator = RootCauseInvestigator(session)
    changes = investigator.check_recent_changes(req.repo_path)
    return {
        "session_id": req.session_id,
        "recent_changes": changes,
    }


@router.post("/phase1/boundary-evidence")
async def gather_boundary_evidence(
    req: GatherBoundaryEvidenceRequest
) -> dict[str, Any]:
    """Phase 1: 收集组件边界证据

    多组件系统中，在每个边界记录数据进出和环境/配置传播
    """
    session = _get_session(req.session_id)
    investigator = RootCauseInvestigator(session)
    evidence = investigator.gather_boundary_evidence(
        component_name=req.component_name,
        input_data=req.input_data,
        output_data=req.output_data,
        config=req.config,
    )
    return evidence.to_dict()


@router.post("/phase1/trace-root-cause")
async def trace_root_cause(req: TraceRootCauseRequest) -> dict[str, Any]:
    """Phase 1: 追溯根因

    从错误点向上追踪，找到坏值的原始来源。
    修复应在来源处进行，而非症状处。
    """
    session = _get_session(req.session_id)
    investigator = RootCauseInvestigator(session)
    trace = investigator.trace_root_cause(
        error_point=req.error_point,
        bad_value=req.bad_value,
        expected_value=req.expected_value,
        trace_chain=req.trace_chain,
    )
    return trace.to_dict()


@router.post("/phase1/summarize-root-cause")
async def summarize_root_cause(req: SummarizeRootCauseRequest) -> dict[str, Any]:
    """Phase 1 完成: 总结根因

    完成 Phase 1 后才能进入 Phase 2
    """
    session = _get_session(req.session_id)
    investigator = RootCauseInvestigator(session)
    investigator.summarize_root_cause(req.summary)

    phase1_complete = investigator.is_phase1_complete()
    return {
        "session_id": req.session_id,
        "root_cause_summary": req.summary,
        "phase1_complete": phase1_complete,
        "current_phase": session.current_phase.value,
        "warning": (
            "Phase 1 未完成 — 在提出修复之前必须完成根因调查"
            if not phase1_complete
            else None
        ),
    }


# ========== Phase 2: Pattern Analysis ==========


@router.post("/phase2/working-example")
async def add_working_example(req: AddWorkingExampleRequest) -> dict[str, Any]:
    """Phase 2: 添加工作示例

    什么工作代码与损坏代码类似？
    """
    session = _get_session(req.session_id)
    analyzer = PatternAnalyzer(session)
    analyzer.add_working_example(req.description, req.code_path, req.key_difference)
    return {
        "session_id": req.session_id,
        "working_examples_count": len(session.working_examples),
    }


@router.post("/phase2/compare")
async def compare_broken_working(req: CompareBrokenWorkingRequest) -> dict[str, str]:
    """Phase 2: 对比损坏与工作代码

    每个差异都列出来，无论多小
    """
    session = _get_session(req.session_id)
    analyzer = PatternAnalyzer(session)
    diff = analyzer.compare_broken_vs_working(
        req.broken_path,
        req.working_path,
        req.diff_description,
    )
    return diff


@router.post("/phase2/dependencies")
async def analyze_dependencies(req: AnalyzeDependenciesRequest) -> dict[str, Any]:
    """Phase 2: 分析依赖关系

    需要什么其他组件？什么配置、环境？什么假设？
    """
    session = _get_session(req.session_id)
    analyzer = PatternAnalyzer(session)
    analysis = analyzer.analyze_dependencies(req.target_file, req.project_root)
    return analysis


# ========== Phase 3: Hypothesis and Testing ==========


@router.post("/phase3/hypothesis")
async def form_hypothesis(req: FormHypothesisRequest) -> dict[str, Any]:
    """Phase 3: 形成单一假设

    '我认为 X 是根因，因为 Y' — 必须明确，不能模糊
    """
    session = _get_session(req.session_id)
    tester = HypothesisTester(session)
    hypothesis = tester.form_hypothesis(req.statement, req.because)
    return hypothesis.to_dict()


@router.post("/phase3/test-hypothesis")
async def test_hypothesis(req: TestHypothesisRequest) -> dict[str, Any]:
    """Phase 3: 测试假设 — 最小变更，一个变量

    确认 → Phase 4; 拒绝 → 新假设; 不确定 → 收集更多证据
    """
    session = _get_session(req.session_id)
    tester = HypothesisTester(session)
    hypothesis = tester.test_hypothesis(
        req.hypothesis_id,
        req.test_description,
        req.minimal_change,
        req.result,
    )
    return hypothesis.to_dict()


@router.get("/phase3/next-action/{session_id}")
async def get_next_action(session_id: str) -> dict[str, Any]:
    """Phase 3: 获取下一步建议"""
    session = _get_session(session_id)
    tester = HypothesisTester(session)
    action = tester.get_next_action()
    return {"next_action": action, "current_phase": session.current_phase.value}


# ========== Phase 4: Implementation ==========


@router.post("/phase4/failing-test")
async def create_failing_test(req: CreateFailingTestRequest) -> dict[str, Any]:
    """Phase 4: 创建失败测试用例

    修复前必须有失败测试用例
    """
    session = _get_session(req.session_id)
    implementer = FixImplementer(session)
    attempt = implementer.create_failing_test(req.test_description, req.test_code)
    return attempt.to_dict()


@router.post("/phase4/apply-fix")
async def apply_fix(req: ApplyFixRequest) -> dict[str, Any]:
    """Phase 4: 应用单点修复

    一次只修一个根因，不要"顺手"重构
    """
    session = _get_session(req.session_id)
    implementer = FixImplementer(session)
    attempt = implementer.apply_fix(
        req.root_cause_addressed,
        req.description,
        req.test_passed_after,
        req.other_tests_broken,
    )

    # 检查红旗
    flags = RootCauseInvestigator(session).check_red_flags()

    return {
        **attempt.to_dict(),
        "red_flags": flags,
        "architecture_questioned": session.architecture_questioned,
    }


@router.post("/phase4/question-architecture")
async def question_architecture(req: QuestionArchitectureRequest) -> dict[str, Any]:
    """Phase 4: 3+ 次修复失败后质疑架构

    这不是假设失败 — 这是架构错误
    """
    session = _get_session(req.session_id)
    implementer = FixImplementer(session)
    implementer.question_architecture(req.discussion)
    return {
        "session_id": req.session_id,
        "architecture_questioned": True,
        "discussion": req.discussion[:500],
        "recommendation": "停止修复，与团队讨论架构方案",
    }


# ========== Utility Endpoints ==========


@router.post("/quick-diagnose")
async def quick_diagnose_endpoint(req: QuickDiagnoseRequest) -> dict[str, Any]:
    """快速诊断 — 从错误信息自动提取关键线索

    Phase 1 辅助工具
    """
    return quick_diagnose(req.error_text)


@router.get("/report/{session_id}")
async def get_report(session_id: str) -> dict[str, Any]:
    """生成调试报告"""
    session = _get_session(session_id)
    report = generate_debug_report(session)
    return report.to_dict()


@router.get("/red-flags/{session_id}")
async def get_red_flags(session_id: str) -> dict[str, Any]:
    """检查红旗"""
    session = _get_session(session_id)
    investigator = RootCauseInvestigator(session)
    flags = investigator.check_red_flags()
    return {
        "session_id": session_id,
        "red_flags": flags,
        "total_flags": len(session.red_flags),
        "architecture_questioned": session.architecture_questioned,
    }


@router.get("/quick-reference")
async def quick_reference() -> dict[str, Any]:
    """快速参考"""
    return {
        "iron_law": "NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST",
        "phases": {
            "1_root_cause": {
                "steps": [
                    "仔细阅读错误信息",
                    "一致地复现",
                    "检查最近变更",
                    "收集多组件边界证据",
                    "追溯数据流",
                ],
                "success_criteria": "理解了 WHAT 和 WHY",
            },
            "2_pattern": {
                "steps": [
                    "找到工作示例",
                    "与参考实现对比",
                    "识别差异",
                    "理解依赖",
                ],
                "success_criteria": "识别出差异",
            },
            "3_hypothesis": {
                "steps": [
                    "形成单一假设",
                    "最小测试",
                    "验证后继续",
                ],
                "success_criteria": "确认或新假设",
            },
            "4_implementation": {
                "steps": [
                    "创建失败测试用例",
                    "实施单点修复",
                    "验证修复",
                    "3+失败 → 质疑架构",
                ],
                "success_criteria": "Bug 已解决，测试通过",
            },
        },
        "red_flags": [
            "Quick fix for now, investigate later",
            "Just try changing X and see if it works",
            "Add multiple changes, run tests",
            "Skip the test, I'll manually verify",
            "One more fix attempt (when already tried 2+)",
        ],
        "rationalizations_to_avoid": {
            "Issue is simple": "Simple issues have root causes too",
            "Emergency, no time": "Systematic is faster than thrashing",
            "Just try this first": "First fix sets the pattern",
            "I'll write test after": "Untested fixes don't stick",
            "Multiple fixes at once": "Can't isolate what worked",
            "I see the problem": "Seeing symptoms ≠ understanding root cause",
            "One more fix attempt": "3+ failures = architectural problem",
        },
    }

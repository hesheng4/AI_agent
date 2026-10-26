"""系统化调试模块

遵循 systematic-debugging skill 规范的完整四阶段流程：

Phase 1: Root Cause Investigation — 先读错误、复现、查变更、收集证据
Phase 2: Pattern Analysis — 找工作示例、对比差异、理解依赖
Phase 3: Hypothesis and Testing — 单一假设、最小测试、验证
Phase 4: Implementation — 失败测试先行、单点修复、验证

铁律: NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
"""

import json
import logging
import os
import re
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

# ========== 路径安全校验 ==========

# 禁止的 shell 元字符（防注入）
_UNSAFE_PATH_CHARS = re.compile(r"[`;|$&!<>\n\r]")


def _validate_path_safety(
    path: str, field_name: str = "path", allow_empty: bool = False
) -> str:
    """校验路径安全性：防 shell 注入、空字节、路径遍历

    - allow_empty=True 时允许空路径（默认值场景）
    - 路径遍历 '..' 在调试场景下可能是合法的，但记录警告
    """
    if not path:
        if allow_empty:
            return path
        raise ValueError(f"{field_name} 不能为空")
    if not isinstance(path, str):
        raise ValueError(f"{field_name} 必须是字符串")
    if "\x00" in path:
        raise ValueError(f"{field_name} 包含空字节")
    if _UNSAFE_PATH_CHARS.search(path):
        raise ValueError(f"{field_name} 包含禁止字符: {path!r}")
    if ".." in path.split(os.sep) or ".." in path.split("/"):
        logging.getLogger("systematic_debugging").warning(
            f"{field_name} 包含路径遍历符 '..': {path!r}，请确认路径合法"
        )
    return path


logger = logging.getLogger("systematic_debugging")


# ========== 枚举与数据结构 ==========


class DebugPhase(Enum):
    """调试阶段"""

    ROOT_CAUSE = "root_cause"
    PATTERN = "pattern"
    HYPOTHESIS = "hypothesis"
    IMPLEMENTATION = "implementation"


class EvidenceType(Enum):
    """证据类型"""

    ERROR_MESSAGE = "error_message"
    STACK_TRACE = "stack_trace"
    REPRO_STEPS = "repro_steps"
    RECENT_CHANGES = "recent_changes"
    DATA_FLOW = "data_flow"
    COMPONENT_STATE = "component_state"
    BOUNDARY_LOG = "boundary_log"


class FixStatus(Enum):
    """修复状态"""

    PENDING = "pending"
    TEST_CREATED = "test_created"
    FIX_APPLIED = "fix_applied"
    VERIFIED = "verified"
    FAILED = "failed"
    ARCHITECTURE_QUESTION = "architecture_question"


@dataclass
class ErrorEvidence:
    """错误证据"""

    evidence_type: EvidenceType = EvidenceType.ERROR_MESSAGE
    raw_text: str = ""
    source_file: str = ""
    line_number: int = 0
    timestamp: str = ""
    component: str = ""
    phase: DebugPhase = DebugPhase.ROOT_CAUSE
    analysis: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_type": self.evidence_type.value,
            "raw_text": self.raw_text[:2000],
            "source_file": self.source_file,
            "line_number": self.line_number,
            "timestamp": self.timestamp,
            "component": self.component,
            "phase": self.phase.value,
            "analysis": self.analysis[:500],
            "tags": self.tags,
        }


@dataclass
class RootCauseTrace:
    """根因追溯链

    从错误点向上追踪，找到坏值的原始来源。
    遵循 root-cause-tracing.md 规范。
    """

    error_point: str = ""  # 错误发生位置
    bad_value: str = ""  # 错误值
    expected_value: str = ""  # 期望值
    trace_chain: list[dict[str, str]] = field(default_factory=list)
    root_cause: str = ""  # 最终根因
    fix_location: str = ""  # 修复位置（与根因可能不同）

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_point": self.error_point,
            "bad_value": self.bad_value,
            "expected_value": self.expected_value,
            "trace_chain": self.trace_chain,
            "root_cause": self.root_cause,
            "fix_location": self.fix_location,
        }


@dataclass
class Hypothesis:
    """假设"""

    id: int = 0
    statement: str = ""  # "我认为 X 是根因，因为 Y"
    tested: bool = False
    result: str = ""  # confirmed / rejected / inconclusive
    test_description: str = ""
    minimal_change: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "statement": self.statement,
            "tested": self.tested,
            "result": self.result,
            "test_description": self.test_description,
            "minimal_change": self.minimal_change[:500],
            "timestamp": self.timestamp,
        }


@dataclass
class FixAttempt:
    """修复尝试"""

    attempt_number: int = 0
    description: str = ""
    root_cause_addressed: str = ""
    test_created: bool = False
    test_passed_before: bool = False
    fix_applied: bool = False
    test_passed_after: bool = False
    other_tests_broken: bool = False
    status: FixStatus = FixStatus.PENDING
    timestamp: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt_number": self.attempt_number,
            "description": self.description,
            "root_cause_addressed": self.root_cause_addressed,
            "test_created": self.test_created,
            "test_passed_before": self.test_passed_before,
            "fix_applied": self.fix_applied,
            "test_passed_after": self.test_passed_after,
            "other_tests_broken": self.other_tests_broken,
            "status": self.status.value,
            "timestamp": self.timestamp,
            "notes": self.notes,
        }


@dataclass
class DebugSession:
    """调试会话 — 贯穿四阶段的完整记录"""

    session_id: str = ""
    title: str = ""
    created_at: str = ""
    updated_at: str = ""

    # Phase 1: Root Cause
    current_phase: DebugPhase = DebugPhase.ROOT_CAUSE
    error_evidence: list[ErrorEvidence] = field(default_factory=list)
    reproduction_steps: list[str] = field(default_factory=list)
    recent_changes: list[dict[str, str]] = field(default_factory=list)
    root_cause_traces: list[RootCauseTrace] = field(default_factory=list)
    root_cause_summary: str = ""

    # Phase 2: Pattern
    working_examples: list[dict[str, str]] = field(default_factory=list)
    broken_vs_working_diffs: list[dict[str, str]] = field(default_factory=list)
    dependency_analysis: dict[str, Any] = field(default_factory=dict)

    # Phase 3: Hypothesis
    hypotheses: list[Hypothesis] = field(default_factory=list)
    current_hypothesis_id: int = 0

    # Phase 4: Implementation
    fix_attempts: list[FixAttempt] = field(default_factory=list)
    architecture_questioned: bool = False
    architecture_discussion: str = ""

    # Red flags
    red_flags: list[str] = field(default_factory=list)

    # Outcome
    resolved: bool = False
    resolution: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "current_phase": self.current_phase.value,
            "error_evidence": [e.to_dict() for e in self.error_evidence],
            "reproduction_steps": self.reproduction_steps,
            "recent_changes": self.recent_changes,
            "root_cause_traces": [t.to_dict() for t in self.root_cause_traces],
            "root_cause_summary": self.root_cause_summary,
            "working_examples": self.working_examples,
            "broken_vs_working_diffs": self.broken_vs_working_diffs,
            "dependency_analysis": self.dependency_analysis,
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "current_hypothesis_id": self.current_hypothesis_id,
            "fix_attempts": [f.to_dict() for f in self.fix_attempts],
            "architecture_questioned": self.architecture_questioned,
            "architecture_discussion": self.architecture_discussion[:500],
            "red_flags": self.red_flags,
            "resolved": self.resolved,
            "resolution": self.resolution,
        }


@dataclass
class DebugReport:
    """调试报告"""

    session: DebugSession = field(default_factory=DebugSession)
    phase_checklist: dict[str, dict[str, Any]] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "session": self.session.to_dict(),
            "phase_checklist": self.phase_checklist,
            "recommendations": self.recommendations,
            "generated_at": self.generated_at,
        }


# ========== Phase 1: Root Cause Investigation ==========


class RootCauseInvestigator:
    """Phase 1: 根因调查器

    铁律: 在完成 Phase 1 之前，不能提出修复方案
    """

    def __init__(self, session: DebugSession):
        self.session = session

    def read_error_message(self, error_text: str) -> ErrorEvidence:
        """仔细阅读错误信息 — 不要跳过任何内容"""
        evidence = ErrorEvidence(
            evidence_type=EvidenceType.ERROR_MESSAGE,
            raw_text=error_text,
            timestamp=datetime.now().isoformat(),
            phase=DebugPhase.ROOT_CAUSE,
        )

        # 提取关键信息
        # 文件路径和行号
        file_match = re.search(
            r'File "(.+?)", line (\d+)',
            error_text,
        )
        if file_match:
            evidence.source_file = file_match.group(1)
            evidence.line_number = int(file_match.group(2))

        # 错误类型
        error_match = re.search(
            r"(\w+Error|\w+Exception|FAILED|SIGTERM|SIGSEGV)",
            error_text,
        )
        if error_match:
            evidence.tags.append(error_match.group(1))

        # 组件推断
        if "ascend" in error_text.lower() or "npu" in error_text.lower():
            evidence.component = "ascend"
        elif "vllm" in error_text.lower():
            evidence.component = "vllm"
        elif "torch" in error_text.lower():
            evidence.component = "pytorch"
        elif "database" in error_text.lower() or "sql" in error_text.lower():
            evidence.component = "database"
        elif "redis" in error_text.lower():
            evidence.component = "redis"
        elif "llm" in error_text.lower() or "openai" in error_text.lower():
            evidence.component = "llm"
        elif "auth" in error_text.lower() or "jwt" in error_text.lower():
            evidence.component = "auth"
        else:
            evidence.component = "unknown"

        self.session.error_evidence.append(evidence)
        self.session.updated_at = datetime.now().isoformat()
        return evidence

    def parse_stack_trace(self, trace_text: str) -> ErrorEvidence:
        """完整阅读堆栈跟踪"""
        evidence = ErrorEvidence(
            evidence_type=EvidenceType.STACK_TRACE,
            raw_text=trace_text,
            timestamp=datetime.now().isoformat(),
            phase=DebugPhase.ROOT_CAUSE,
        )

        # 提取调用链
        frames = re.findall(
            r'File "(.+?)", line (\d+), in (\w+)',
            trace_text,
        )
        if frames:
            evidence.source_file = frames[-1][0]  # 最内层
            evidence.line_number = int(frames[-1][1])
            for frame_file, frame_line, frame_func in frames:
                evidence.tags.append(f"{frame_file}:{frame_line}:{frame_func}")

        self.session.error_evidence.append(evidence)
        self.session.updated_at = datetime.now().isoformat()
        return evidence

    def add_reproduction_steps(self, steps: list[str]) -> None:
        """记录复现步骤"""
        self.session.reproduction_steps = steps
        self.session.updated_at = datetime.now().isoformat()

    def check_recent_changes(
        self, repo_path: str = ".", max_commits: int = 10
    ) -> list[dict[str, str]]:
        """检查最近变更"""
        # 校验用户输入的路径
        _validate_path_safety(repo_path, "repo_path", allow_empty=True)
        changes = []
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", f"-{max_commits}"],
                capture_output=True,
                text=True,
                cwd=repo_path or ".",
                timeout=30,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().splitlines():
                    parts = line.split(" ", 1)
                    changes.append(
                        {
                            "commit": parts[0] if parts else "",
                            "message": parts[1] if len(parts) > 1 else "",
                        }
                    )

            # 检查未提交的变更
            diff_result = subprocess.run(
                ["git", "diff", "--stat"],
                capture_output=True,
                text=True,
                cwd=repo_path,
                timeout=30,
            )
            if diff_result.stdout.strip():
                changes.append(
                    {
                        "commit": "UNCOMMITTED",
                        "message": diff_result.stdout.strip()[:200],
                    }
                )

        except Exception as e:
            changes.append(
                {
                    "commit": "ERROR",
                    "message": f"Git 检查失败: {str(e)}",
                }
            )

        self.session.recent_changes = changes
        self.session.updated_at = datetime.now().isoformat()
        return changes

    def gather_boundary_evidence(
        self,
        component_name: str,
        input_data: Any = None,
        output_data: Any = None,
        config: dict[str, Any] | None = None,
    ) -> ErrorEvidence:
        """多组件系统中收集边界证据

        在每个组件边界记录: 什么数据进入、什么数据离开、环境/配置是否传递
        """
        boundary: dict[str, Any] = {
            "component": component_name,
            "input": str(input_data)[:500] if input_data else "N/A",
            "output": str(output_data)[:500] if output_data else "N/A",
            "config": str(config)[:500] if config else "N/A",
            "env_propagation": {},
        }

        # 检查环境变量传播
        env_vars = [
            "ASCEND_RT_VISIBLE_DEVICES",
            "VLLM_USE_MODELSCOPE",
            "PYTORCH_NPU_ALLOC_CONF",
            "TASK_QUEUE_ENABLE",
            "HCCL_BUFFSIZE",
            "OMP_PROC_BIND",
            "DATABASE_URL",
            "REDIS_URL",
            "OPENAI_API_KEY",
            "SECRET_KEY",
        ]
        for var in env_vars:
            val = os.environ.get(var)
            boundary["env_propagation"][var] = "SET" if val else "UNSET"

        evidence = ErrorEvidence(
            evidence_type=EvidenceType.BOUNDARY_LOG,
            raw_text=json.dumps(boundary, indent=2, ensure_ascii=False),
            component=component_name,
            timestamp=datetime.now().isoformat(),
            phase=DebugPhase.ROOT_CAUSE,
            tags=["boundary", component_name],
        )

        self.session.error_evidence.append(evidence)
        self.session.updated_at = datetime.now().isoformat()
        return evidence

    def trace_root_cause(
        self,
        error_point: str,
        bad_value: str,
        expected_value: str,
        trace_chain: list[dict[str, str]],
    ) -> RootCauseTrace:
        """追溯根因 — 从错误点向上追踪到坏值的原始来源

        trace_chain 格式:
        [
            {"location": "func_a:42", "value_received": "...", "passed_to": "func_b"},
            {"location": "func_b:15", "value_received": "...", "passed_to": "func_c"},
        ]
        """
        trace = RootCauseTrace(
            error_point=error_point,
            bad_value=bad_value,
            expected_value=expected_value,
            trace_chain=trace_chain,
        )

        # 自动推断根因
        if trace_chain:
            first_link = trace_chain[0]
            trace.root_cause = "根因追溯: {} 处产生了错误值 '{}'，期望 '{}'".format(
                first_link.get("location", "unknown"),
                bad_value[:50],
                expected_value[:50],
            )
            trace.fix_location = first_link.get("location", "")

        self.session.root_cause_traces.append(trace)
        self.session.updated_at = datetime.now().isoformat()
        return trace

    def check_red_flags(self) -> list[str]:
        """检查红旗 — 如果命中，应该停止并返回 Phase 1"""
        flags = []
        attempt_count = len(self.session.fix_attempts)

        if attempt_count >= 3:
            flags.append(
                f"已尝试 {attempt_count} 次修复仍未解决 — 应质疑架构而非继续修复"
            )

        if attempt_count >= 2:
            broken_elsewhere = any(
                f.other_tests_broken for f in self.session.fix_attempts
            )
            if broken_elsewhere:
                flags.append("修复导致其他测试失败 — 可能是架构问题或共享状态耦合")

        if not self.session.root_cause_summary and attempt_count > 0:
            flags.append(
                "未确定根因就进行了修复 — 违反铁律: NO FIXES WITHOUT ROOT CAUSE"
            )

        # 检查是否有"快速修复"倾向
        for attempt in self.session.fix_attempts:
            if not attempt.test_created:
                flags.append(f"修复 #{attempt.attempt_number} 未先创建失败测试用例")

        self.session.red_flags.extend(flags)
        self.session.updated_at = datetime.now().isoformat()
        return flags

    def summarize_root_cause(self, summary: str) -> None:
        """Phase 1 完成: 总结根因"""
        self.session.root_cause_summary = summary
        self.session.current_phase = DebugPhase.PATTERN
        self.session.updated_at = datetime.now().isoformat()

    def is_phase1_complete(self) -> bool:
        """检查 Phase 1 是否完成"""
        has_evidence = len(self.session.error_evidence) > 0
        has_repro = len(self.session.reproduction_steps) > 0
        has_root_cause = bool(self.session.root_cause_summary)
        return has_evidence and has_repro and has_root_cause


# ========== Phase 2: Pattern Analysis ==========


class PatternAnalyzer:
    """Phase 2: 模式分析器"""

    def __init__(self, session: DebugSession):
        self.session = session

    def add_working_example(
        self,
        description: str,
        code_path: str = "",
        key_difference: str = "",
    ) -> None:
        """添加工作示例"""
        self.session.working_examples.append(
            {
                "description": description,
                "code_path": code_path,
                "key_difference": key_difference,
            }
        )
        self.session.updated_at = datetime.now().isoformat()

    def compare_broken_vs_working(
        self,
        broken_path: str,
        working_path: str,
        diff_description: str = "",
    ) -> dict[str, str]:
        """对比损坏与工作的代码"""
        diff_result = {
            "broken_path": broken_path,
            "working_path": working_path,
            "diff_description": diff_description,
            "diff_output": "",
        }

        try:
            # 校验用户输入的路径
            _validate_path_safety(broken_path, "broken_path")
            _validate_path_safety(working_path, "working_path")
            result = subprocess.run(
                ["git", "diff", "--no-index", broken_path, working_path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            diff_result["diff_output"] = result.stdout[:3000]
        except ValueError as e:
            diff_result["diff_output"] = f"路径校验失败: {str(e)}"
        except Exception as e:
            diff_result["diff_output"] = f"Diff 失败: {str(e)}"

        self.session.broken_vs_working_diffs.append(diff_result)
        self.session.updated_at = datetime.now().isoformat()
        return diff_result

    def analyze_dependencies(
        self,
        target_file: str,
        project_root: str = ".",
    ) -> dict[str, Any]:
        """分析依赖关系"""
        # 校验用户输入的路径
        _validate_path_safety(target_file, "target_file")
        _validate_path_safety(project_root, "project_root", allow_empty=True)
        analysis = {
            "target_file": target_file,
            "imports": [],
            "imported_by": [],
            "config_deps": [],
            "env_deps": [],
        }

        try:
            with open(target_file, encoding="utf-8", errors="replace") as f:
                content = f.read()

            # 提取 import
            import_matches = re.findall(
                r"^(?:from|import)\s+([\w.]+)",
                content,
                re.MULTILINE,
            )
            analysis["imports"] = list(set(import_matches))[:50]

            # 提取环境变量依赖
            env_matches = re.findall(
                r'os\.environ\.get\(["\'](\w+)["\']\)',
                content,
            )
            analysis["env_deps"] = list(set(env_matches))

            # 提取配置依赖
            config_matches = re.findall(
                r"(?:settings|config)\.(\w+)",
                content,
            )
            analysis["config_deps"] = list(set(config_matches))

        except Exception as e:
            analysis["error"] = str(e)

        self.session.dependency_analysis = analysis
        self.session.updated_at = datetime.now().isoformat()
        return analysis

    def is_phase2_complete(self) -> bool:
        """检查 Phase 2 是否完成"""
        has_working = len(self.session.working_examples) > 0
        has_diffs = len(self.session.broken_vs_working_diffs) > 0
        return has_working or has_diffs


# ========== Phase 3: Hypothesis and Testing ==========


class HypothesisTester:
    """Phase 3: 假设与测试器"""

    def __init__(self, session: DebugSession):
        self.session = session

    def form_hypothesis(
        self,
        statement: str,
        because: str = "",
    ) -> Hypothesis:
        """形成单一假设

        "我认为 X 是根因，因为 Y"
        必须明确，不能模糊
        """
        hypothesis = Hypothesis(
            id=len(self.session.hypotheses) + 1,
            statement=f"{statement} (因为 {because})" if because else statement,
            timestamp=datetime.now().isoformat(),
        )

        self.session.hypotheses.append(hypothesis)
        self.session.current_hypothesis_id = hypothesis.id
        self.session.updated_at = datetime.now().isoformat()
        return hypothesis

    def test_hypothesis(
        self,
        hypothesis_id: int,
        test_description: str,
        minimal_change: str,
        result: str,  # confirmed / rejected / inconclusive
    ) -> Hypothesis:
        """测试假设 — 最小变更，一个变量"""
        for h in self.session.hypotheses:
            if h.id == hypothesis_id:
                h.tested = True
                h.test_description = test_description
                h.minimal_change = minimal_change
                h.result = result
                h.timestamp = datetime.now().isoformat()
                self.session.updated_at = datetime.now().isoformat()
                return h

        raise ValueError(f"假设 #{hypothesis_id} 不存在")

    def get_next_action(self) -> str:
        """根据当前假设状态建议下一步"""
        if not self.session.hypotheses:
            return "Phase 3: 形成第一个假设 — '我认为 X 是根因，因为 Y'"

        last = self.session.hypotheses[-1]
        if not last.tested:
            return f"Phase 3: 测试假设 #{last.id} — 做最小变更来验证"

        if last.result == "confirmed":
            self.session.current_phase = DebugPhase.IMPLEMENTATION
            return "Phase 4: 假设已确认，进入实施 — 先创建失败测试用例"

        if last.result == "rejected":
            return "Phase 3: 假设被拒绝 — 基于新信息形成新假设"

        if last.result == "inconclusive":
            return "Phase 3: 结果不确定 — 增加诊断工具，收集更多证据"

        return "Phase 3: 继续假设-测试循环"


# ========== Phase 4: Implementation ==========


class FixImplementer:
    """Phase 4: 修复实施器

    铁律:
    - 修复前必须有失败测试
    - 一次只修一个根因
    - 不要"顺手"重构
    """

    def __init__(self, session: DebugSession):
        self.session = session

    def create_failing_test(
        self,
        test_description: str,
        test_code: str = "",
    ) -> FixAttempt:
        """创建失败测试用例 — 修复前必须有"""
        attempt = FixAttempt(
            attempt_number=len(self.session.fix_attempts) + 1,
            description=f"创建失败测试: {test_description}",
            test_created=True,
            test_passed_before=False,  # 应该失败
            timestamp=datetime.now().isoformat(),
        )

        self.session.fix_attempts.append(attempt)
        self.session.updated_at = datetime.now().isoformat()

        # 检查红旗
        self._check_attempt_count()

        return attempt

    def apply_fix(
        self,
        root_cause_addressed: str,
        description: str,
        test_passed_after: bool = False,
        other_tests_broken: bool = False,
    ) -> FixAttempt:
        """应用单点修复"""
        attempt = FixAttempt(
            attempt_number=len(self.session.fix_attempts) + 1,
            description=f"修复: {description}",
            root_cause_addressed=root_cause_addressed,
            fix_applied=True,
            test_passed_after=test_passed_after,
            other_tests_broken=other_tests_broken,
            timestamp=datetime.now().isoformat(),
        )

        if test_passed_after and not other_tests_broken:
            attempt.status = FixStatus.VERIFIED
        elif test_passed_after and other_tests_broken:
            attempt.status = FixStatus.FAILED
            attempt.notes = "修复通过但破坏了其他测试"
        else:
            attempt.status = FixStatus.FAILED

        self.session.fix_attempts.append(attempt)
        self.session.updated_at = datetime.now().isoformat()

        # 检查红旗
        self._check_attempt_count()

        return attempt

    def question_architecture(self, discussion: str) -> None:
        """3+ 次修复失败后，质疑架构

        这不是假设失败 — 这是架构错误
        """
        self.session.architecture_questioned = True
        self.session.architecture_discussion = discussion
        self.session.updated_at = datetime.now().isoformat()

    def mark_resolved(self, resolution: str) -> None:
        """标记已解决"""
        self.session.resolved = True
        self.session.resolution = resolution
        self.session.updated_at = datetime.now().isoformat()

    def _check_attempt_count(self) -> None:
        """检查修复尝试次数"""
        count = len(self.session.fix_attempts)
        if count >= 3:
            self.session.red_flags.append(
                f"已尝试 {count} 次修复 — 应质疑架构而非继续修复"
            )
            self.session.architecture_questioned = True


# ========== Debug Session Manager ==========


class DebugSessionManager:
    """调试会话管理器"""

    def __init__(self, storage_dir: str = "./debug_sessions"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, DebugSession] = {}

    def create_session(self, title: str = "") -> DebugSession:
        """创建新调试会话"""
        session_id = "debug_{}_{}".format(
            datetime.now().strftime("%Y%m%d"),
            len(self._sessions) + 1,
        )
        session = DebugSession(
            session_id=session_id,
            title=title or session_id,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> DebugSession | None:
        """获取会话"""
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[dict[str, Any]]:
        """列出所有会话"""
        return [
            {
                "session_id": s.session_id,
                "title": s.title,
                "current_phase": s.current_phase.value,
                "resolved": s.resolved,
                "updated_at": s.updated_at,
            }
            for s in self._sessions.values()
        ]

    @staticmethod
    def _validate_session_id(session_id: str) -> str:
        """校验 session_id 防止路径遍历

        合法格式：字母数字下划线短横线，不允许 . / \\ 等
        """
        if not session_id or not isinstance(session_id, str):
            raise ValueError("session_id 不能为空")
        if not re.match(r"^[a-zA-Z0-9_\-]+$", session_id):
            raise ValueError(
                f"非法 session_id: {session_id!r}，仅允许字母数字下划线短横线"
            )
        return session_id

    def save_session(self, session: DebugSession) -> str:
        """保存会话到文件"""
        self._validate_session_id(session.session_id)
        path = self.storage_dir / f"{session.session_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)
        return str(path)

    def load_session(self, session_id: str) -> DebugSession | None:
        """从文件加载会话"""
        self._validate_session_id(session_id)
        path = self.storage_dir / f"{session_id}.json"
        if not path.exists():
            return None

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        # 重建 DebugSession
        session = DebugSession(
            session_id=data.get("session_id", ""),
            title=data.get("title", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            current_phase=DebugPhase(data.get("current_phase", "root_cause")),
            root_cause_summary=data.get("root_cause_summary", ""),
            architecture_questioned=data.get("architecture_questioned", False),
            architecture_discussion=data.get("architecture_discussion", ""),
            red_flags=data.get("red_flags", []),
            resolved=data.get("resolved", False),
            resolution=data.get("resolution", ""),
        )
        self._sessions[session_id] = session
        return session


# ========== Diagnostic Instrumentation ==========


@contextmanager
def boundary_trace(
    component_name: str, log_inputs: bool = True, log_outputs: bool = True
) -> Iterator[Any]:
    """边界追踪上下文管理器

    在组件边界添加诊断工具:
    - 记录什么数据进入
    - 记录什么数据离开
    - 验证环境/配置传播

    用法:
        with boundary_trace("vllm_service") as bt:
            result = call_vllm(prompt)
            bt.output = result
    """

    class BoundaryTracer:
        def __init__(self) -> None:
            self.name = component_name
            self.input = None
            self.output = None
            self.error: str | None = None
            self.start_time = datetime.now().isoformat()
            self.env_snapshot: dict[str, str] = {}

        def capture_env(self, *var_names: str) -> None:
            for var in var_names:
                self.env_snapshot[var] = "SET" if os.environ.get(var) else "UNSET"

    bt = BoundaryTracer()
    logger.info(f"[BOUNDARY] >>> {component_name} ENTER")

    try:
        yield bt
    except Exception as e:
        bt.error = str(e)
        logger.error(f"[BOUNDARY] !!! {component_name} ERROR: {str(e)[:200]}")
        raise
    finally:
        if log_outputs and bt.output is not None:
            logger.info(f"[BOUNDARY] {component_name} OUTPUT: {str(bt.output)[:200]}")
        status = "ERROR" if bt.error else "OK"
        logger.info(f"[BOUNDARY] <<< {component_name} EXIT ({status})")


_ERROR_TYPE_PATTERNS = [
    (r"ImportError|ModuleNotFoundError", "import_error"),
    (r"FileNotFoundError", "file_not_found"),
    (r"PermissionError", "permission_denied"),
    (r"TimeoutError|TimeoutException", "timeout"),
    (r"ConnectionError|ConnectionRefusedError", "connection_error"),
    (r"KeyError", "key_error"),
    (r"TypeError", "type_error"),
    (r"ValueError", "value_error"),
    (r"AttributeError", "attribute_error"),
    (r"RuntimeError", "runtime_error"),
    (r"OSError", "os_error"),
    (r"MemoryError|OutOfMemoryError", "oom"),
    (r"SyntaxError", "syntax_error"),
    (r"AssertionError", "assertion_error"),
]

_COMPONENT_PATTERNS = {
    "ascend": r"ascend|npu|torch_npu|cann|hccl",
    "vllm": r"vllm|vllm-ascend",
    "pytorch": r"torch\.|pytorch|cuda",
    "database": r"database|sql|sqlite|mysql|postgres",
    "redis": r"redis",
    "llm": r"openai|llm|gpt|qwen|chat",
    "auth": r"auth|jwt|token|login",
    "api": r"fastapi|uvicorn|http|request|response",
}

_INVESTIGATION_BY_TYPE = {
    "import_error": [
        "检查包是否安装: pip list | grep <package>",
        "检查 Python 环境: which python / conda info",
        "检查 sys.path: python -c 'import sys; print(sys.path)'",
    ],
    "file_not_found": [
        "检查文件是否存在: ls -la <path>",
        "检查工作目录: pwd",
        "检查符号链接: readlink -f <path>",
    ],
    "connection_error": [
        "检查服务是否运行: curl <url>/health",
        "检查端口是否监听: ss -tlnp | grep <port>",
        "检查防火墙: iptables -L",
    ],
    "timeout": [
        "检查网络连通性: ping <host>",
        "检查服务负载: top / htop",
        "增加超时时间重试",
    ],
    "oom": [
        "检查内存使用: free -h / npu-smi info",
        "检查是否有内存泄漏",
        "减小 batch_size 或 max_model_len",
    ],
}

_COMMON_CAUSES_BY_COMPONENT = {
    "ascend": [
        "CANN 版本不匹配",
        "环境变量未设置 (PYTORCH_NPU_ALLOC_CONF 等)",
        "NPU 驱动版本过旧",
        "torch_npu 版本与 PyTorch 不匹配",
    ],
    "vllm": [
        "模型路径错误",
        "显存不足",
        "张量并行配置错误",
        "量化格式不匹配",
    ],
    "pytorch": [
        "CUDA/NPU 设备不可用",
        "张量形状不匹配",
        "数据类型错误",
    ],
}


def _extract_error_type(error_text: str) -> str:
    for pattern, etype in _ERROR_TYPE_PATTERNS:
        if re.search(pattern, error_text):
            return etype
    return "unknown"


def _extract_error_location(error_text: str) -> str:
    file_match = re.search(r'File "(.+?)", line (\d+)', error_text)
    if file_match:
        return f"{file_match.group(1)}:{file_match.group(2)}"
    return ""


def _infer_component(error_text: str) -> str:
    for comp, pattern in _COMPONENT_PATTERNS.items():
        if re.search(pattern, error_text, re.IGNORECASE):
            return comp
    return "unknown"


def quick_diagnose(error_text: str) -> dict[str, Any]:
    """快速诊断 — 从错误信息自动提取关键线索

    遵循 Phase 1 规范: 仔细阅读错误信息。
    各步骤拆分到 _extract_* / _infer_* 函数，便于单测与复用。
    """
    error_type = _extract_error_type(error_text)
    component = _infer_component(error_text)
    return {
        "error_type": error_type,
        "error_location": _extract_error_location(error_text),
        "component": component,
        "suggested_investigation": _INVESTIGATION_BY_TYPE.get(
            error_type,
            ["仔细阅读完整错误信息", "复现问题", "检查最近变更"],
        ),
        "common_causes": _COMMON_CAUSES_BY_COMPONENT.get(component, []),
        "phase": "root_cause",
    }


def generate_debug_report(session: DebugSession) -> DebugReport:
    """生成调试报告"""
    report = DebugReport(
        session=session,
        generated_at=datetime.now().isoformat(),
    )

    # Phase 检查清单
    report.phase_checklist = {
        "phase_1_root_cause": {
            "has_error_evidence": len(session.error_evidence) > 0,
            "has_repro_steps": len(session.reproduction_steps) > 0,
            "has_root_cause_summary": bool(session.root_cause_summary),
            "phase_complete": RootCauseInvestigator(session).is_phase1_complete(),
        },
        "phase_2_pattern": {
            "has_working_examples": len(session.working_examples) > 0,
            "has_comparison": len(session.broken_vs_working_diffs) > 0,
            "has_dependency_analysis": bool(session.dependency_analysis),
            "phase_complete": PatternAnalyzer(session).is_phase2_complete(),
        },
        "phase_3_hypothesis": {
            "has_hypotheses": len(session.hypotheses) > 0,
            "all_hypotheses_tested": (
                all(h.tested for h in session.hypotheses)
                if session.hypotheses
                else False
            ),
            "has_confirmed_hypothesis": any(
                h.result == "confirmed" for h in session.hypotheses
            ),
        },
        "phase_4_implementation": {
            "test_created_before_fix": all(
                f.test_created for f in session.fix_attempts if f.fix_applied
            ),
            "fix_attempt_count": len(session.fix_attempts),
            "architecture_questioned": session.architecture_questioned,
            "resolved": session.resolved,
        },
    }

    # 建议
    recommendations = []

    if not report.phase_checklist["phase_1_root_cause"]["phase_complete"]:
        recommendations.append("Phase 1 未完成 — 在提出修复之前，必须完成根因调查")

    if session.red_flags:
        recommendations.append("红旗警告: {}".format("; ".join(session.red_flags[:3])))

    if len(session.fix_attempts) >= 3 and not session.resolved:
        recommendations.append("3+ 次修复失败 — 停止修复，质疑架构，与团队讨论")

    if session.architecture_questioned:
        recommendations.append("架构已被质疑 — 在继续之前进行架构讨论")

    report.recommendations = recommendations

    return report

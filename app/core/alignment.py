"""精度对齐框架 - 基线对比约束与验收标准定义

按照 ascend-ai4s-precision-alignment skill 规则:
- 基线来源优先级: 官方文档 > 用户GPU结果 > CPU调试
- 阈值必须在比较前声明
- 严格同条件对比
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class BaselineSource(Enum):
    """基线来源（优先级从高到低）"""

    OFFICIAL_README = "official_readme"  # 官方 README
    OFFICIAL_EXAMPLE = "official_example"  # 官方示例
    OFFICIAL_BENCHMARK = "official_benchmark"  # 官方 benchmark
    OFFICIAL_DOC = "official_doc"  # 官方文档
    USER_GPU_RESULT = "user_gpu_result"  # 用户提供的 GPU 真实结果
    CPU_DEBUG_ONLY = "cpu_debug_only"  # 仅用于调试，不作为最终结论


class AlignmentTask(Enum):
    """对齐任务类型"""

    LLM_INFERENCE = "llm_inference"  # LLM 推理精度
    EMBEDDING_INFERENCE = "embedding_inference"  # Embedding 推理精度
    AGENT_PIPELINE = "agent_pipeline"  # 完整 Agent 流水线


@dataclass
class ComparisonConstraints:
    """对比约束 — 确保严格同条件比较

    任何一项不同都不能直接对比，必须在报告中说明差异。
    """

    # 模型
    model_name: str
    model_revision: str = ""  # commit hash 或版本
    checkpoint_path: str = ""

    # 推理参数
    dtype: str = "bfloat16"  # float16 / bfloat16 / float32
    max_model_len: int = 8192
    tensor_parallel_size: int = 4

    # 生成参数（LLM）
    temperature: float = 0.0  # 精度对比用 temperature=0
    top_k: int = 1  # 贪婪解码
    top_p: float = 1.0
    max_new_tokens: int = 128
    repetition_penalty: float = 1.0

    # Embedding 参数
    normalize_embeddings: bool = True
    batch_size: int = 32

    # 分词参数
    tokenizer: str = ""
    padding: str = "left"
    truncation: bool = True

    # 运行环境
    seed: int = 42
    device: str = "npu"
    vllm_version: str = ""
    torch_version: str = ""
    torch_npu_version: str = ""
    cann_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__

    def diff(self, other: ComparisonConstraints) -> dict[str, Any]:
        """对比两组约束，返回差异项"""
        differences = {}
        for key in self.__dict__:
            if self.__dict__[key] != other.__dict__[key]:
                differences[key] = {
                    "self": self.__dict__[key],
                    "other": other.__dict__[key],
                }
        return differences


@dataclass
class AlignmentThresholds:
    """精度对齐阈值 — 必须在比较前声明

    遵循规则：不能先看到 mismatch，再临时放宽阈值。
    """

    # LLM 推理阈值
    llm_exact_match: float = 1.0  # 贪婪解码下应完全匹配
    llm_logit_atol: float = 1e-3  # logits 绝对误差
    llm_logit_rtol: float = 1e-2  # logits 相对误差
    llm_token_match_rate: float = 1.0  # token 匹配率（贪婪解码）

    # Embedding 阈值
    emb_cosine_sim: float = 0.999  # 余弦相似度
    emb_l2_atol: float = 1e-3  # L2 距离绝对误差
    emb_element_atol: float = 1e-4  # 逐元素绝对误差
    emb_element_rtol: float = 1e-3  # 逐元素相对误差

    # 端到端 Agent 流水线
    agent_task_success_rate: float = 0.95  # 任务成功率
    agent_result_similarity: float = 0.90  # 结果语义相似度

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__


@dataclass
class AlignmentResult:
    """单次对齐比较结果"""

    task: AlignmentTask
    baseline_source: BaselineSource
    constraints: ComparisonConstraints
    thresholds: AlignmentThresholds

    # 比较结果
    passed: bool = False
    metric_name: str = ""
    metric_value: float = 0.0
    threshold_value: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)

    # 证据
    baseline_command: str = ""
    npu_command: str = ""
    baseline_output_snippet: str = ""
    npu_output_snippet: str = ""

    # 如果是 CPU 调试对比，必须标注
    is_cpu_debug_only: bool = False
    cpu_debug_note: str = ""

    def to_report_section(self) -> str:
        """生成报告片段"""
        lines = [
            f"### {self.task.value} 对齐结果",
            f"- **基线来源**: {self.baseline_source.value}",
            f"- **判定**: {'✅ PASS' if self.passed else '❌ FAIL'}",
            (
                f"- **指标**: {self.metric_name} = {self.metric_value:.6f} "
                f"(阈值: {self.threshold_value})"
            ),
        ]

        if self.is_cpu_debug_only:
            lines.append(f"- ⚠️ **CPU 调试对比**: {self.cpu_debug_note}")
            lines.append("  - 此对比仅用于调试，不作为最终精度对齐结论")
            lines.append("  - 不能证明 NPU 与官方模型一致")
            lines.append("  - 不能替代官方基线或用户 GPU 基线")

        if self.details:
            lines.append("- **详细信息**:")
            for k, v in self.details.items():
                lines.append(f"  - {k}: {v}")

        return "\n".join(lines)


@dataclass
class AlignmentReport:
    """完整精度对齐报告"""

    # 报告元信息
    model_name: str
    report_date: str = ""
    reporter: str = "Ascend Precision Alignment Agent"

    # 基线来源策略
    baseline_source_priority: list[str] = field(
        default_factory=lambda: [
            "官方 README / 官方示例 / 官方 benchmark / 官方文档",
            "用户提供的 GPU 真实运行结果",
        ]
    )

    # 对比约束摘要
    constraints_summary: dict[str, Any] = field(default_factory=dict)

    # 对齐结果
    results: list[AlignmentResult] = field(default_factory=list)

    # 结论
    overall_passed: bool = False
    coverage_description: str = ""
    most_likely_cause: str = ""
    next_steps: list[str] = field(default_factory=list)

    def generate_markdown(self) -> str:
        """生成完整 Markdown 报告（按章节拼装，便于维护）"""
        lines: list[str] = []
        lines.extend(self._md_header())
        lines.extend(self._md_baseline_policy())
        lines.extend(self._md_constraints_summary())
        lines.extend(self._md_acceptance_criteria())
        lines.extend(self._md_alignment_results())
        lines.extend(self._md_comparison_table())
        lines.extend(self._md_conclusion())
        lines.extend(self._md_cpu_warning())
        return "\n".join(lines)

    def _md_header(self) -> list[str]:
        return [
            f"# 精度对齐报告: {self.model_name}",
            "",
            f"**日期**: {self.report_date}",
            f"**报告人**: {self.reporter}",
            "",
        ]

    def _md_baseline_policy(self) -> list[str]:
        lines = ["## 基线来源策略", ""]
        for i, source in enumerate(self.baseline_source_priority, 1):
            lines.append(f"{i}. {source}")
        lines.append("")
        return lines

    def _md_constraints_summary(self) -> list[str]:
        lines = ["## 对比约束摘要", ""]
        for k, v in self.constraints_summary.items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")
        return lines

    def _md_acceptance_criteria(self) -> list[str]:
        lines = ["## 验收标准（预先声明）", ""]
        if self.results:
            thresholds = self.results[0].thresholds
            for k, v in thresholds.to_dict().items():
                lines.append(f"- **{k}**: {v}")
        lines.append("")
        return lines

    def _md_alignment_results(self) -> list[str]:
        lines = ["## 对齐结果", ""]
        for result in self.results:
            lines.append(result.to_report_section())
            lines.append("")
        return lines

    def _md_comparison_table(self) -> list[str]:
        lines = [
            "## 数值对比表",
            "",
            "| 任务 | 指标 | 实测值 | 阈值 | 结果 |",
            "|------|------|--------|------|------|",
        ]
        for r in self.results:
            status = "PASS" if r.passed else "FAIL"
            lines.append(
                f"| {r.task.value} | {r.metric_name} | "
                f"{r.metric_value:.6f} | {r.threshold_value} | {status} |"
            )
        lines.append("")
        return lines

    def _md_conclusion(self) -> list[str]:
        lines = [
            "## 总体结论",
            "",
            f"- **是否对齐**: {'✅ 是' if self.overall_passed else '❌ 否'}",
            f"- **比较覆盖范围**: {self.coverage_description}",
            f"- **最可能原因**: {self.most_likely_cause or 'N/A'}",
            "",
            "## 下一步动作",
            "",
        ]
        for i, step in enumerate(self.next_steps, 1):
            lines.append(f"{i}. {step}")
        lines.append("")
        return lines

    def _md_cpu_warning(self) -> list[str]:
        cpu_results = [r for r in self.results if r.is_cpu_debug_only]
        if not cpu_results:
            return []
        lines = [
            "## ⚠️ CPU 调试对比声明",
            "",
            "以下对比使用了 CPU 结果，仅用于调试目的：",
            "",
        ]
        for r in cpu_results:
            lines.append(f"- {r.task.value}: {r.cpu_debug_note}")
        lines.extend(
            [
                "",
                (
                    "**上述 CPU 对比不能证明 NPU 与官方模型一致，"
                    "不能替代官方基线或用户 GPU 基线。**"
                ),
                "",
            ]
        )
        return lines


# ========== 预定义的模型对齐配置 ==========

QWEN25_72B_CONSTRAINTS = ComparisonConstraints(
    model_name="Qwen/Qwen2.5-72B-Instruct",
    dtype="bfloat16",
    max_model_len=8192,
    tensor_parallel_size=4,
    temperature=0.0,
    top_k=1,
    top_p=1.0,
    max_new_tokens=128,
    tokenizer="Qwen/Qwen2.5-72B-Instruct",
)

BGE_LARGE_ZH_CONSTRAINTS = ComparisonConstraints(
    model_name="BAAI/bge-large-zh-v1.5",
    dtype="bfloat16",
    normalize_embeddings=True,
    batch_size=32,
)

DEFAULT_THRESHOLDS = AlignmentThresholds()

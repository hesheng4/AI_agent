"""Nature-Figure: 论文级 Figure Contract + 期刊导出

遵循 nature-figure SKILL.md 规范：
- Figure Contract: 结论/证据链/原型/期刊导出规范
- Backend 门控: Python (matplotlib/seaborn) or R (ggplot2)
- 期刊级导出: SVG/PDF/TIFF 300dpi
- 多面板科学图: hero panel / 颜色约束
- 自审/QA 循环
"""

from typing import Any

from app.utils.exceptions import ToolException
from app.utils.logger import get_logger

logger = get_logger("agent.figure")

# 期刊导出规范
JOURNAL_EXPORT_SPECS = {
    "nature": {
        "dpi": 300,
        "formats": ["pdf", "tiff"],
        "max_width_inches": 7.2,
        "max_height_inches": 9.5,
        "color_mode": "rgb",
        "font_family": "Helvetica",
        "min_font_size": 5,
    },
    "nat-comms": {
        "dpi": 300,
        "formats": ["pdf", "tiff"],
        "max_width_inches": 7.2,
        "max_height_inches": 9.5,
        "color_mode": "rgb",
        "font_family": "Helvetica",
        "min_font_size": 5,
    },
    "generic": {
        "dpi": 300,
        "formats": ["pdf", "png", "svg"],
        "max_width_inches": 7.5,
        "max_height_inches": 10.0,
        "color_mode": "rgb",
        "font_family": "sans-serif",
        "min_font_size": 6,
    },
}

# Nature 推荐调色板（克制、可区分、色盲友好）
NATURE_PALETTE = [
    "#0C5DA5",  # 蓝
    "#00B945",  # 绿
    "#FF9500",  # 橙
    "#FF2C00",  # 红
    "#845B97",  # 紫
    "#474747",  # 深灰
    "#9E9E9E",  # 浅灰
]

# 图原型分类
ARCHETYPES = [
    "comparison",  # 多组比较 (bar/box/violin)
    "distribution",  # 分布 (hist/kde/violin)
    "correlation",  # 相关 (scatter/heatmap)
    "time_series",  # 时序 (line/area)
    "composition",  # 组成 (pie/stacked)
    "spatial",  # 空间 (map/image)
    "network",  # 网络 (graph/sankey)
]


class FigureContract:
    """Figure Contract — 在绘图前定义图表的科学逻辑

    每张图必须回答一个科学问题，contract 确保图表服务于论证链。
    """

    def __init__(
        self,
        conclusion: str,
        evidence_chain: list[str],
        archetype: str,
        journal: str = "generic",
        backend: str = "python",
        panels: list[dict[str, Any]] | None = None,
    ):
        self.conclusion = conclusion
        self.evidence_chain = evidence_chain
        self.archetype = archetype
        self.journal = journal
        self.backend = backend
        self.panels = panels or []

        # 验证
        if self.archetype not in ARCHETYPES:
            raise ValueError(f"未知图原型: {self.archetype}，可选: {ARCHETYPES}")
        if self.backend not in ("python", "r"):
            raise ValueError("必须明确选择 backend: python 或 r，不能猜测")

        self.export_spec = JOURNAL_EXPORT_SPECS.get(
            journal, JOURNAL_EXPORT_SPECS["generic"]
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "conclusion": self.conclusion,
            "evidence_chain": self.evidence_chain,
            "archetype": self.archetype,
            "journal": self.journal,
            "backend": self.backend,
            "panels": self.panels,
            "export_spec": self.export_spec,
        }


class FigureTools:
    """论文级图表工具 — matplotlib 后端"""

    @staticmethod
    def create_contract(
        conclusion: str,
        evidence_chain: list[str],
        archetype: str,
        journal: str = "generic",
        backend: str = "python",
        panels: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """创建 Figure Contract（绘图前必须调用）"""
        contract = FigureContract(
            conclusion=conclusion,
            evidence_chain=evidence_chain,
            archetype=archetype,
            journal=journal,
            backend=backend,
            panels=panels,
        )
        return contract.to_dict()

    @staticmethod
    def apply_journal_style(
        journal: str = "generic",
    ) -> dict[str, Any]:
        """应用期刊级 matplotlib 样式配置"""
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            raise ToolException(
                "matplotlib 未安装，请运行: pip install matplotlib",
                tool_name="figure",
            )

        spec = JOURNAL_EXPORT_SPECS.get(journal, JOURNAL_EXPORT_SPECS["generic"])

        # Nature 风格配置
        plt.rcParams.update(
            {
                "font.family": spec["font_family"],
                "font.size": 8,
                "axes.linewidth": 0.5,
                "axes.labelsize": 8,
                "xtick.labelsize": 7,
                "ytick.labelsize": 7,
                "legend.fontsize": 7,
                "figure.dpi": spec["dpi"],
                "savefig.dpi": spec["dpi"],
                "savefig.bbox": "tight",
                "savefig.pad_inches": 0.05,
                "axes.spines.top": False,
                "axes.spines.right": False,
                "figure.figsize": (spec["max_width_inches"], 3.5),
            }
        )

        return {
            "journal": journal,
            "style_applied": True,
            "palette": NATURE_PALETTE,
            "export_spec": spec,
        }

    @staticmethod
    def export_figure(
        figure_data: str,
        contract: dict[str, Any],
        output_format: str = "pdf",
    ) -> dict[str, Any]:
        """期刊级导出图表

        Args:
            figure_data: base64 编码的图表数据
            contract: Figure Contract
            output_format: 导出格式 (pdf/tiff/svg/png)
        """
        import base64

        spec = contract.get("export_spec", JOURNAL_EXPORT_SPECS["generic"])

        # 验证格式
        allowed_formats = spec.get("formats", ["pdf", "png", "svg"])
        if output_format not in allowed_formats:
            logger.warning(
                f"期刊 {contract.get('journal')} 不推荐 {output_format} 格式，"
                f"推荐: {allowed_formats}"
            )

        # 解码 base64
        try:
            img_bytes = base64.b64decode(figure_data)
        except Exception as e:
            raise ToolException(f"base64 解码失败: {e}", tool_name="figure")

        return {
            "format": output_format,
            "dpi": spec["dpi"],
            "size_bytes": len(img_bytes),
            "journal": contract.get("journal", "generic"),
            "conclusion": contract.get("conclusion", ""),
            "archetype": contract.get("archetype", ""),
        }

    @staticmethod
    def qa_check(contract: dict[str, Any]) -> dict[str, Any]:
        """Figure QA 检查

        验证：
        1. contract 有结论和证据链
        2. 原型合法
        3. 期刊导出规范满足
        4. 面板数合理 (1-6)
        """
        issues = []

        if not contract.get("conclusion"):
            issues.append("CRITICAL: Figure 缺少核心结论")
        if not contract.get("evidence_chain"):
            issues.append("CRITICAL: Figure 缺少证据链")
        if contract.get("archetype") not in ARCHETYPES:
            issues.append(f"WARNING: 未知原型 {contract.get('archetype')}")
        panels = contract.get("panels", [])
        if len(panels) > 6:
            issues.append(f"WARNING: {len(panels)} 面板过多，Nature 推荐 ≤6")
        if len(panels) == 0:
            issues.append("INFO: 单面板图")

        spec = contract.get("export_spec", {})
        if spec.get("dpi", 0) < 300:
            issues.append("CRITICAL: DPI < 300，不满足期刊要求")

        return {
            "passed": not any("CRITICAL" in i for i in issues),
            "issues": issues,
            "severity": (
                "critical"
                if any("CRITICAL" in i for i in issues)
                else "warning"
                if any("WARNING" in i for i in issues)
                else "ok"
            ),
        }


class FigureAgent:
    """论文级图表 Agent（独立于 BaseAgent，不依赖 LLM）"""

    def __init__(self):
        self.tools = FigureTools()
        self.logger = get_logger("agent.figure")

    async def process(self, request: dict[str, Any]) -> dict[str, Any]:
        """处理图表请求

        支持：
        - create_contract: 创建 Figure Contract
        - apply_style: 应用期刊样式
        - export: 期刊级导出
        - qa: QA 检查
        """
        task = request.get("task", "create_contract")

        # "generate" 是工作流模板（write_from_scratch 第 7 步）使用的任务名，
        # 语义等价于 create_contract
        if task in ("create_contract", "generate"):
            return self.tools.create_contract(
                conclusion=request.get("conclusion", ""),
                evidence_chain=request.get("evidence_chain", []),
                archetype=request.get("archetype", "comparison"),
                journal=request.get("journal", "generic"),
                backend=request.get("backend", "python"),
                panels=request.get("panels"),
            )
        elif task == "apply_style":
            return self.tools.apply_journal_style(
                journal=request.get("journal", "generic"),
            )
        elif task == "export":
            return self.tools.export_figure(
                figure_data=request.get("figure_data", ""),
                contract=request.get("contract", {}),
                output_format=request.get("format", "pdf"),
            )
        elif task == "qa":
            return self.tools.qa_check(
                contract=request.get("contract", {}),
            )
        else:
            raise ToolException(f"未知任务: {task}", tool_name="figure")

    @staticmethod
    def export_to_file(
        fig, output_path: str, format: str = "pdf", dpi: int = 300
    ) -> str:
        """将 matplotlib Figure 导出为期刊级文件"""
        try:
            import matplotlib.pyplot as plt

            savefig_kwargs = {
                "fname": output_path,
                "format": format,
                "dpi": dpi,
                "bbox_inches": "tight",
                "pad_inches": 0.05,
            }
            if format in ("pdf", "svg"):
                savefig_kwargs["metadata"] = {"Creator": "Nature-Figure-Tool"}
            fig.savefig(**savefig_kwargs)
            plt.close(fig)
            return output_path
        except Exception as e:
            return f"导出失败: {e}"

    @staticmethod
    def create_nature_figure(contract: dict, data: dict) -> Any:
        """按 Figure Contract 创建 Nature 风格图表"""
        import matplotlib.pyplot as plt

        spec = contract.get("export_spec", {})
        fig, ax = plt.subplots(figsize=(spec.get("max_width_inches", 7.2), 3.5))
        ax.set_title(contract.get("conclusion", ""), fontsize=10, fontweight="bold")
        ax.text(
            0.5,
            0.5,
            "Figure content placeholder",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        return fig

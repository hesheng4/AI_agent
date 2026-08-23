"""数据导出工具"""

import csv
import io
import json
from datetime import datetime
from typing import Any

from app.utils.logger import get_logger

logger = get_logger("export")


class DataExporter:
    """数据导出器"""

    @staticmethod
    def to_csv(data: list[dict[str, Any]], filename: str = "export.csv") -> bytes:
        """导出为CSV"""
        logger.info(f"导出CSV: {len(data)} 行")

        if not data:
            return b""

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

        return output.getvalue().encode("utf-8-sig")  # 带BOM，Excel兼容

    @staticmethod
    def to_json(data: Any, filename: str = "export.json", pretty: bool = True) -> bytes:
        """导出为JSON"""
        logger.info("导出JSON")

        indent = 2 if pretty else None
        return json.dumps(data, ensure_ascii=False, indent=indent).encode("utf-8")

    @staticmethod
    def to_markdown_table(data: list[dict[str, Any]]) -> str:
        """导出为Markdown表格"""
        if not data:
            return ""

        headers = list(data[0].keys())
        lines = []

        # 表头
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

        # 数据行
        for row in data:
            values = [str(row.get(h, "")) for h in headers]
            lines.append("| " + " | ".join(values) + " |")

        return "\n".join(lines)

    @staticmethod
    def papers_to_bibtex(papers: list[dict[str, Any]]) -> str:
        """导出文献为BibTeX格式"""
        logger.info(f"导出BibTeX: {len(papers)} 篇")

        entries = []
        for i, paper in enumerate(papers, 1):
            # 生成key
            first_author = (
                paper.get("authors", ["unknown"])[0].split()[-1].lower()
                if paper.get("authors")
                else "unknown"
            )
            year = paper.get("year", "0000")
            key = f"{first_author}{year}_{i}"

            # 格式化作者
            authors = " and ".join(paper.get("authors", []))

            entry = f"""@article{{{key},
  title = {{{paper.get("title", "")}}},
  author = {{{authors}}},
  year = {{{year}}},
  journal = {{{paper.get("journal", "")}}},
  url = {{{paper.get("url", "")}}},
  abstract = {{{paper.get("abstract", "")[:200]}}}
}}"""
            entries.append(entry)

        return "\n\n".join(entries)

    @staticmethod
    def papers_to_ris(papers: list[dict[str, Any]]) -> str:
        """导出文献为RIS格式"""
        logger.info(f"导出RIS: {len(papers)} 篇")

        entries = []
        for paper in papers:
            entry = "TY  - JOUR"  # 期刊文章
            entry += f"\nTI  - {paper.get('title', '')}"

            for author in paper.get("authors", []):
                entry += f"\nAU  - {author}"

            if paper.get("year"):
                entry += f"\nPY  - {paper['year']}"
            if paper.get("journal"):
                entry += f"\nJO  - {paper['journal']}"
            if paper.get("abstract"):
                entry += f"\nAB  - {paper['abstract'][:500]}"
            if paper.get("url"):
                entry += f"\nUR  - {paper['url']}"

            entry += "\nER  - "
            entries.append(entry)

        return "\n\n".join(entries)

    @staticmethod
    def analysis_to_report(results: dict[str, Any], title: str = "数据分析报告") -> str:
        """生成分析报告"""
        logger.info("生成分析报告")

        report = f"""# {title}

生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 分析结果

"""
        # 添加结果
        if "results" in results:
            report += "### 统计数据\n\n"
            report += (
                f"```json\n"
                f"{json.dumps(results['results'], ensure_ascii=False, indent=2)}"
                f"\n```\n\n"
            )

        if "explanation" in results:
            report += "### AI解释\n\n"
            report += results["explanation"] + "\n\n"

        if "data_shape" in results:
            report += "### 数据规模\n\n"
            report += f"- 行数: {results['data_shape'][0]}\n"
            report += f"- 列数: {results['data_shape'][1]}\n\n"

        return report

    @staticmethod
    def experiment_to_report(plan: dict[str, Any]) -> str:
        """生成实验方案报告"""
        logger.info("生成实验方案报告")

        report = f"""# 实验方案

生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 研究目标

{plan.get("goal", "未指定")}

## 设计类型

{plan.get("design_type", "未指定")} - {plan.get("design_description", "")}

## 变量

- 自变量: {", ".join(plan.get("variables", {}).get("independent", []))}
- 因变量: {", ".join(plan.get("variables", {}).get("dependent", []))}
- 控制变量: {", ".join(plan.get("variables", {}).get("control", []))}

## 实验步骤

"""
        for i, step in enumerate(plan.get("steps", []), 1):
            report += f"{i}. {step}\n"

        report += f"""
## 样本量建议

- 最小样本量: {plan.get("sample_size_recommendation", {}).get("min", "N/A")}
- 推荐样本量: {plan.get("sample_size_recommendation", {}).get("recommended", "N/A")}
- 每组样本量: {plan.get("sample_size_recommendation", {}).get("per_group", "N/A")}

## 伦理考虑

"""
        for item in plan.get("ethical_considerations", []):
            report += f"- {item}\n"

        return report

    @staticmethod
    def to_latex(manuscript: dict[str, Any]) -> str:
        r"""导出为 LaTeX 文档骨架

        生成 \documentclass{article} + \title + \section 列表的基础骨架。
        所有用户内容经 LaTeX 特殊字符转义，避免 % # & _ { } \ 导致编译错误。
        """
        logger.info("导出 LaTeX")

        def _escape(text: str) -> str:
            """转义 LaTeX 特殊字符（与 latex_export._escape_latex 对齐的精简版）。"""
            if not text:
                return ""
            for char, repl in [
                ("\\", r"\textbackslash{}"),
                ("&", r"\&"),
                ("%", r"\%"),
                ("#", r"\#"),
                ("_", r"\_"),
                ("{", r"\{"),
                ("}", r"\}"),
                ("~", r"\textasciitilde{}"),
                ("^", r"\textasciicircum{}"),
            ]:
                text = text.replace(char, repl)
            return text

        title = _escape(manuscript.get("title", ""))
        sections = manuscript.get("sections", []) or []

        lines = [
            "\\documentclass{article}",
            f"\\title{{{title}}}",
            "\\begin{document}",
            "\\maketitle",
            "",
        ]

        for section in sections:
            if not isinstance(section, dict):
                continue
            sec_title = _escape(section.get("title", ""))
            sec_content = section.get("content", "")  # 正文内容假定已为 LaTeX 或纯文本
            lines.append(f"\\section{{{sec_title}}}")
            lines.append(sec_content)
            lines.append("")

        lines.append("\\end{document}")
        return "\n".join(lines)

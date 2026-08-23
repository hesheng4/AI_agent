"""LaTeX 编译环境集成 — 方案A：调用系统 LaTeX

安装前提：
- TeX Live 2025 已安装到 D:\\latex\\texlive\\2025
- xelatex / pdflatex / lualatex 在 PATH 中可用

功能：
1. 编译 .tex → PDF（xelatex/pdflatex/lualatex）
2. 解析 .log 文件检测排版问题
3. 编译前后 PDF 对比验证
4. 自动修复循环：修改 → 编译 → 检查 → 再修改
5. 支持 nature-polishing 的 LaTeX 排版修复
"""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.utils.logger import get_logger

logger = get_logger("latex_engine")

# 常见 LaTeX 排版问题的日志模式
LOG_PATTERNS = {
    "overfull_hbox": {
        "pattern": r"Overfull \\hbox \((\d+\.?\d*)pt too wide\)",
        "severity": "warning",
        "description": "行溢出（文字超出行宽）",
    },
    "overfull_vbox": {
        "pattern": r"Overfull \\vbox \((\d+\.?\d*)pt too high\)",
        "severity": "warning",
        "description": "盒溢出（内容超出盒高）",
    },
    "underfull_hbox": {
        "pattern": r"Underfull \\hbox .* detected at line (\d+)",
        "severity": "info",
        "description": "行不满（文字间距过大）",
    },
    "underfull_vbox": {
        "pattern": r"Underfull \\vbox .* has become empty",
        "severity": "info",
        "description": "竖直盒为空",
    },
    "float_too_large": {
        "pattern": r"Float too large for page by (\d+\.?\d*)pt",
        "severity": "critical",
        "description": "浮动体过大超出页面",
    },
    "rerun_file": {
        "pattern": r"Rerun to get .* right",
        "severity": "info",
        "description": "需要再次编译",
    },
    "undefined_ref": {
        "pattern": r"Reference `([^']+)' on page (\d+) undefined",
        "severity": "warning",
        "description": "未定义的引用",
    },
    "missing_font": {
        "pattern": r"Font .* not found",
        "severity": "critical",
        "description": "字体缺失",
    },
}


class LatexEngine:
    """LaTeX 编译引擎 — 调用系统 TeX Live"""

    def __init__(self):
        self.xelatex = shutil.which("xelatex")
        self.pdflatex = shutil.which("pdflatex")
        self.lualatex = shutil.which("lualatex")
        self._available = any([self.xelatex, self.pdflatex, self.lualatex])

    @property
    def available(self) -> bool:
        """检查 LaTeX 编译器是否可用"""
        return self._available

    def get_info(self) -> dict[str, Any]:
        """获取 LaTeX 环境信息"""
        info = {"available": self.available, "compilers": {}}
        for name, path in [
            ("xelatex", self.xelatex),
            ("pdflatex", self.pdflatex),
            ("lualatex", self.lualatex),
        ]:
            if path:
                try:
                    r = subprocess.run(
                        [path, "--version"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    ver = r.stdout.split("\n")[0] if r.stdout else "unknown"
                except Exception:
                    ver = "error"
                info["compilers"][name] = {"path": path, "version": ver}
        return info

    def compile(
        self,
        tex_path: str,
        engine: str = "xelatex",
        runs: int = 2,
        timeout: int = 120,
        output_dir: str | None = None,
    ) -> dict[str, Any]:
        """编译 .tex → PDF

        Args:
            tex_path: .tex 源文件路径
            engine: 编译引擎 (xelatex/pdflatex/lualatex)
            runs: 编译次数（解决引用需 2+ 次）
            timeout: 单次编译超时（秒）
            output_dir: 输出目录（默认与 .tex 同目录）

        Returns:
            编译结果 + 日志分析
        """
        if not self.available:
            return {
                "success": False,
                "error": (
                    "LaTeX 编译器未安装。请安装 TeX Live（2025 或更高版本）"
                    "并确保 xelatex/pdflatex/lualatex 在 PATH 中可用。"
                ),
            }

        # 选择编译器
        compiler = {
            "xelatex": self.xelatex,
            "pdflatex": self.pdflatex,
            "lualatex": self.lualatex,
        }.get(engine)
        if not compiler:
            return {"success": False, "error": f"{engine} 不可用"}

        tex_path = Path(tex_path)
        if not tex_path.exists():
            return {"success": False, "error": f"文件不存在: {tex_path}"}

        out_dir = output_dir or str(tex_path.parent)
        pdf_path = tex_path.with_suffix(".pdf")
        log_path = tex_path.with_suffix(".log")

        # 多次编译（解决交叉引用）：中间轮次仅用于解析引用，最终轮次的日志才用于问题分析
        for run in range(1, runs + 1):
            try:
                result = subprocess.run(
                    [
                        compiler,
                        "-interaction=nonstopmode",
                        "-halt-on-error",
                        f"-output-directory={out_dir}",
                        str(tex_path),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(tex_path.parent),
                )
                logger.info(f"LaTeX 编译第 {run} 次: 返回码={result.returncode}")
            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "error": f"编译超时 ({timeout}s)，第 {run} 次",
                }
            except Exception as e:
                return {"success": False, "error": f"编译异常: {e}"}

        # 解析日志
        issues = self.parse_log(str(log_path))
        success = pdf_path.exists()

        return {
            "success": success,
            "pdf_path": str(pdf_path) if success else None,
            "log_path": str(log_path),
            "engine": engine,
            "runs": runs,
            "issues": issues,
            "critical_count": sum(1 for i in issues if i["severity"] == "critical"),
            "warning_count": sum(1 for i in issues if i["severity"] == "warning"),
        }

    def parse_log(self, log_path: str) -> list[dict[str, Any]]:
        """解析 LaTeX .log 文件，提取排版问题"""
        if not os.path.exists(log_path):
            return []

        with open(log_path, encoding="utf-8", errors="replace") as f:
            log_content = f.read()

        issues = []
        for name, config in LOG_PATTERNS.items():
            for match in re.finditer(config["pattern"], log_content):
                issues.append(
                    {
                        "type": name,
                        "severity": config["severity"],
                        "description": config["description"],
                        "detail": match.group(0),
                        "groups": match.groups(),
                    }
                )

        # 按严重度排序
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        issues.sort(key=lambda x: severity_order.get(x["severity"], 3))

        return issues

    def auto_fix(
        self,
        tex_path: str,
        max_iterations: int = 3,
        engine: str = "xelatex",
    ) -> dict[str, Any]:
        """自动修复循环：修改 → 编译 → 检查 → 再修改

        针对常见排版问题自动应用修复：
        - Float too large → 添加 [H] 或缩小
        - Overfull hbox → 添加 \\sloppy 或调整断词
        - 稀疏页 → 添加 \\clearpage
        """
        tex_path = Path(tex_path)
        original = tex_path.read_text(encoding="utf-8")
        current = original
        history = []

        for iteration in range(1, max_iterations + 1):
            # 编译
            result = self.compile(str(tex_path), engine=engine)
            if not result["success"]:
                break

            issues = result["issues"]
            critical = [i for i in issues if i["severity"] == "critical"]
            warnings = [i for i in issues if i["severity"] == "warning"]

            if not critical and not warnings:
                history.append(
                    {
                        "iteration": iteration,
                        "action": "none",
                        "issues_remaining": 0,
                    }
                )
                break

            # 应用自动修复
            fixed = False

            # Fix 1: Float too large → 添加 [H]（仅对未指定位置选项的浮动体，
            # 与 writing/agent.py:fix_latex_layout 保持一致：
            # 不覆盖用户已指定的 [t]/[h] 等）
            if any(i["type"] == "float_too_large" for i in critical):
                current = re.sub(
                    r"\\begin\{figure\}(?!\[)",
                    r"\\begin{figure}[H]",
                    current,
                )
                current = re.sub(
                    r"\\begin\{table\}(?!\[)",
                    r"\\begin{table}[H]",
                    current,
                )
                fixed = True

            # Fix 2: Overfull hbox → 在 \begin{document} 后插入 \sloppy
            # （限定在文档体内，避免拼到文件开头破坏 preamble；
            #  \sloppy 是声明命令，作用于当前 group/文档体）
            if any(i["type"] == "overfull_hbox" for i in warnings):
                if r"\sloppy" not in current and r"\begin{document}" in current:
                    current = current.replace(
                        r"\begin{document}",
                        r"\begin{document}" + "\n" + r"\sloppy",
                        1,
                    )
                    fixed = True

            if fixed:
                tex_path.write_text(current, encoding="utf-8")
                history.append(
                    {
                        "iteration": iteration,
                        "action": "applied_fixes",
                        "critical_before": len(critical),
                        "warnings_before": len(warnings),
                    }
                )
            else:
                history.append(
                    {
                        "iteration": iteration,
                        "action": "manual_review_needed",
                        "critical": len(critical),
                        "warnings": len(warnings),
                    }
                )
                break

        # 最终编译
        final_result = self.compile(str(tex_path), engine=engine)

        return {
            "final_success": final_result["success"],
            "final_pdf": final_result.get("pdf_path"),
            "final_issues": final_result["issues"],
            "iterations": history,
            "was_modified": current != original,
        }

    def diff_pdfs(self, pdf_before: str, pdf_after: str) -> dict[str, Any]:
        """对比编译前后 PDF（基于文件大小 + 页数变化）"""
        try:
            import fitz  # PyMuPDF

            doc_before = fitz.open(pdf_before)
            doc_after = fitz.open(pdf_after)
            result = {
                "pages_before": len(doc_before),
                "pages_after": len(doc_after),
                "page_count_changed": len(doc_before) != len(doc_after),
            }
            doc_before.close()
            doc_after.close()
            return result
        except ImportError:
            # 降级：仅比较文件大小
            size_before = (
                os.path.getsize(pdf_before) if os.path.exists(pdf_before) else 0
            )
            size_after = os.path.getsize(pdf_after) if os.path.exists(pdf_after) else 0
            return {
                "size_before": size_before,
                "size_after": size_after,
                "size_changed": size_before != size_after,
            }

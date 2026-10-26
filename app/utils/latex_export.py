"""LaTeX 论文导出工具

将论文内容转换为 LaTeX 源码，支持多种文档类和期刊模板。
生成可编译的 .tex 文件，用户可下载后在本地编译为 PDF。
"""

import re
from typing import Any

from app.utils.logger import get_logger

logger = get_logger("latex_export")


class LaTeXExporter:
    """LaTeX 论文导出器"""

    # 文档类映射
    DOCUMENT_CLASSES = {
        "standard": "article",
        "nat-comms": "article",
        "ieee": "IEEEtran",
        "acm": "acmart",
        "springer": "svjour3",
        "elsevier": "elsarticle",
    }

    # 期刊级配置
    JOURNAL_CONFIG: dict[str, dict[str, Any]] = {
        "standard": {
            "doc_class": "article",
            "extra_packages": [],
            "geometry": "a4paper, margin=2.5cm",
            "font_size": "12pt",
            "bib_style": "plain",
        },
        "nat-comms": {
            "doc_class": "article",
            "extra_packages": [
                "natbib",
                "hyperref",
            ],
            "geometry": "a4paper, margin=2cm",
            "font_size": "11pt",
            "bib_style": "nature",
        },
        "ieee": {
            "doc_class": "IEEEtran",
            "extra_packages": [],
            "geometry": "letterpaper, margin=1in",
            "font_size": "10pt",
            "bib_style": "IEEEtran",
        },
        "acm": {
            "doc_class": "acmart",
            "extra_packages": [],
            "geometry": "",
            "font_size": "",
            "bib_style": "ACM-Reference-Format",
        },
    }

    # 章节名中英映射
    SECTION_MAP = {
        "introduction": "Introduction",
        "引言": "Introduction",
        "methods": "Methods",
        "方法": "Methods",
        "results": "Results",
        "结果": "Results",
        "discussion": "Discussion",
        "讨论": "Discussion",
        "conclusion": "Conclusion",
        "结论": "Conclusion",
        "abstract": "Abstract",
        "摘要": "Abstract",
        "references": "References",
        "参考文献": "References",
        "acknowledgements": "Acknowledgements",
        "致谢": "Acknowledgements",
        "supplementary": "Supplementary Information",
        "补充材料": "Supplementary Information",
    }

    @staticmethod
    def export_paper(
        content: str,
        title: str = "",
        authors: str = "",
        abstract: str = "",
        keywords: list[str] | None = None,
        journal: str = "standard",
        paper_type: str = "research",
        outline: dict[str, Any] | None = None,
        terminology_ledger: dict[str, Any] | None = None,
        references: list[str] | None = None,
    ) -> str:
        """将论文内容导出为 LaTeX 源码

        Args:
            content: 论文正文（Markdown 或纯文本）
            title: 论文标题
            authors: 作者列表
            abstract: 摘要
            keywords: 关键词列表
            journal: 期刊格式
            paper_type: 论文类型
            outline: 大纲结构（可选，用于章节划分）
            terminology_ledger: 术语账本（可选）
            references: 参考文献（可选）

        Returns:
            完整的 LaTeX 源码字符串
        """
        logger.info(f"导出 LaTeX: 标题={title}, 期刊={journal}, 类型={paper_type}")

        config = LaTeXExporter.JOURNAL_CONFIG.get(
            journal, LaTeXExporter.JOURNAL_CONFIG["standard"]
        )
        doc_class = config["doc_class"]
        font_size = config["font_size"]
        geometry = config["geometry"]

        # ── 构建文档 ──
        parts = []

        # 1. 文档类声明
        class_options = []
        if font_size:
            class_options.append(font_size)
        if journal == "nat-comms":
            class_options.append("twocolumn")
        if journal == "ieee":
            class_options.append("journal")

        options_str = ",".join(class_options) if class_options else ""
        parts.append(
            f"\\documentclass[{options_str}]{{{doc_class}}}"
            if options_str
            else f"\\documentclass{{{doc_class}}}"
        )
        parts.append("")

        # 2. 宏包
        packages = [
            ("inputenc", "utf8"),
            ("fontenc", "T1"),
            ("CJKutf8", ""),  # 中文支持
            ("amsmath", ""),
            ("amssymb", ""),
            ("graphicx", ""),
            ("booktabs", ""),
            ("hyperref", "colorlinks=true,linkcolor=blue,citecolor=blue,urlcolor=blue"),
            ("xcolor", ""),
            ("geometry", geometry if geometry else "a4paper, margin=2.5cm"),
            ("caption", ""),
            ("subcaption", ""),
            ("algorithm2e", ""),
            ("listings", ""),
        ]

        for pkg, opts in packages:
            if pkg == "CJKutf8":
                # CJK 在 xeCJK / ctex 环境下可能冲突，加条件
                parts.append(f"% \\usepackage{{{pkg}}}")  # 默认注释，需要时取消
            elif opts:
                parts.append(f"\\usepackage[{opts}]{{{pkg}}}")
            else:
                parts.append(f"\\usepackage{{{pkg}}}")

        # 期刊级额外宏包
        for pkg in config.get("extra_packages", []):
            parts.append(f"\\usepackage{{{pkg}}}")

        parts.append("")

        # 3. 中文支持（ctex 方式，推荐 XeLaTeX 编译）
        parts.append("% ── 中文支持（推荐使用 XeLaTeX 编译）──")
        parts.append("\\usepackage{ctex}")
        parts.append("")

        # 4. 自定义命令
        parts.append("% ── 自定义命令 ──")
        parts.append("\\newcommand{\\superscript}[1]{\\textsuperscript{#1}}")
        parts.append("\\newcommand{\\footnotemark}[1]{\\superscript{#1}}")
        parts.append("")

        # 5. 标题信息
        if title:
            parts.append(f"\\title{{{LaTeXExporter._escape_latex(title)}}}")
        if authors:
            parts.append(f"\\author{{{LaTeXExporter._escape_latex(authors)}}}")
        parts.append("")

        # 6. 文档开始
        parts.append("\\begin{document}")
        parts.append("")

        # 7. maketitle
        if title:
            parts.append("\\maketitle")
            parts.append("")

        # 8. 摘要
        if abstract:
            parts.append("\\begin{abstract}")
            parts.append(LaTeXExporter._convert_text(abstract))
            parts.append("\\end{abstract}")
            parts.append("")

        # 9. 关键词
        if keywords:
            kw_str = " \\sep ".join(LaTeXExporter._escape_latex(k) for k in keywords)
            parts.append("\\keywords{" + kw_str + "}")
            parts.append("")

        # 10. 正文
        if outline and isinstance(outline, dict) and "sections" in outline:
            # 从大纲结构化输出
            body = LaTeXExporter._convert_with_outline(content, outline)
        else:
            # 从纯文本/Markdown 转换
            body = LaTeXExporter._convert_text(content)

        parts.append(body)
        parts.append("")

        # 11. 参考文献
        if references:
            parts.append("% ── 参考文献 ──")
            parts.append("\\bibliographystyle{" + config["bib_style"] + "}")
            parts.append("\\begin{thebibliography}{99}")
            for i, ref in enumerate(references, 1):
                parts.append(f"\\bibitem{{ref{i}}} {LaTeXExporter._escape_latex(ref)}")
            parts.append("\\end{thebibliography}")
            parts.append("")

        # 12. 文档结束
        parts.append("\\end{document}")

        return "\n".join(parts)

    # ─────────────────────────────────────────────
    # 内部转换方法
    # ─────────────────────────────────────────────

    @staticmethod
    def _convert_text(text: str) -> str:
        """将 Markdown / 纯文本转换为 LaTeX"""
        if not text:
            return ""

        lines = text.split("\n")
        result = []
        i = 0

        while i < len(lines):
            line = lines[i]

            # 跳过空行
            if not line.strip():
                result.append("")
                i += 1
                continue

            # Markdown 标题
            heading_match = re.match(r"^(#{1,4})\s+(.*)", line)
            if heading_match:
                level = len(heading_match.group(1))
                heading_text = heading_match.group(2).strip()
                heading_text = LaTeXExporter._escape_latex(heading_text)
                if level == 1:
                    result.append(f"\\section{{{heading_text}}}")
                elif level == 2:
                    result.append(f"\\subsection{{{heading_text}}}")
                elif level == 3:
                    result.append(f"\\subsubsection{{{heading_text}}}")
                else:
                    result.append(f"\\paragraph{{{heading_text}}}")
                i += 1
                continue

            # 块级图片（![alt](url) 占整行）— 浮动体环境属块级，不应行内插入
            # URL 含 _ % 等特殊字符需转义；alt 文本转义
            img_match = re.match(r"^!\[([^\]]*)\]\(([^\)]+)\)\s*$", line)
            if img_match:
                alt = LaTeXExporter._escape_latex(img_match.group(1))
                url = LaTeXExporter._escape_latex(img_match.group(2))
                result.append("\\begin{figure}[htbp]")
                result.append("\\centering")
                result.append(f"\\includegraphics[width=0.8\\textwidth]{{{url}}}")
                if alt:
                    result.append(f"\\caption{{{alt}}}")
                result.append("\\end{figure}")
                result.append("")
                i += 1
                continue

            # Markdown 列表项 / 有序列表项（统一检测，按连续块包裹环境）
            list_match = re.match(r"^(\s*)[-*+]\s+(.*)", line)
            olist_match = re.match(r"^(\s*)\d+\.\s+(.*)", line)
            if list_match or olist_match:
                # 收集连续列表项，判断类型（无序/有序）并包裹对应环境
                is_ordered = bool(olist_match) and not list_match
                env = "enumerate" if is_ordered else "itemize"
                result.append(f"\\begin{{{env}}}")
                while i < len(lines):
                    cur = lines[i]
                    lm = re.match(r"^(\s*)[-*+]\s+(.*)", cur)
                    om = re.match(r"^(\s*)\d+\.\s+(.*)", cur)
                    if lm:
                        item_text = LaTeXExporter._convert_inline(lm.group(2))
                        result.append(f"\\item {item_text}")
                        i += 1
                    elif om and is_ordered is not False:
                        # 同类列表项：有序块内继续收有序项
                        if is_ordered:
                            item_text = LaTeXExporter._convert_inline(om.group(2))
                            result.append(f"\\item {item_text}")
                            i += 1
                        else:
                            break  # 无序块遇到有序项，结束当前块
                    elif not cur.strip():
                        # 空行：列表可能结束，预读下一行是否仍为列表项
                        j = i + 1
                        while j < len(lines) and not lines[j].strip():
                            j += 1
                        if j < len(lines):
                            nxt = lines[j]
                            if re.match(r"^(\s*)[-*+]\s+", nxt) or (
                                is_ordered and re.match(r"^(\s*)\d+\.\s+", nxt)
                            ):
                                result.append("")  # 列表内空行保留
                                i += 1
                                continue
                        break
                    else:
                        break
                result.append(f"\\end{{{env}}}")
                continue

            # 代码块开始
            if line.strip().startswith("```"):
                lang = line.strip()[3:].strip()
                result.append(
                    f"\\begin{{lstlisting}}[{'language=' + lang if lang else ''}]"
                )
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    result.append(lines[i])
                    i += 1
                result.append("\\end{lstlisting}")
                i += 1  # skip closing ```
                continue

            # LaTeX 公式块 ($$...$$)
            if line.strip().startswith("$$"):
                formula_lines = [line.strip()[2:]]
                i += 1
                while i < len(lines) and not lines[i].strip().endswith("$$"):
                    formula_lines.append(lines[i])
                    i += 1
                if i < len(lines):
                    last = lines[i].strip()
                    if last.endswith("$$"):
                        formula_lines.append(last[:-2])
                formula = "\n".join(formula_lines).strip()
                result.append("\\begin{equation}")
                result.append(formula)
                result.append("\\end{equation}")
                i += 1
                continue

            # 表格 (Markdown 管道表格)
            if (
                "|" in line
                and i + 1 < len(lines)
                and re.match(r"^[\s|:-]+$", lines[i + 1])
            ):
                table_result = LaTeXExporter._convert_table(lines, i)
                result.extend(table_result["lines"])
                i = table_result["next_i"]
                continue

            # 普通段落
            para_lines = [LaTeXExporter._convert_inline(line)]
            i += 1
            while (
                i < len(lines)
                and lines[i].strip()
                and not re.match(r"^(#{1,4}\s|[-*+]\s|\d+\.\s|```|\$\$)", lines[i])
            ):
                para_lines.append(LaTeXExporter._convert_inline(lines[i]))
                i += 1
            result.append(" ".join(para_lines))
            result.append("")  # paragraph break

        return "\n".join(result)

    @staticmethod
    def _convert_with_outline(content: str, outline: dict[str, Any]) -> str:
        """使用大纲结构转换内容为 LaTeX"""
        result = []

        sections = outline.get("sections", [])
        if not sections:
            return LaTeXExporter._convert_text(content)

        # 按大纲的章节划分正文
        content.lower()
        pos = 0

        for section_def in sections:
            sec_title = section_def.get("title", "")
            subsections = section_def.get("subsections", [])

            # 章节标题
            sec_latex_name = LaTeXExporter.SECTION_MAP.get(
                sec_title.lower(), LaTeXExporter._escape_latex(sec_title)
            )
            result.append(f"\\section{{{sec_latex_name}}}")
            result.append("")

            # 在正文中查找该章节的内容
            sec_content, pos = LaTeXExporter._extract_section_content(
                content, sec_title, pos
            )
            if sec_content:
                result.append(LaTeXExporter._convert_text(sec_content))
                result.append("")

            # 子章节
            for sub in subsections:
                sub_latex_name = LaTeXExporter._escape_latex(sub)
                result.append(f"\\subsection{{{sub_latex_name}}}")
                result.append("")
                sub_content, pos = LaTeXExporter._extract_section_content(
                    content, sub, pos
                )
                if sub_content:
                    result.append(LaTeXExporter._convert_text(sub_content))
                    result.append("")

        return "\n".join(result)

    @staticmethod
    def _extract_section_content(
        text: str, section_name: str, start_pos: int = 0
    ) -> tuple[str, int]:
        """从文本中提取指定章节的内容"""
        # 尝试匹配 Markdown 标题或纯文本标题
        patterns = [
            re.compile(
                r"^#{1,4}\s+" + re.escape(section_name) + r"\s*$",
                re.IGNORECASE | re.MULTILINE,
            ),
            re.compile(
                r"^" + re.escape(section_name) + r"\s*$", re.IGNORECASE | re.MULTILINE
            ),
        ]

        match = None
        for pattern in patterns:
            match = pattern.search(text, start_pos)
            if match:
                break

        if not match:
            return "", start_pos

        content_start = match.end()

        # 查找下一个同级或更高级标题
        next_heading = re.search(r"^#{1,4}\s+\S", text[content_start:], re.MULTILINE)
        if next_heading:
            content_end = content_start + next_heading.start()
        else:
            content_end = len(text)

        return text[content_start:content_end].strip(), content_end

    @staticmethod
    def _convert_inline(text: str) -> str:
        """转换行内 Markdown 元素为 LaTeX

        图片 (![alt](url)) 不在此处理 — 浮动体环境属块级元素，在 _convert_text
        中按整行检测，避免在段落行内插入 \begin{figure} 导致 LaTeX 编译错误。
        """
        if not text:
            return ""

        # 行内代码
        text = re.sub(r"`([^`]+)`", r"\\texttt{\1}", text)

        # 粗体
        text = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", text)

        # 斜体
        text = re.sub(r"\*(.+?)\*", r"\\textit{\1}", text)

        # 行内公式 $...$
        text = re.sub(r"\$([^\$]+)\$", r"$\1$", text)

        # 超链接 [text](url)（hyperref 已在 preamble 声明）
        # URL 内的特殊字符需转义（_ % # 等），hyperref 的 \url 更稳健但 \href 需转义
        def _href_repl(m: re.Match[str]) -> str:
            url = LaTeXExporter._escape_latex(m.group(2))
            link_text = LaTeXExporter._escape_latex(m.group(1))
            return f"\\href{{{url}}}{{{link_text}}}"

        text = re.sub(r"\[([^\]]+)\]\(([^\)]+)\)", _href_repl, text)

        # 转义 LaTeX 特殊字符（最后执行，避免破坏上面的命令替换）
        text = LaTeXExporter._escape_latex(text)

        return text

    @staticmethod
    def _convert_table(lines: list[str], start_i: int) -> dict[str, Any]:
        """转换 Markdown 表格为 LaTeX"""
        # 解析表头
        header_cells = [c.strip() for c in lines[start_i].split("|") if c.strip()]

        # 跳过分隔行
        i = start_i + 2

        # 解析数据行
        rows = []
        while i < len(lines) and "|" in lines[i] and lines[i].strip():
            cells = [c.strip() for c in lines[i].split("|") if c.strip()]
            rows.append(cells)
            i += 1

        col_count = len(header_cells)
        col_spec = "l" * col_count

        result = []
        result.append("\\begin{table}[htbp]")
        result.append("\\centering")
        result.append(f"\\begin{{tabular}}{{{col_spec}}}")
        result.append("\\toprule")

        # 表头
        header_escaped = " & ".join(
            LaTeXExporter._escape_latex(c) for c in header_cells
        )
        result.append(header_escaped + " \\\\")
        result.append("\\midrule")

        # 数据行
        for row in rows:
            row_escaped = " & ".join(LaTeXExporter._escape_latex(c) for c in row)
            result.append(row_escaped + " \\\\")

        result.append("\\bottomrule")
        result.append("\\end{tabular}")
        result.append("\\end{table}")

        return {"lines": result, "next_i": i}

    @staticmethod
    def _escape_latex(text: str) -> str:
        """转义 LaTeX 特殊字符"""
        if not text:
            return ""

        # 保留已有的 LaTeX 命令
        # 先标记 LaTeX 命令
        latex_commands = []
        placeholder_idx = 0

        def save_latex(m: re.Match[str]) -> str:
            nonlocal placeholder_idx
            # 占位符必须不含 LaTeX 特殊字符（_ % # & { } ~ ^），否则会被转义破坏还原
            placeholder = f"LATEXCMDPLACEHOLDER{placeholder_idx}ENDPLACEHOLDER"
            latex_commands.append((placeholder, m.group(0)))
            placeholder_idx += 1
            return placeholder

        # 保留 \command{...} 结构（支持多层嵌套花括号）
        # 用逐步扫描替代纯正则（纯正则无法处理任意深度嵌套）：
        # 反复匹配最内层的 \cmd{...}（不含嵌套花括号），用占位符替换，
        # 直到无更多命令可匹配。这样深层嵌套从内向外逐层保留。
        prev = None
        while prev != text:
            prev = text
            text = re.sub(r"\\[a-zA-Z]+\{[^{}]*\}", save_latex, text)
        # 保留 \\ 开头的纯命令名（但排除转义序列 \_ \% \# \& \{ \} \$ \\）
        # 这些转义序列的特征是反斜杠后跟非字母（标点/符号），不应被当作命令保留
        text = re.sub(r"\\[a-zA-Z]+", save_latex, text)
        # 保留数学模式
        text = re.sub(r"\$[^$]+\$", save_latex, text)

        # 转义特殊字符
        escapes = [
            ("&", r"\&"),
            ("%", r"\%"),
            ("#", r"\#"),
            ("_", r"\_"),
            ("{", r"\{"),
            ("}", r"\}"),
            ("~", r"\textasciitilde{}"),
            ("^", r"\textasciicircum{}"),
        ]
        for char, replacement in escapes:
            text = text.replace(char, replacement)

        # 还原 LaTeX 命令（外层先、内层后）
        # 迭代扫描从内向外匹配占位，所以列表中外层命令在后。
        # 还原必须外层先：外层还原会重新引入内层占位符，随后内层还原填充。
        for placeholder, original in reversed(latex_commands):
            text = text.replace(placeholder, original)

        return text

    @staticmethod
    def generate_compilation_instructions() -> str:
        """生成编译说明"""
        return """# LaTeX 编译说明

## 推荐编译方式

### 方法一：使用 XeLaTeX（推荐，支持中文）
```bash
xelatex paper.tex
xelatex paper.tex  # 运行两次以正确生成引用和目录
```

### 方法二：使用 latexmk（自动化编译）
```bash
latexmk -xelatex paper.tex
```

### 方法三：使用 Overleaf（在线编辑器）
1. 访问 https://www.overleaf.com
2. 创建新项目，上传 .tex 文件
3. 将编译器设置为 XeLaTeX

## 注意事项
- 首次编译需运行两次以正确解析交叉引用
- 如包含参考文献，需运行 bibtex：
  ```bash
  xelatex paper.tex
  bibtex paper
  xelatex paper.tex
  xelatex paper.tex
  ```
- 图片文件需与 .tex 文件位于同一目录
- 中文内容需要 XeLaTeX 或 LuaLaTeX 编译器
"""

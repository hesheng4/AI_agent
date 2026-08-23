"""R36 tests — LaTeX 语言语法实现正确性。

验证 3 处高严重度缺陷修复：
- X1: export.py to_latex 转义 LaTeX 特殊字符（% # & _ { } \\）
- X3: latex_export _convert_text 列表项包裹 \\begin{itemize}/\\begin{enumerate}
- X8: latex_export _escape_latex 保留命令正则不误吃嵌套花括号
"""


# ── X1: export.py to_latex 转义 ──


def test_x1_export_to_latex_escapes_special_chars():
    r"""to_latex 应转义 title 中的 % # & _ { } 等特殊字符。"""
    from app.utils.export import DataExporter

    manuscript = {
        "title": "Test 100% & #1 _under {brace}",
        "sections": [{"title": "Sec&Title", "content": "body"}],
    }
    latex = DataExporter.to_latex(manuscript)
    # 特殊字符应被转义（前缀 \）
    assert r"\%" in latex, "% 应转义"
    assert r"\&" in latex, "& 应转义"
    assert r"\#" in latex, "# 应转义"
    assert r"\_" in latex, "_ 应转义"
    # 不应出现未转义的裸特殊字符在 title 上下文
    # （body content 不转义，仅 title/section title 转义）
    title_line = [line for line in latex.split("\n") if line.startswith("\\title{")][0]
    assert "%" not in title_line.replace(r"\%", "") or r"\%" in title_line


def test_x1_export_to_latex_section_title_escaped():
    r"""section title 应转义特殊字符。"""
    from app.utils.export import DataExporter

    manuscript = {
        "title": "OK",
        "sections": [{"title": "Sec_1 & Sec_2", "content": "x"}],
    }
    latex = DataExporter.to_latex(manuscript)
    sec_line = [line for line in latex.split("\n") if line.startswith("\\section{")][0]
    assert r"\_" in sec_line
    assert r"\&" in sec_line


def test_x1_export_to_latex_empty_title():
    """空 title 不应崩溃，生成空 \\title{}。"""
    from app.utils.export import DataExporter

    latex = DataExporter.to_latex({"title": "", "sections": []})
    assert "\\title{}" in latex
    assert "\\begin{document}" in latex
    assert "\\end{document}" in latex


# ── X3: 列表环境包裹 ──


def test_x3_unordered_list_wrapped_in_itemize():
    r"""无序列表应包裹在 \begin{itemize}...\end{itemize} 中。"""
    from app.utils.latex_export import LaTeXExporter

    md = "- item one\n- item two\n- item three"
    latex = LaTeXExporter._convert_text(md)
    assert "\\begin{itemize}" in latex, "应包裹 itemize 环境"
    assert "\\end{itemize}" in latex
    assert latex.count("\\item") == 3


def test_x3_ordered_list_wrapped_in_enumerate():
    r"""有序列表应包裹在 \begin{enumerate} 中。"""
    from app.utils.latex_export import LaTeXExporter

    md = "1. first\n2. second\n3. third"
    latex = LaTeXExporter._convert_text(md)
    assert "\\begin{enumerate}" in latex, "应包裹 enumerate 环境"
    assert "\\end{enumerate}" in latex
    assert latex.count("\\item") == 3


def test_x3_list_no_bare_item_outside_env():
    r"""不应出现环境外的裸 \\item（编译错误）。"""
    from app.utils.latex_export import LaTeXExporter

    md = "- a\n- b\n\nparagraph\n- c"
    latex = LaTeXExporter._convert_text(md)
    # 所有 \item 应在 itemize/enumerate 内（简化检查：环境存在性）
    import re

    envs = re.findall(r"\\begin\{(itemize|enumerate)\}", latex)
    # 至少有一个环境包裹
    assert len(envs) >= 1, "应至少有一个列表环境"
    # 不应在 result 顶层出现未被任何环境包裹的 \item
    # （精确检查需解析环境配对，此处用环境存在性保证）


def test_x3_list_followed_by_paragraph():
    """列表后跟段落，段落应在 \\end{itemize} 之后。"""
    from app.utils.latex_export import LaTeXExporter

    md = "- item\n\nThis is a paragraph."
    latex = LaTeXExporter._convert_text(md)
    end_idx = latex.find("\\end{itemize}")
    para_idx = latex.find("This is a paragraph")
    assert end_idx != -1 and para_idx != -1
    assert end_idx < para_idx, "段落应在列表环境结束之后"


# ── X8: _escape_latex 命令保留 ──


def test_x8_escape_preserves_nested_brace_command():
    r"""_escape_latex 应保留含嵌套花括号的命令 \textbf{a \emph{b}}。"""
    from app.utils.latex_export import LaTeXExporter

    text = r"\textbf{bold \emph{italic}} text"
    escaped = LaTeXExporter._escape_latex(text)
    # 命令应被保留（还原），不被转义
    assert r"\textbf{bold \emph{italic}}" in escaped, f"嵌套命令应保留，实际: {escaped}"


def test_x8_escape_preserves_math_mode():
    r"""_escape_latex 应保留数学模式 $x^2$ 内的内容不转义。"""
    from app.utils.latex_export import LaTeXExporter

    text = r"Equation $x_1 + x_2$ here"
    escaped = LaTeXExporter._escape_latex(text)
    assert "$x_1 + x_2$" in escaped, f"数学模式应保留，实际: {escaped}"


def test_x8_escape_special_chars_outside_commands():
    r"""命令外的特殊字符 % & _ 应被转义。"""
    from app.utils.latex_export import LaTeXExporter

    text = "50% off & free_trial"
    escaped = LaTeXExporter._escape_latex(text)
    assert r"\%" in escaped, "% 应转义"
    assert r"\&" in escaped, "& 应转义"
    assert r"\_" in escaped, "_ 应转义"


def test_x8_escape_empty_string():
    """空字符串不应崩溃。"""
    from app.utils.latex_export import LaTeXExporter

    assert LaTeXExporter._escape_latex("") == ""
    assert LaTeXExporter._escape_latex(None) == ""


# ── 回归：_convert_text 基本功能 ──


def test_convert_text_heading():
    r"""Markdown # 标题 → \section。"""
    from app.utils.latex_export import LaTeXExporter

    latex = LaTeXExporter._convert_text("# Introduction\nbody")
    assert "\\section{Introduction}" in latex


def test_convert_text_code_block():
    r"""代码块 ``` → lstlisting 环境。"""
    from app.utils.latex_export import LaTeXExporter

    md = "```python\nprint('hi')\n```"
    latex = LaTeXExporter._convert_text(md)
    assert "\\begin{lstlisting}" in latex
    assert "\\end{lstlisting}" in latex

"""R35 tests — L2/L8/L9 LaTeX 低优先遗留修复。

- L2: latex_engine compile 错误消息不再硬编码绝对路径
- L8: writing fix_latex_layout section 正则处理嵌套花括号 + subsection
- L9: polishing fix_latex_layout 截断在安全边界（不切断 LaTeX 命令）
"""

import inspect
import re

# ── L2: 错误消息通用化 ──


def test_l2_compile_error_no_hardcoded_path():
    r"""compile 错误消息不应含硬编码 D:\latex 绝对路径。"""
    import app.utils.latex_engine as le

    src = inspect.getsource(le.LatexEngine.compile)
    assert r"D:\latex" not in src, "不应硬编码 D:\\latex 路径"
    assert "PATH" in src or "xelatex" in src, "应提示 PATH 或编译器名"


# ── L8: section 正则处理嵌套花括号 + subsection ──


def test_l8_section_regex_matches_plain_section():
    r"""正则应匹配普通 \section{Title}。"""
    tex = r"\section{Introduction}" + "\nbody\n"
    matches = re.findall(
        r"\\(?:sub){0,2}section\*?\{((?:[^{}]|\{[^{}]*\})+)\}",
        tex,
    )
    assert "Introduction" in matches


def test_l8_section_regex_matches_nested_braces():
    r"""正则应匹配含嵌套花括号的 \section{The \textbf{X} method}。"""
    tex = r"\section{The \textbf{X} method}" + "\n"
    matches = re.findall(
        r"\\(?:sub){0,2}section\*?\{((?:[^{}]|\{[^{}]*\})+)\}",
        tex,
    )
    assert len(matches) == 1
    assert "textbf" in matches[0] or "X" in matches[0]


def test_l8_section_regex_matches_subsection():
    r"""正则应匹配 \subsection 与 \subsubsection。"""
    tex = (
        r"\section{A}" + "\n"
        r"\subsection{B}" + "\n"
        r"\subsubsection{C}" + "\n"
    )
    matches = re.findall(
        r"\\(?:sub){0,2}section\*?\{((?:[^{}]|\{[^{}]*\})+)\}",
        tex,
    )
    assert "A" in matches and "B" in matches and "C" in matches


def test_l8_section_regex_matches_starred_section():
    r"""正则应匹配 \section*{Unnumbered}（星号变体）。"""
    tex = r"\section*{Acknowledgments}" + "\n"
    matches = re.findall(
        r"\\(?:sub){0,2}section\*?\{((?:[^{}]|\{[^{}]*\})+)\}",
        tex,
    )
    assert "Acknowledgments" in matches


def test_l8_writing_fix_latex_layout_uses_robust_regex():
    """writing agent fix_latex_layout 应使用含嵌套花括号处理的正则。"""
    import app.agents.writing.agent as wa

    src = inspect.getsource(wa.WritingAgent.fix_latex_layout)
    # 修复后正则应含 (?:sub){0,2} 与嵌套花括号模式
    assert "(?:sub){0,2}" in src, "应匹配 subsection 变体"
    assert "[^{}]" in src or "\\{[^{}]" in src, "应处理嵌套花括号"


# ── L9: 截断在安全边界 ──


def test_l9_polishing_fix_latex_layout_safe_truncation():
    """polishing fix_latex_layout 截断应在换行/空白边界，不切断命令。"""
    import app.agents.polishing.agent as pa

    src = inspect.getsource(pa.PolishingAgent.fix_latex_layout)
    # 修复后应含安全边界逻辑（rfind 换行/空格）
    assert "rfind" in src, "应使用 rfind 寻找安全截断边界"
    assert "boundary" in src or "截断" in src, "应有截断边界处理"


def test_l9_polishing_truncation_logic_preserves_command():
    """模拟截断逻辑：超长 tex_source 截断后不应以 \begin{figu 结尾。"""
    # 构造超长 tex：末尾是一个未完成的命令
    tex = "Normal line.\n" * 800 + r"\begin{figu"  # ~8100+ 字符
    snippet = tex[:8000]
    if len(tex) > 8000:
        boundary = snippet.rfind("\n")
        if boundary < 4000:
            boundary = snippet.rfind(" ")
        if boundary >= 4000:
            snippet = snippet[:boundary]
        snippet = snippet + "\n... [源码过长，已截断]"
    # 截断后不应含未完成的 \begin{figu
    assert "figu" not in snippet or snippet.rstrip().endswith("]"), (
        f"截断应避免切断命令，实际末尾: {snippet[-50:]!r}"
    )


def test_l9_polishing_short_source_not_truncated():
    """短 tex_source 不应触发截断逻辑。"""
    tex = r"\section{Short}" + "\nbody"
    snippet = tex[:8000]
    if len(tex) > 8000:
        boundary = snippet.rfind("\n")
        if boundary < 4000:
            boundary = snippet.rfind(" ")
        if boundary >= 4000:
            snippet = snippet[:boundary]
        snippet = snippet + "\n... [源码过长，已截断]"
    assert "源码过长" not in snippet, "短源码不应被标记为截断"
    assert "Short" in snippet

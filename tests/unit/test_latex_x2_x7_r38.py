"""R38 tests — X2/X7 LaTeX 最后低优先遗留。

- X2: len() 死代码已移除（R37 X3 重构副作用，本测试确认）
- X7: _escape_latex 保留命令支持多层嵌套花括号
"""

import inspect

# ── X2: 死代码移除确认 ──


def test_x2_no_dead_len_in_convert_text():
    r"""_convert_text 不应含无效果的 len(list_match.group(1)) 死代码。"""
    from app.utils.latex_export import LaTeXExporter

    src = inspect.getsource(LaTeXExporter._convert_text)
    # 不应出现 len(list_match.group(1)) 作为独立语句（死代码）
    assert "len(list_match.group(1))\n" not in src, (
        "不应含 len(list_match.group(1)) 死代码"
    )


# ── X7: 多层嵌套花括号保留 ──


def test_x7_preserves_single_level_command():
    r"""单层命令 \textbf{bold} 应保留。"""
    from app.utils.latex_export import LaTeXExporter

    escaped = LaTeXExporter._escape_latex(r"\textbf{bold} text")
    assert r"\textbf{bold}" in escaped


def test_x7_preserves_two_level_nested():
    r"""两层嵌套 \textbf{a \emph{b}} 应完整保留。"""
    from app.utils.latex_export import LaTeXExporter

    escaped = LaTeXExporter._escape_latex(r"\textbf{a \emph{b}} text")
    assert r"\textbf{a \emph{b}}" in escaped, f"两层嵌套应保留，实际: {escaped}"


def test_x7_preserves_three_level_nested():
    r"""三层嵌套 \textbf{a \emph{b \textbf{c}}} 应完整保留。"""
    from app.utils.latex_export import LaTeXExporter

    escaped = LaTeXExporter._escape_latex(r"\textbf{a \emph{b \textbf{c}}} text")
    assert r"\textbf{a \emph{b \textbf{c}}}" in escaped, (
        f"三层嵌套应保留，实际: {escaped}"
    )


def test_x7_preserves_math_mode_still():
    r"""数学模式 $x_1$ 应保留（X7 修复不应破坏数学模式）。"""
    from app.utils.latex_export import LaTeXExporter

    escaped = LaTeXExporter._escape_latex(r"Eq $x_1 + x_2$ end")
    assert "$x_1 + x_2$" in escaped


def test_x7_escapes_special_chars_outside_commands():
    r"""命令外的特殊字符仍应转义（X7 修复不应破坏转义）。"""
    from app.utils.latex_export import LaTeXExporter

    escaped = LaTeXExporter._escape_latex(r"50% \textbf{bold} & more")
    assert r"\%" in escaped, "% 应转义"
    assert r"\&" in escaped, "& 应转义"
    assert r"\textbf{bold}" in escaped, "命令应保留"


def test_x7_mixed_nested_and_special():
    r"""混合场景：嵌套命令 + 特殊字符。"""
    from app.utils.latex_export import LaTeXExporter

    escaped = LaTeXExporter._escape_latex(r"\textbf{a_b} & 50%")
    assert r"\textbf{a_b}" in escaped, "含 _ 的命令应保留（_ 在命令内不转义）"
    assert r"\&" in escaped
    assert r"\%" in escaped

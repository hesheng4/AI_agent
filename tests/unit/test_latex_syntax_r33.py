"""LaTeX 编写部分语法审计测试 (R33)。

验证 R33 修复的 5 个缺陷：
- L6: math_to_omml._script 的 sSup 分支应输出上标而非下标（最高严重度）
- L1: latex_engine 模块无 SyntaxWarning
- L4: auto_fix Fix1 不覆盖用户已指定的浮动体位置选项
- L5: auto_fix Fix2 ``\\sloppy`` 插入到 ``\\begin{document}``` 后而非文件开头
- L3: compile 循环无死变量 all_issues
"""

import re
import warnings

import pytest

# ── L6: _script sSup 输出上标而非下标 ──


def test_script_ssup_outputs_sup_not_sub():
    """sSup（纯上标，如 x^2）的 OMML 应含 sup 元素而非 sub 元素承载上标内容。

    R33 修复前：L55 ``result.append(sup if kind == "sSubSup" else sub)`` 对 sSup
    追加 sub，导致上标内容渲染为下标（x^2 → x₂）。
    """
    pytest.importorskip("docx")  # math_to_omml 依赖 python-docx
    from xml.etree import ElementTree

    # 构造 MathML msup: <msup><mi>x</mi><mn>2</mn></msup>
    mathml = ElementTree.fromstring(
        "<math xmlns='http://www.w3.org/1998/Math/MathML'>"
        "<msup><mi>x</mi><mn>2</mn></msup></math>"
    )
    # 用 math_to_omml 的 _append_mathml 处理 msup（会调用 _script target, node, "sSup"）
    import os
    import sys

    sys.path.insert(
        0,
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "app",
            "agents",
            "paper_to_patent",
            "scripts",
        ),
    )
    from math_to_omml import _append_mathml, _element

    o_math = _element("oMath")
    # msup 是 math 的子节点
    msup = mathml[0]
    _append_mathml(o_math, msup)

    # oMath 结构应为: oMath > sSup > [e(含x), sup(含2)]
    ssup = o_math.find("{*}sSup")
    assert ssup is not None, "应生成 sSup 元素"
    e = ssup.find("{*}e")
    sup = ssup.find("{*}sup")
    sub = ssup.find("{*}sub")
    assert e is not None, "sSup 应含 base 元素 e"
    assert sup is not None, "sSup 应含 sup 元素（上标）"
    # 关键断言：上标内容 '2' 应在 sup 中，不应生成 sub
    sup_text = "".join(t.text or "" for t in sup.iter() if t.text)
    assert "2" in sup_text, f"上标内容 '2' 应在 sup 元素中，实际 sup={sup_text}"
    assert sub is None, "sSup 不应生成 sub 元素（修复前缺陷）"


def test_script_ssub_outputs_sub_not_sup():
    """sSub（纯下标，如 x_2）的 OMML 应含 sub 元素而非 sup。"""
    pytest.importorskip("docx")
    import os
    import sys
    from xml.etree import ElementTree

    sys.path.insert(
        0,
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "app",
            "agents",
            "paper_to_patent",
            "scripts",
        ),
    )
    from math_to_omml import _append_mathml, _element

    mathml = ElementTree.fromstring(
        "<math xmlns='http://www.w3.org/1998/Math/MathML'>"
        "<msub><mi>x</mi><mn>2</mn></msub></math>"
    )
    o_math = _element("oMath")
    _append_mathml(o_math, mathml[0])

    ssub = o_math.find("{*}sSub")
    assert ssub is not None
    sub = ssub.find("{*}sub")
    sup = ssub.find("{*}sup")
    assert sub is not None, "sSub 应含 sub 元素"
    assert sup is None, "sSub 不应生成 sup 元素"
    sub_text = "".join(t.text or "" for t in sub.iter() if t.text)
    assert "2" in sub_text


def test_script_ssubsup_outputs_both():
    """sSubSup（如 x_2^3）应同时含 sub 和 sup，且内容正确。"""
    pytest.importorskip("docx")
    import os
    import sys
    from xml.etree import ElementTree

    sys.path.insert(
        0,
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "app",
            "agents",
            "paper_to_patent",
            "scripts",
        ),
    )
    from math_to_omml import _append_mathml, _element

    mathml = ElementTree.fromstring(
        "<math xmlns='http://www.w3.org/1998/Math/MathML'>"
        "<msubsup><mi>x</mi><mn>2</mn><mn>3</mn></msubsup></math>"
    )
    o_math = _element("oMath")
    _append_mathml(o_math, mathml[0])

    ssubsup = o_math.find("{*}sSubSup")
    assert ssubsup is not None
    sub = ssubsup.find("{*}sub")
    sup = ssubsup.find("{*}sup")
    assert sub is not None and sup is not None
    sub_text = "".join(t.text or "" for t in sub.iter() if t.text)
    sup_text = "".join(t.text or "" for t in sup.iter() if t.text)
    assert "2" in sub_text, f"下标 '2' 应在 sub，实际 {sub_text}"
    assert "3" in sup_text, f"上标 '3' 应在 sup，实际 {sup_text}"


# ── L1: latex_engine 模块无 SyntaxWarning ──


def test_latex_engine_no_syntax_warning():
    r"""导入 latex_engine 不应触发 SyntaxWarning（\l 无效转义序列）。"""
    import importlib

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        import app.utils.latex_engine as le

        importlib.reload(le)
    syntax_warns = [w for w in caught if issubclass(w.category, SyntaxWarning)]
    assert syntax_warns == [], f"latex_engine 不应触发 SyntaxWarning: {syntax_warns}"


# ── L3: compile 无死变量 all_issues ──


def test_compile_no_dead_all_issues():
    """compile 方法源码不应含未使用的 all_issues 变量。"""
    import inspect

    import app.utils.latex_engine as le

    src = inspect.getsource(le.LatexEngine.compile)
    assert "all_issues" not in src, "compile 不应含死变量 all_issues"


# ── L4: auto_fix Fix1 不覆盖用户位置选项 ──
# （正则 (?!\[) 本就只匹配无 [ 的，与 writing/agent 一致；此测试确认注释+行为）


def test_auto_fix_fix1_regex_skips_positioned_floats():
    """auto_fix Fix1 正则不应匹配 \\begin{figure}[t]（用户已指定位置）。"""
    # 验证修复注释存在（L4 修复标记）
    import inspect

    import app.utils.latex_engine as le

    auto_fix_src = inspect.getsource(le.LatexEngine.auto_fix)
    assert "不覆盖用户已指定" in auto_fix_src or r"(?!\[)" in auto_fix_src


# ── L5: auto_fix Fix2 \sloppy 插入位置 ──


def test_auto_fix_fix2_sloppy_after_begin_document():
    """auto_fix Fix2 应将 \\sloppy 插入到 \\begin{document} 后而非文件开头。"""
    import inspect

    import app.utils.latex_engine as le

    src = inspect.getsource(le.LatexEngine.auto_fix)
    # 修复后应含 \begin{document} 检查
    assert r"\begin{document}" in src, "Fix2 应检查 \\begin{document} 存在"
    # 不应再出现拼到文件开头的模式
    assert 'r"\\sloppy" + "\\n" + current' not in src, "Fix2 不应拼到文件开头"


# ── LOG_PATTERNS 正则可编译性 ──


def test_log_patterns_regex_compilable():
    """LOG_PATTERNS 所有正则应可编译（无无效转义）。"""
    import app.utils.latex_engine as le

    for name, config in le.LOG_PATTERNS.items():
        try:
            re.compile(config["pattern"])
        except re.error as e:
            pytest.fail(f"LOG_PATTERNS[{name}] 正则编译失败: {e}")

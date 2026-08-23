#!/usr/bin/env python3
"""Convert a LaTeX equation into editable Word Office Math (OMML)."""

from copy import deepcopy
from xml.etree import ElementTree

from docx.oxml import OxmlElement
from docx.oxml.ns import qn

MATHML_NS = "{http://www.w3.org/1998/Math/MathML}"


def _element(name: str):
    return OxmlElement(f"m:{name}")


def _text_run(text: str):
    run = _element("r")
    properties = _element("rPr")
    style = _element("sty")
    style.set(qn("m:val"), "p")
    properties.append(style)
    run.append(properties)
    value = _element("t")
    value.text = text
    run.append(value)
    return run


def _append_children(target, source) -> None:
    if source.text and source.text.strip():
        target.append(_text_run(source.text.strip()))
    for child in source:
        _append_mathml(target, child)
        if child.tail and child.tail.strip():
            target.append(_text_run(child.tail.strip()))


def _script(target, node, kind: str) -> None:
    """生成 OMML sSub/sSup/sSubSup 元素。

    MathML 子节点顺序：
    - msub/msup: [base, script]（2 子节点，script 是下标或上标）
    - msubsup: [base, sub_script, super_script]（3 子节点）
    按 kind 将对应子节点放入 sub/sup 元素，避免变量名误导导致内容错位。
    """
    result = _element(kind)
    expression = _element("e")
    sub = _element("sub")
    sup = _element("sup")
    children = list(node)
    if children:
        _append_mathml(expression, children[0])
    if kind == "sSub":
        # msub: children[1] 是下标
        if len(children) > 1:
            _append_mathml(sub, children[1])
    elif kind == "sSup":
        # msup: children[1] 是上标
        if len(children) > 1:
            _append_mathml(sup, children[1])
    else:  # sSubSup: msubsup
        if len(children) > 1:
            _append_mathml(sub, children[1])
        if len(children) > 2:
            _append_mathml(sup, children[2])
    result.append(expression)
    # OMML sSub: base + 下标；sSup: base + 上标；sSubSup: base + 下标 + 上标
    if kind in {"sSub", "sSubSup"}:
        result.append(sub)
    if kind in {"sSup", "sSubSup"}:
        result.append(sup)
    target.append(result)


def _accent(target, node) -> None:
    """重音符号（mover + accent=true）：OMML acc 元素。

    结构：acc > accPr(含 chr) > e(基础表达式)
    latex2mathml 对 \\hat{x} 等 → <mover accent="true"><mi>x</mi><mo>^</mo></mover>
    """
    children = list(node)
    accent_char = ""
    if len(children) > 1:
        op = children[1]
        # 取 mo 的文本内容作为重音字符
        accent_char = "".join(op.itertext()) if op is not None else ""
    accent = _element("acc")
    properties = _element("accPr")
    char = _element("chr")
    char.set(qn("m:val"), accent_char)
    properties.append(char)
    expression = _element("e")
    if children:
        _append_mathml(expression, children[0])
    accent.extend((properties, expression))
    target.append(accent)


def _bar(target, node, position: str) -> None:
    """上/下划线（mover/munder + bar）：OMML bar 元素。

    position: "top"（上划线，\\overline）或 "bot"（下划线）。
    """
    bar = _element("bar")
    properties = _element("barPr")
    pos = _element("pos")
    pos.set(qn("m:val"), position)
    properties.append(pos)
    expression = _element("e")
    children = list(node)
    if children:
        _append_mathml(expression, children[0])
    bar.extend((properties, expression))
    target.append(bar)


def _limit(target, node, kind: str) -> None:
    """上下限（munder/mover 非 accent）：OMML limLow / limUpp 元素。

    kind: "limLow"（下限，munder）或 "limUpp"（上限，mover）。
    结构：limLow > e(基础) > lim(极限表达式)
    """
    lim_element = _element(kind)
    expression = _element("e")
    limit = _element("lim")
    children = list(node)
    if children:
        _append_mathml(expression, children[0])
    if len(children) > 1:
        _append_mathml(limit, children[1])
    lim_element.extend((expression, limit))
    target.append(lim_element)


def _resolve_mover_munder(target, node, is_over: bool) -> None:
    """按 accent 属性 + 第二子节点类型分流 mover/munder 到正确 OMML 元素。

    is_over: True=mover（上方），False=munder（下方）。
    规范参考：MS-ODF3 mover 映射到 nAry/overbar/accent/groupChr/limUpp。
    """
    children = list(node)
    accent_attr = node.attrib.get("accent", "").lower() == "true"
    second_is_mo = len(children) > 1 and children[1].tag.removeprefix(MATHML_NS) == "mo"
    second_text = ""
    if second_is_mo:
        second_text = "".join(children[1].itertext())

    # 1. accent=true + 单字符 mo → acc（重音：\hat \vec \tilde 等）
    if is_over and accent_attr and second_is_mo and len(second_text) <= 1:
        _accent(target, node)
        return
    # 2. 上方 + mo 为 ¯(0xAF) → bar top（\overline）
    if is_over and second_is_mo and second_text == "\u00af":
        _bar(target, node, "top")
        return
    # 3. 下方 + mo 为 _ → bar bot（\underline）
    if not is_over and second_is_mo and second_text == "_":
        _bar(target, node, "bot")
        return
    # 4. 其他 → limLow（munder）/ limUpp（mover）
    _limit(target, node, "limUpp" if is_over else "limLow")


def _append_mathml(target, node) -> None:
    tag = node.tag.removeprefix(MATHML_NS)
    children = list(node)

    if tag in {"math", "mrow", "mstyle", "semantics", "annotation"}:
        _append_children(target, node)
    elif tag in {"mi", "mn", "mo", "mtext"}:
        target.append(_text_run("".join(node.itertext())))
    elif tag == "mfrac":
        fraction = _element("f")
        numerator = _element("num")
        denominator = _element("den")
        if children:
            _append_mathml(numerator, children[0])
        if len(children) > 1:
            _append_mathml(denominator, children[1])
        fraction.extend((numerator, denominator))
        target.append(fraction)
    elif tag == "msub":
        _script(target, node, "sSub")
    elif tag == "msup":
        _script(target, node, "sSup")
    elif tag == "msubsup":
        _script(target, node, "sSubSup")
    elif tag == "munderover":
        # 上下限组合：limUpp > e > limLow（上限含下限），与 OMML limUpp 结构对齐
        outer = _element("limUpp")
        outer_expr = _element("e")
        inner = _element("limLow")
        inner_expr = _element("e")
        inner_lim = _element("lim")
        if children:
            _append_mathml(inner_expr, children[0])
        if len(children) > 1:
            _append_mathml(inner_lim, children[1])
        inner.extend((inner_expr, inner_lim))
        outer_expr.append(inner)
        if len(children) > 2:
            outer_lim = _element("lim")
            _append_mathml(outer_lim, children[2])
            outer.append(outer_lim)
        outer.insert(0, outer_expr)
        target.append(outer)
    elif tag == "munder":
        _resolve_mover_munder(target, node, is_over=False)
    elif tag == "mover":
        _resolve_mover_munder(target, node, is_over=True)
    elif tag == "msqrt":
        radical = _element("rad")
        properties = _element("radPr")
        hide_degree = _element("degHide")
        hide_degree.set(qn("m:val"), "1")
        properties.append(hide_degree)
        degree = _element("deg")
        expression = _element("e")
        _append_children(expression, node)
        radical.extend((properties, degree, expression))
        target.append(radical)
    elif tag == "mroot":
        radical = _element("rad")
        degree = _element("deg")
        expression = _element("e")
        if children:
            _append_mathml(expression, children[0])
        if len(children) > 1:
            _append_mathml(degree, children[1])
        radical.extend((degree, expression))
        target.append(radical)
    elif tag == "mfenced":
        delimiter = _element("d")
        properties = _element("dPr")
        begin = _element("begChr")
        begin.set(qn("m:val"), node.attrib.get("open", "("))
        end = _element("endChr")
        end.set(qn("m:val"), node.attrib.get("close", ")"))
        properties.extend((begin, end))
        expression = _element("e")
        _append_children(expression, node)
        delimiter.extend((properties, expression))
        target.append(delimiter)
    elif tag == "mtable":
        matrix = _element("m")
        for row_node in children:
            row = _element("mr")
            for cell_node in list(row_node):
                cell = _element("e")
                _append_children(cell, cell_node)
                row.append(cell)
            matrix.append(row)
        target.append(matrix)
    elif tag in {"mtr", "mtd"}:
        _append_children(target, node)
    elif tag == "mspace":
        target.append(_text_run(" "))
    else:
        _append_children(target, node)


def latex_to_omml(latex: str):
    try:
        from latex2mathml.converter import convert
    except ImportError as error:
        raise RuntimeError(
            "Native equations require latex2mathml: py -3 -m pip install latex2mathml"
        ) from error

    mathml = ElementTree.fromstring(convert(latex))
    paragraph = _element("oMathPara")
    math = _element("oMath")
    _append_mathml(math, mathml)
    paragraph.append(math)
    return paragraph


def clone_omml(element):
    return deepcopy(element)

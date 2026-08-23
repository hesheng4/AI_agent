r"""L7 tests — munder/mover/munderover 语义正确映射到 OMML acc/bar/limLow/limUpp。

R34 修复前：mover→sSup / munder→sSub（上下修饰当上下标，语义错误）。
R34 修复后：按 accent 属性 + 第二子节点类型分流：
  - mover + accent=true + 单字符 mo → acc（重音：\hat \vec \tilde）
  - mover + mo=¯(0xAF) → bar top（\overline）
  - munder + mo=_ → bar bot（\underline）
  - munder 其他 → limLow（下限：\lim_{n}）
  - mover 其他 → limUpp（上限）
  - munderover → limUpp 包 limLow（上下限组合）
"""

import os
import sys
from xml.etree import ElementTree

# math_to_omml 在 scripts 目录，需加入 path
SCRIPTS_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "app",
    "agents",
    "paper_to_patent",
    "scripts",
)
sys.path.insert(0, SCRIPTS_DIR)

# docx 已确认安装（python-docx 1.2.0）
from math_to_omml import _append_mathml, _element  # noqa: E402

MATH_NS = "http://www.w3.org/1998/Math/MathML"


def _mathml(xml: str):
    """解析 MathML 字符串为 ElementTree 节点。"""
    return ElementTree.fromstring(f"<math xmlns='{MATH_NS}'>{xml}</math>")


def _omml_children(o_math, tag: str):
    """查找 oMath 下指定 tag 的子元素
    （OOXML m: 命名空间无 namespace prefix，OxmlElement 已处理）。
    """
    return o_math.findall(
        f"{{http://schemas.openxmlformats.org/officeDocument/2006/math}}{tag}"
    )


def _text_of(element) -> str:
    """提取元素内所有文本。"""
    return "".join(t.text or "" for t in element.iter() if t.text)


# ── mover + accent=true → acc（重音）──


def test_mover_accent_hat_to_acc():
    r"""\\hat{x} → mover accent=true → OMML acc 元素，重音字符 '^' 在 accPr/chr。"""
    mathml = _mathml('<mover accent="true"><mi>x</mi><mo>^</mo></mover>')
    o_math = _element("oMath")
    _append_mathml(o_math, mathml[0])
    acc = _omml_children(o_math, "acc")
    assert acc is not None and len(acc) == 1, "应生成 acc 元素"
    chr_elem = acc[0].find(
        "{http://schemas.openxmlformats.org/officeDocument/2006/math}accPr/{http://schemas.openxmlformats.org/officeDocument/2006/math}chr"
    )
    assert chr_elem is not None, "acc 应含 accPr/chr"
    assert (
        chr_elem.get("{http://schemas.openxmlformats.org/officeDocument/2006/math}val")
        == "^"
    ), "chr 应为 '^'"
    e = acc[0].find("{http://schemas.openxmlformats.org/officeDocument/2006/math}e")
    assert "x" in _text_of(e), "acc 基础表达式应为 x"


def test_mover_accent_vec_to_acc():
    r"""\\vec{x} → mover accent=true + mo='→' → acc."""
    mathml = _mathml('<mover accent="true"><mi>x</mi><mo>&#x2192;</mo></mover>')
    o_math = _element("oMath")
    _append_mathml(o_math, mathml[0])
    acc = _omml_children(o_math, "acc")
    assert len(acc) == 1
    chr_elem = acc[0].find(
        "{http://schemas.openxmlformats.org/officeDocument/2006/math}accPr/{http://schemas.openxmlformats.org/officeDocument/2006/math}chr"
    )
    assert (
        chr_elem.get("{http://schemas.openxmlformats.org/officeDocument/2006/math}val")
        == "\u2192"
    )


# ── mover + mo=¯ → bar top（上划线）──


def test_mover_overline_to_bar_top():
    r"""\\overline{x} → mover + mo=¯(0xAF) → OMML bar pos=top."""
    mathml = _mathml("<mover><mi>x</mi><mo>&#x00AF;</mo></mover>")
    o_math = _element("oMath")
    _append_mathml(o_math, mathml[0])
    bar = _omml_children(o_math, "bar")
    assert len(bar) == 1, "应生成 bar 元素"
    pos = bar[0].find(
        "{http://schemas.openxmlformats.org/officeDocument/2006/math}barPr/{http://schemas.openxmlformats.org/officeDocument/2006/math}pos"
    )
    assert pos is not None, "bar 应含 barPr/pos"
    assert (
        pos.get("{http://schemas.openxmlformats.org/officeDocument/2006/math}val")
        == "top"
    ), "pos 应为 top"
    # 不应生成 acc 或 sSup
    assert _omml_children(o_math, "acc") == []
    assert _omml_children(o_math, "sSup") == [], "overline 不应映射为上标"


# ── munder + mo=_ → bar bot（下划线）──


def test_munder_underline_to_bar_bot():
    r"""\\underline{x} → munder + mo='_' → OMML bar pos=bot."""
    mathml = _mathml("<munder><mi>x</mi><mo>_</mo></munder>")
    o_math = _element("oMath")
    _append_mathml(o_math, mathml[0])
    bar = _omml_children(o_math, "bar")
    assert len(bar) == 1
    pos = bar[0].find(
        "{http://schemas.openxmlformats.org/officeDocument/2006/math}barPr/{http://schemas.openxmlformats.org/officeDocument/2006/math}pos"
    )
    assert (
        pos.get("{http://schemas.openxmlformats.org/officeDocument/2006/math}val")
        == "bot"
    )
    assert _omml_children(o_math, "sSub") == [], "underline 不应映射为下标"


# ── munder 其他 → limLow（下限）──


def test_munder_lim_to_limlow():
    r"""\\lim_{n\\to\\infty} x → munder + mi 基础 → OMML limLow."""
    # 简化：munder 基础为 lim，下方为 n
    mathml = _mathml("<munder><mi>lim</mi><mi>n</mi></munder>")
    o_math = _element("oMath")
    _append_mathml(o_math, mathml[0])
    lim_low = _omml_children(o_math, "limLow")
    assert len(lim_low) == 1, "应生成 limLow 元素"
    e = lim_low[0].find("{http://schemas.openxmlformats.org/officeDocument/2006/math}e")
    lim = lim_low[0].find(
        "{http://schemas.openxmlformats.org/officeDocument/2006/math}lim"
    )
    assert "lim" in _text_of(e), "基础应为 lim"
    assert "n" in _text_of(lim), "极限表达式应为 n"
    assert _omml_children(o_math, "sSub") == [], "lim 不应映射为下标"


# ── mover 其他 → limUpp（上限）──


def test_mover_other_to_limupp():
    """mover（非 accent，非 ¯）→ OMML limUpp。"""
    mathml = _mathml("<mover><mi>x</mi><mi>n</mi></mover>")
    o_math = _element("oMath")
    _append_mathml(o_math, mathml[0])
    lim_upp = _omml_children(o_math, "limUpp")
    assert len(lim_upp) == 1, "应生成 limUpp 元素"
    assert _omml_children(o_math, "sSup") == [], "不应映射为上标"


# ── munderover → limUpp 包 limLow（上下限组合）──


def test_munderover_to_limupp_wrapping_limlow():
    r"""munderover（如 \sum_{i=0}^{n}）→ limUpp > e > limLow 结构."""
    mathml = _mathml("<munderover><mi>&#x2211;</mi><mi>i=0</mi><mi>n</mi></munderover>")
    o_math = _element("oMath")
    _append_mathml(o_math, mathml[0])
    lim_upp = _omml_children(o_math, "limUpp")
    assert len(lim_upp) == 1, "应生成 limUpp 元素"
    e = lim_upp[0].find("{http://schemas.openxmlformats.org/officeDocument/2006/math}e")
    assert e is not None, "limUpp 应含 e"
    # e 内应含 limLow
    lim_low_in_e = e.findall(
        "{http://schemas.openxmlformats.org/officeDocument/2006/math}limLow"
    )
    assert len(lim_low_in_e) == 1, "limUpp 的 e 应含 limLow（下限）"
    # limUpp 应含 lim（上限 n）
    lim = lim_upp[0].find(
        "{http://schemas.openxmlformats.org/officeDocument/2006/math}lim"
    )
    assert lim is not None, "limUpp 应含 lim（上限）"
    assert "n" in _text_of(lim)
    assert _omml_children(o_math, "sSubSup") == [], "munderover 不应映射为 sSubSup"


# ── 回归：R33 的 L6 修复仍有效（上标不是下标）──


def test_msup_still_correct_after_l7():
    """L7 修改不应破坏 R33 的 L6 修复：msup → sSup，上标在 sup。"""
    mathml = _mathml("<msup><mi>x</mi><mn>2</mn></msup>")
    o_math = _element("oMath")
    _append_mathml(o_math, mathml[0])
    s_sup = _omml_children(o_math, "sSup")
    assert len(s_sup) == 1
    sup = s_sup[0].find(
        "{http://schemas.openxmlformats.org/officeDocument/2006/math}sup"
    )
    sub = s_sup[0].find(
        "{http://schemas.openxmlformats.org/officeDocument/2006/math}sub"
    )
    assert sup is not None and "2" in _text_of(sup)
    assert sub is None, "sSup 不应含 sub（L6 修复）"

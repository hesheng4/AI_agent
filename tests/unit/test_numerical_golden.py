"""数值黄金测试 — 以 scipy 为独立基准，校验手写的统计/功效实现

背景：本项目统计核心为纯手写（零第三方依赖），此前 479 个用例全绿，
      但对统计引擎的数值正确性零敏感度——把 t 分布 p 值改动最多 49%
      之后测试依然全绿。本文件即为此而设。

设计：
- scipy 仅作测试基准（dev 依赖），不进入生产依赖；缺失时整体跳过
- 每个断言都写明基准来源与容差理由
- 覆盖此前实测发现的全部缺陷：
    P0-1 _normal_cdf 展开点自变量错误（A&S 7.1.26 应为 x = z/sqrt(2)）
    P0-2 _approx_p_value 用 ad-hoc 变换冒充 t 分布
    P0-3 power_analysis._normal_cdf 同源副本
    P0-4 sample_size_ttest 对独立两样本误用单样本公式（少给一半样本量）
    P0-5 _calculate_power_ttest 非中心参数口径错误（功效高估最多 0.21）
"""

import math

import pytest

scipy = pytest.importorskip("scipy", reason="数值黄金测试需要 scipy 作为基准")

from scipy import stats as sps  # noqa: E402

from app.services.power_analysis import PowerAnalysis  # noqa: E402
from app.services.statistics import StatisticsEnhancer as S  # noqa: E402


# --------------------------------------------------------------------------
# P0-1 标准正态 CDF
# --------------------------------------------------------------------------


class TestNormalCDF:
    """A&S 7.1.26 的设计精度为 |eps| < 1.5e-7，取 1e-6 作断言上界

    修复前此处最大误差为 3.687e-2（z=0.5），即 5 个数量级的偏差。
    """

    @pytest.mark.parametrize(
        "z",
        [-6.0, -3.0, -1.96, -1.0, -0.5, 0.0, 0.5, 1.0, 1.96, 2.0, 3.0, 4.0, 6.0],
    )
    def test_matches_scipy(self, z):
        assert S._normal_cdf(z) == pytest.approx(sps.norm.cdf(z), abs=1e-6)

    def test_max_error_over_grid(self):
        worst = max(
            abs(S._normal_cdf(z / 10) - sps.norm.cdf(z / 10))
            for z in range(-80, 81)
        )
        assert worst < 1e-6, f"最大绝对误差 {worst:.3e} 超出 A&S 7.1.26 设计精度"

    def test_symmetry(self):
        for z in (0.3, 1.0, 2.5, 4.0):
            assert S._normal_cdf(-z) == pytest.approx(1 - S._normal_cdf(z), abs=1e-9)


# --------------------------------------------------------------------------
# P0-2 t 分布双侧 p 值
# --------------------------------------------------------------------------


class TestTPValue:
    """修复前使用 z = t/sqrt(1+t^2/(2df)) 的 ad-hoc 变换，48 个采样点中
    45 个相对误差 >10%，且 p 值系统性偏小（反保守），在 alpha=0.05 下
    会把不显著的结果误判为显著。
    """

    @pytest.mark.parametrize("df", [1, 2, 3, 5, 10, 20, 29, 30, 60, 120, 500])
    @pytest.mark.parametrize("t", [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 6.0])
    def test_matches_scipy_two_sided(self, df, t):
        expected = 2 * sps.t.sf(abs(t), df)
        got = S._approx_p_value(t, df)
        # 极小 p 值用相对容差，否则用绝对容差
        assert got == pytest.approx(expected, rel=1e-4, abs=1e-9)

    def test_no_systematic_underestimate(self):
        """反保守检验：p 值不得系统性偏小，否则假阳性膨胀"""
        under = 0
        total = 0
        for df in (2, 3, 5, 10, 20, 29, 60, 120):
            for t in (1.0, 1.5, 2.0, 2.5, 3.0, 4.0):
                got = S._approx_p_value(t, df)
                exp = 2 * sps.t.sf(t, df)
                total += 1
                if got < exp * (1 - 1e-6):
                    under += 1
        assert under == 0, f"{total} 个采样点中 {under} 个 p 值偏小（反保守）"

    def test_alpha_boundary_no_flip(self):
        """alpha=0.05 边界上不得出现显著性结论翻转"""
        flips = []
        for df in (2, 3, 5, 8, 10, 15, 20, 29, 50):
            for t in [x / 10 for x in range(15, 45)]:
                got_sig = S._approx_p_value(t, df) < 0.05
                exp_sig = 2 * sps.t.sf(t, df) < 0.05
                if got_sig != exp_sig:
                    flips.append((df, t))
        assert not flips, f"显著性结论翻转 {len(flips)} 处，例：{flips[:5]}"

    def test_monotone_decreasing_in_t(self):
        for df in (3, 10, 60):
            vals = [S._approx_p_value(t / 4, df) for t in range(2, 40)]
            assert all(
                a >= b - 1e-12 for a, b in zip(vals, vals[1:])
            ), f"df={df} 时 p 值非单调递减"


# --------------------------------------------------------------------------
# F 分布 / 卡方 p 值（此前实现正确，此处作回归保护）
# --------------------------------------------------------------------------


class TestFAndChi2PValue:
    @pytest.mark.parametrize(
        "d1,d2", [(1, 5), (2, 10), (3, 20), (5, 30), (4, 60), (10, 100)]
    )
    @pytest.mark.parametrize("f", [0.5, 1.0, 2.0, 3.0, 5.0, 10.0])
    def test_f_matches_scipy(self, d1, d2, f):
        assert S._approx_p_value_f(f, d1, d2) == pytest.approx(
            sps.f.sf(f, d1, d2), rel=1e-4, abs=1e-9
        )

    @pytest.mark.parametrize("df", [1, 2, 3, 5, 10, 20, 50])
    @pytest.mark.parametrize("x", [0.5, 1.0, 3.0, 5.0, 10.0, 20.0, 40.0])
    def test_chi2_decision_region(self, df, x):
        """决策区间（p >= 1e-3，即实际做显著性判断的区域）须准确

        实测 41 个决策区间采样点中仅 1 个相对误差 >10%。
        """
        expected = sps.chi2.sf(x, df)
        if expected < 1e-3:
            pytest.skip("极端尾部由 test_chi2_extreme_tail_known_limitation 覆盖")
        got = S._approx_p_value_chi2(x, df)
        assert got == pytest.approx(expected, rel=0.12, abs=1e-6)

    @pytest.mark.parametrize("df", [1, 2, 3, 5])
    @pytest.mark.parametrize("x", [20.0, 40.0])
    def test_chi2_extreme_tail_known_limitation(self, df, x):
        """已知局限（P2）：Wilson-Hilferty 在 p < 1e-3 时严重退化

        实测最坏情形 df=1/x=40：报 1.05e-08，真值 2.54e-10，差约 40 倍。
        不影响 alpha=0.05/0.01 的显著性判定，但会让「p < 0.0001」这类
        对外报告的极小 p 值失真。修复需引入正则化不完全 Gamma 函数
        （当前代码只有不完全 Beta）。此处锁定现状，防止进一步劣化。
        """
        expected = sps.chi2.sf(x, df)
        if expected >= 1e-3:
            pytest.skip("非极端尾部")
        got = S._approx_p_value_chi2(x, df)
        # 方向上必须仍在同一数量级内单调缩小、且不得为负或 >1
        assert 0.0 <= got <= 1.0
        assert got < 1e-2, f"极端尾部未收敛：df={df} x={x} -> {got}"


# --------------------------------------------------------------------------
# P0-3 power_analysis._normal_cdf 同源副本
# --------------------------------------------------------------------------


class TestPowerAnalysisNormalCDF:
    @pytest.mark.parametrize("z", [-4.0, -1.96, -1.0, -0.5, 0.0, 0.5, 1.0, 1.96, 4.0])
    def test_matches_scipy(self, z):
        assert PowerAnalysis._normal_cdf(z) == pytest.approx(
            sps.norm.cdf(z), abs=1e-6
        )


class TestNormalQuantile:
    """Acklam 有理逼近，设计相对精度约 1.15e-9 —— 这部分实现是正确的，作回归保护"""

    @pytest.mark.parametrize(
        "p", [0.001, 0.01, 0.025, 0.05, 0.1, 0.3, 0.5, 0.7, 0.9, 0.975, 0.99, 0.999]
    )
    def test_matches_scipy(self, p):
        assert PowerAnalysis._normal_quantile(p) == pytest.approx(
            sps.norm.ppf(p), abs=1e-6
        )


# --------------------------------------------------------------------------
# P0-4 / P0-5 样本量与功效
# --------------------------------------------------------------------------


def _exact_power_two_sample(n_per_group, d, alpha=0.05):
    """独立两样本 t 检验精确功效（scipy 非中心 t）"""
    df = 2 * n_per_group - 2
    nc = d * math.sqrt(n_per_group / 2)
    t_crit = sps.t.ppf(1 - alpha / 2, df)
    return float(sps.nct.sf(t_crit, df, nc))


def _exact_power_paired(n_pairs, d, alpha=0.05):
    """配对 t 检验精确功效（退化为单样本 t，df = n-1）"""
    df = n_pairs - 1
    nc = d * math.sqrt(n_pairs)
    t_crit = sps.t.ppf(1 - alpha / 2, df)
    return float(sps.nct.sf(t_crit, df, nc))


def _min_n_two_sample(d, alpha=0.05, target=0.80, cap=2000):
    """scipy 精确基准：满足目标功效的最小每组样本量"""
    for n in range(2, cap):
        if _exact_power_two_sample(n, d, alpha) >= target:
            return n
    raise AssertionError(f"d={d} 在 cap={cap} 内未达到功效 {target}")


def _min_n_paired(d, alpha=0.05, target=0.80, cap=2000):
    """scipy 精确基准：满足目标功效的最小对子数"""
    for n in range(2, cap):
        if _exact_power_paired(n, d, alpha) >= target:
            return n
    raise AssertionError(f"d={d} 在 cap={cap} 内未达到功效 {target}")


class TestSampleSizeTTest:
    """修复前两种设计共用单样本公式，独立两样本每组样本量只有所需的一半"""

    @pytest.mark.parametrize("d", [0.2, 0.3, 0.5, 0.8, 1.0])
    def test_two_sample_size_matches_exact(self, d):
        """与 scipy 非中心 t 精确解对齐，容差 ±1

        注意：教科书常用的 z 闭式解 n = 2(z_a+z_b)^2/d^2 本身会略微低估
        （忽略 t 分布临界值更宽），因此本实现给出的 n 应 >= 闭式解。
        """
        expected = _min_n_two_sample(d)
        got = PowerAnalysis.sample_size_ttest(
            effect_size=d, alpha=0.05, power=0.80, paired=False
        )["n_per_group"]
        assert abs(got - expected) <= 1, (
            f"d={d}: 本实现 n={got}/组，scipy 精确解 {expected}/组"
        )

    @pytest.mark.parametrize("d", [0.2, 0.3, 0.5, 0.8, 1.0])
    def test_never_below_textbook_closed_form(self, d):
        """不得小于 z 闭式解——低于它意味着功效必然不足"""
        z_a = sps.norm.ppf(1 - 0.05 / 2)
        z_b = sps.norm.ppf(0.80)
        closed_form = math.ceil(2 * ((z_a + z_b) / d) ** 2)
        got = PowerAnalysis.sample_size_ttest(
            effect_size=d, alpha=0.05, power=0.80, paired=False
        )["n_per_group"]
        assert got >= closed_form, (
            f"d={d}: n={got} 低于 z 闭式解 {closed_form}，功效必然不足"
        )

    @pytest.mark.parametrize("d", [0.2, 0.5, 0.8])
    def test_two_sample_achieves_target_power(self, d):
        """按建议样本量开题，真实功效必须真的达到 0.80"""
        n = PowerAnalysis.sample_size_ttest(
            effect_size=d, alpha=0.05, power=0.80, paired=False
        )["n_per_group"]
        real = _exact_power_two_sample(n, d)
        assert real >= 0.78, f"d={d} 建议 n={n}/组，真实功效仅 {real:.3f}（<0.78）"

    @pytest.mark.parametrize("d", [0.2, 0.5, 0.8])
    def test_paired_size_matches_exact(self, d):
        """配对设计与 scipy 非中心 t 精确解对齐，容差 ±1"""
        expected = _min_n_paired(d)
        got = PowerAnalysis.sample_size_ttest(
            effect_size=d, alpha=0.05, power=0.80, paired=True
        )["n_per_group"]
        assert abs(got - expected) <= 1, (
            f"d={d}: 本实现 {got} 对，scipy 精确解 {expected} 对"
        )

    @pytest.mark.parametrize("d", [0.2, 0.5, 0.8])
    def test_paired_achieves_target_power(self, d):
        """配对设计：对子数按单样本口径，真实功效同样须达 0.80"""
        n = PowerAnalysis.sample_size_ttest(
            effect_size=d, alpha=0.05, power=0.80, paired=True
        )["n_per_group"]
        real = _exact_power_paired(n, d)
        assert real >= 0.78, f"d={d} 建议 {n} 对，真实功效仅 {real:.3f}"

    def test_reported_power_matches_truth(self):
        """对外报告的 actual_power 不得与真实功效偏差超过 0.05"""
        for d in (0.2, 0.3, 0.5, 0.8, 1.0):
            r = PowerAnalysis.sample_size_ttest(
                effect_size=d, alpha=0.05, power=0.80, paired=False
            )
            claimed = r["actual_power"]
            real = _exact_power_two_sample(r["n_per_group"], d)
            assert abs(claimed - real) <= 0.05, (
                f"d={d}: 报告功效 {claimed:.3f}，真实 {real:.3f}，"
                f"偏差 {claimed - real:+.3f}"
            )

    def test_paired_needs_fewer_than_independent(self):
        """同等条件下配对设计所需对子数应少于独立两样本的每组样本量"""
        for d in (0.3, 0.5, 0.8):
            ind = PowerAnalysis.sample_size_ttest(
                effect_size=d, paired=False
            )["n_per_group"]
            pai = PowerAnalysis.sample_size_ttest(effect_size=d, paired=True)[
                "n_per_group"
            ]
            assert pai < ind, f"d={d}: 配对 {pai} 未少于独立 {ind}"


class TestPowerCalculation:
    @pytest.mark.parametrize(
        "n", [8, 16, 32, 64, 100, 200]
    )
    @pytest.mark.parametrize("d", [0.2, 0.3, 0.5, 0.8])
    def test_two_sample_power_matches_scipy(self, n, d):
        """正态近似对非中心 t 的偏差上限约 0.05，取 0.06 作容差"""
        got = PowerAnalysis._calculate_power_ttest(
            n=n, effect_size=d, alpha=0.05, paired=False
        )
        exp = _exact_power_two_sample(n, d)
        assert abs(got - exp) <= 0.06, (
            f"n={n}/组 d={d}: 算得 {got:.4f}，scipy {exp:.4f}，"
            f"偏差 {got - exp:+.4f}"
        )

    @pytest.mark.parametrize("n", [16, 32, 64, 100])
    @pytest.mark.parametrize("d", [0.3, 0.5, 0.8])
    def test_paired_power_matches_scipy(self, n, d):
        got = PowerAnalysis._calculate_power_ttest(
            n=n, effect_size=d, alpha=0.05, paired=True
        )
        exp = _exact_power_paired(n, d)
        assert abs(got - exp) <= 0.06, (
            f"n={n} 对 d={d}: 算得 {got:.4f}，scipy {exp:.4f}，偏差 {got - exp:+.4f}"
        )

    def test_power_monotone_in_n(self):
        vals = [
            PowerAnalysis._calculate_power_ttest(
                n=n, effect_size=0.5, alpha=0.05, paired=False
            )
            for n in range(5, 200, 5)
        ]
        assert all(
            b >= a - 1e-9 for a, b in zip(vals, vals[1:])
        ), "功效随样本量非单调递增"


class TestPowerCurve:
    def test_target_n_consistent_with_sample_size(self):
        """功效曲线给出的 target_n 必须与 sample_size_ttest 自洽"""
        d = 0.5
        curve = PowerAnalysis.power_curve_ttest(effect_size=d, alpha=0.05, max_n=200)
        ss = PowerAnalysis.sample_size_ttest(
            effect_size=d, alpha=0.05, power=0.80, paired=False
        )["n_per_group"]
        # 曲线按步长 5 采样，target_n 应落在 [ss, ss+5) 区间
        assert ss <= curve["target_n"] < ss + 5, (
            f"功效曲线 target_n={curve['target_n']}，样本量计算给出 {ss}"
        )


# --------------------------------------------------------------------------
# 描述性统计
# --------------------------------------------------------------------------


class TestDescriptiveStats:
    def test_known_values(self):
        data = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        r = S.descriptive_stats(data)
        assert r["n"] == 8
        assert r["mean"] == pytest.approx(5.0, abs=1e-9)
        # 样本方差（n-1）：32/7
        assert r["variance"] == pytest.approx(32 / 7, abs=1e-4)
        assert r["std_dev"] == pytest.approx(math.sqrt(32 / 7), abs=1e-4)
        assert r["median"] == pytest.approx(4.5, abs=1e-9)

    def test_matches_scipy_on_random_data(self):
        import random

        random.seed(20260831)
        data = [random.gauss(10, 3) for _ in range(500)]
        r = S.descriptive_stats(data)
        assert r["mean"] == pytest.approx(sps.tmean(data), abs=1e-4)
        assert r["variance"] == pytest.approx(sps.tvar(data), abs=1e-2)
        assert r["median"] == pytest.approx(sps.scoreatpercentile(data, 50), abs=1e-2)

    def test_empty_input(self):
        assert "error" in S.descriptive_stats([])

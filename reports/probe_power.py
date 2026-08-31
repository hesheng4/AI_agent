"""功效分析实测：样本量 / 功效 vs 非中心 t 分布精确值

非中心 t：T' = (Z + ncp) / sqrt(V/df)，Z~N(0,1)，V~chi2(df)
  P(T' > t) = 1 - E_V[ Phi(t*sqrt(V/df) - ncp) ]
用 chi2 密度数值积分求期望，作为独立基准。
"""

import math
import sys

sys.path.insert(0, ".")

from app.services.power_analysis import PowerAnalysis as P


def norm_cdf(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def chi2_pdf(u, df):
    if u <= 0:
        return 0.0
    return math.exp(
        (df / 2 - 1) * math.log(u)
        - u / 2
        - (df / 2) * math.log(2)
        - math.lgamma(df / 2)
    )


def nct_sf(t, df, ncp, n=4000, ub=None):
    """P(T' > t)，非中心 t 生存函数，数值积分"""
    ub = ub or max(4 * df, 200)
    lo, hi = 1e-9, ub
    h = (hi - lo) / n
    s = 0.0
    for i in range(n + 1):
        u = lo + i * h
        w = 1 if i in (0, n) else (4 if i % 2 else 2)
        s += w * chi2_pdf(u, df) * (1 - norm_cdf(t * math.sqrt(u / df) - ncp))
    return s * h / 3


def two_sample_power(n_per_group, d, alpha=0.05):
    """两样本 t 检验真实功效（双侧）"""
    df = 2 * n_per_group - 2
    ncp = d * math.sqrt(n_per_group / 2)
    # 临界值用 t 分布分位数（二分求解中心 t 生存函数）
    lo, hi = 0.0, 50.0
    for _ in range(100):
        m = (lo + hi) / 2
        if nct_sf(m, df, 0.0) > alpha:
            lo = m
        else:
            hi = m
    t_crit = (lo + hi) / 2
    return nct_sf(t_crit, df, ncp), t_crit


def ref_n_two_sample(d, alpha=0.05, power=0.80):
    """教科书：两样本每组所需 n = 2(z_a+z_b)^2/d^2"""
    za, zb = 1.959963985, 0.841621234
    return math.ceil(2 * ((za + zb) / d) ** 2)


print("=" * 80)
print("功效分析实测审计 — app/services/power_analysis.py")
print("=" * 80)

print("\n[A] sample_size_ttest(paired=False)：模块输出 vs 教科书标准值")
print(
    f"{'d':>5} {'模块n/组':>9} {'标准n/组':>9} {'缺口':>8} {'模块称power':>12} {'真实power':>11} {'偏差':>9}"
)
for d in [0.2, 0.3, 0.5, 0.8, 1.0]:
    r = P.sample_size_ttest(effect_size=d, alpha=0.05, power=0.80, paired=False)
    n_mod = r["n_per_group"]
    n_ref = ref_n_two_sample(d)
    claimed = r["actual_power"]
    real, _ = two_sample_power(n_mod, d)
    gap = n_mod / n_ref
    print(
        f"{d:5.1f} {n_mod:9d} {n_ref:9d} {gap:7.2f}x {claimed:12.4f} {real:11.4f} "
        f"{claimed - real:+8.3f}"
    )

print("\n[B] 直接验证功效反算：给定 n/组，模块 _calculate_power_ttest vs 真实值")
print(f"{'n/组':>6} {'d':>5} {'模块power':>11} {'真实power':>11} {'偏差':>9}")
for n in [16, 32, 64, 100]:
    for d in [0.3, 0.5, 0.8]:
        try:
            claimed = P._calculate_power_ttest(n=n, effect_size=d, alpha=0.05)
        except Exception as e:
            claimed = float("nan")
        real, _ = two_sample_power(n, d)
        print(f"{n:6d} {d:5.1f} {claimed:11.4f} {real:11.4f} {claimed - real:+8.3f}")

print("\n[C] _normal_quantile（Acklam 实现）精度检查")
worst = 0.0
for p in [0.001, 0.01, 0.025, 0.05, 0.1, 0.3, 0.5, 0.7, 0.9, 0.975, 0.99, 0.999]:
    got = P._normal_quantile(p)
    # 基准：二分反解 erf
    lo, hi = -10.0, 10.0
    for _ in range(200):
        m = (lo + hi) / 2
        if norm_cdf(m) < p:
            lo = m
        else:
            hi = m
    exp = (lo + hi) / 2
    worst = max(worst, abs(got - exp))
    print(f"  p={p:<6} got={got:+.9f}  exact={exp:+.9f}  err={abs(got - exp):.2e}")
print(f"→ _normal_quantile 最大误差 {worst:.2e}")

print("\n[D] _normal_cdf（power_analysis 内的副本）精度检查")
worst2 = 0.0
for z in [0.5, 1.0, 1.96, 2.0, 3.0, 4.0]:
    got = P._normal_cdf(z)
    exp = norm_cdf(z)
    worst2 = max(worst2, abs(got - exp))
    print(f"  z={z:<5} got={got:.9f}  exact={exp:.9f}  err={abs(got - exp):.2e}")
print(f"→ power_analysis._normal_cdf 最大误差 {worst2:.2e}（与 statistics.py 同源 bug）")

print("\n" + "=" * 80)

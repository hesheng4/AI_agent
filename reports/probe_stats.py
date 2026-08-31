"""厚算法实测：手写统计分布 vs 精确值（数值积分基准）

判定：能否跑出正确数值。误差用「相对误差」与「绝对误差」双口径。
"""

import math
import sys

sys.path.insert(0, ".")

from app.services.statistics import StatisticsEnhancer as S

# ---------- 独立基准：数值积分（Simpson）----------


def simpson(f, a, b, n=200000):
    if n % 2:
        n += 1
    h = (b - a) / n
    s = f(a) + f(b)
    for i in range(1, n):
        s += f(a + i * h) * (4 if i % 2 else 2)
    return s * h / 3


def t_pdf(x, df):
    return math.exp(
        math.lgamma((df + 1) / 2)
        - math.lgamma(df / 2)
        - 0.5 * math.log(df * math.pi)
        - (df + 1) / 2 * math.log1p(x * x / df)
    )


def t_tail_exact(t, df):
    """P(|T| > t)，双侧，数值积分到足够远的截断点"""
    t = abs(t)
    tail = simpson(lambda x: t_pdf(x, df), t, t + 200, 200000)
    # 补上极远尾部（幂律衰减，解析上界）
    return min(1.0, 2 * tail)


def f_tail_exact(f, d1, d2):
    """P(F > f)，数值积分"""
    c = math.exp(
        d1 / 2 * math.log(d1)
        + d2 / 2 * math.log(d2)
        + math.lgamma((d1 + d2) / 2)
        - math.lgamma(d1 / 2)
        - math.lgamma(d2 / 2)
    )

    def pdf(x):
        return (
            c * x ** (d1 / 2 - 1) * (d2 + d1 * x) ** (-(d1 + d2) / 2)
        )

    ub = max(f * 3, f + 50)
    return min(1.0, simpson(pdf, f, ub, 200000))


def chi2_tail_exact(x, df):
    """P(Chi2 > x)，数值积分"""

    def pdf(t):
        if t <= 0:
            return 0.0
        return math.exp(
            (df / 2 - 1) * math.log(t)
            - t / 2
            - (df / 2) * math.log(2)
            - math.lgamma(df / 2)
        )

    ub = max(x * 3, x + 200)
    return min(1.0, simpson(pdf, x, ub, 200000))


def norm_cdf_exact(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def rel(a, b):
    """相对误差，b 为基准"""
    if b == 0:
        return abs(a - b)
    return abs(a - b) / abs(b)


print("=" * 78)
print("厚算法实测审计 — app/services/statistics.py（纯手写，零 scipy 依赖）")
print("=" * 78)

# ---------- 1. 正态 CDF ----------
print("\n[1] _normal_cdf  vs  math.erf 精确值")
print(f"{'z':>6} {'impl':>18} {'exact':>18} {'abs_err':>12}")
worst_n = 0.0
for z in [0.0, 0.5, 1.0, 1.96, 2.0, 2.576, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0]:
    got = S._normal_cdf(z)
    exp = norm_cdf_exact(z)
    err = abs(got - exp)
    worst_n = max(worst_n, err)
    print(f"{z:6.2f} {got:18.12f} {exp:18.12f} {err:12.3e}")
print(f"→ 最大绝对误差 {worst_n:.3e}")

print("\n[1b] 尾巴上的相对误差（这是 p 值计算的真正风险点）")
print(f"{'z':>6} {'impl 1-CDF':>16} {'exact 1-CDF':>16} {'相对误差':>12}")
for z in [3.0, 4.0, 5.0, 6.0, 7.0, 8.0]:
    got = 1 - S._normal_cdf(z)
    exp = 1 - norm_cdf_exact(z)
    r = rel(got, exp)
    print(f"{z:6.2f} {got:16.9e} {exp:16.9e} {r:11.1%}")

# ---------- 2. t 分布 p 值 ----------
print("\n[2] _approx_p_value(t, df)  vs  数值积分精确值（双侧）")
print(f"{'df':>4} {'t':>7} {'impl':>13} {'exact':>13} {'相对误差':>11} {'判定':>8}")
t_bad = 0
t_tot = 0
for df in [2, 3, 5, 10, 15, 29, 30, 60, 120]:
    for t in [1.0, 1.5, 2.0, 2.5, 3.0, 4.0]:
        got = S._approx_p_value(t, df)
        exp = t_tail_exact(t, df)
        r = rel(got, exp)
        t_tot += 1
        anti = got < exp  # 偏小 => 反保守 => 假阳性膨胀
        if r > 0.10:
            t_bad += 1
        if t in (2.0, 3.0) or df in (3, 29):
            flag = ("反保守!" if anti and r > 0.10 else "ok") if r <= 0.10 else "偏差大"
            print(f"{df:4d} {t:7.2f} {got:13.6f} {exp:13.6f} {r:10.1%} {flag:>8}")
print(f"→ {t_tot} 个采样点中 {t_bad} 个相对误差 >10%")

print("\n[2b] 显著性判定翻转检查（α=0.05 边界）")
print(f"{'df':>4} {'t':>7} {'impl p':>11} {'exact p':>11}  {'impl结论':>9} {'真实结论':>9} 一致?")
flips = 0
for df in [2, 3, 5, 8, 10, 15, 20, 29]:
    for t in [1.8, 2.0, 2.2, 2.3, 2.5, 2.8, 3.2, 4.0]:
        gp = S._approx_p_value(t, df)
        ep = t_tail_exact(t, df)
        gc = gp < 0.05
        ec = ep < 0.05
        if gc != ec:
            flips += 1
            print(
                f"{df:4d} {t:7.2f} {gp:11.5f} {ep:11.5f}  "
                f"{'显著' if gc else '不显著':>9} {'显著' if ec else '不显著':>9}  ✗ 翻转"
            )
print(f"→ α=0.05 下共 {flips} 处结论翻转（{56} 个采样点）")

# ---------- 3. F 分布 ----------
print("\n[3] _approx_p_value_f(f, df1, df2)  vs  数值积分精确值")
print(f"{'df1':>4} {'df2':>5} {'f':>7} {'impl':>13} {'exact':>13} {'相对误差':>11}")
f_bad = 0
f_tot = 0
for d1, d2 in [(2, 10), (3, 20), (5, 30), (1, 15), (4, 60), (10, 100)]:
    for f in [1.0, 2.0, 3.0, 5.0, 10.0]:
        got = S._approx_p_value_f(f, d1, d2)
        exp = f_tail_exact(f, d1, d2)
        r = rel(got, exp)
        f_tot += 1
        if r > 0.10:
            f_bad += 1
        if f in (3.0, 5.0):
            print(f"{d1:4d} {d2:5d} {f:7.2f} {got:13.6f} {exp:13.6f} {r:10.1%}")
print(f"→ {f_tot} 个采样点中 {f_bad} 个相对误差 >10%")

# ---------- 4. 卡方 ----------
print("\n[4] _approx_p_value_chi2(chi2, df)  vs  数值积分精确值")
print(f"{'df':>4} {'chi2':>8} {'impl':>13} {'exact':>13} {'相对误差':>11}")
c_bad = 0
c_tot = 0
for df in [1, 2, 3, 5, 10, 20]:
    for x in [1.0, 3.0, 5.0, 10.0, 20.0]:
        got = S._approx_p_value_chi2(x, df)
        exp = chi2_tail_exact(x, df)
        r = rel(got, exp)
        c_tot += 1
        if r > 0.10:
            c_bad += 1
        if x in (5.0, 10.0):
            print(f"{df:4d} {x:8.2f} {got:13.6f} {exp:13.6f} {r:10.1%}")
print(f"→ {c_tot} 个采样点中 {c_bad} 个相对误差 >10%")

print("\n" + "=" * 78)

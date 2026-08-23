"""样本量与功效分析服务"""

import math
from typing import Any

from app.utils.exceptions import ToolException
from app.utils.logger import get_logger

logger = get_logger("services.power_analysis")


class PowerAnalysis:
    """样本量计算与功效分析"""

    # ========== 样本量计算 ==========

    @staticmethod
    def sample_size_ttest(
        effect_size: float = 0.5,
        alpha: float = 0.05,
        power: float = 0.8,
        test_type: str = "two-sided",
        paired: bool = False,
    ) -> dict[str, Any]:
        """t检验样本量计算

        Args:
            effect_size: Cohen's d效应量
            alpha: 显著性水平
            power: 统计功效
            test_type: "two-sided" 或 "one-sided"
            paired: 是否配对样本
        """
        if effect_size <= 0:
            raise ToolException("效应量必须大于0", tool_name="power_analysis")
        if not 0 < alpha < 1:
            raise ToolException("alpha必须在0和1之间", tool_name="power_analysis")
        if not 0 < power < 1:
            raise ToolException("power必须在0和1之间", tool_name="power_analysis")

        # 正态分位数
        z_alpha = PowerAnalysis._normal_quantile(
            1 - alpha / 2 if test_type == "two-sided" else 1 - alpha
        )
        z_beta = PowerAnalysis._normal_quantile(power)

        # 样本量公式：n = ((z_alpha + z_beta) / d)²
        n_per_group = ((z_alpha + z_beta) / effect_size) ** 2
        n_per_group = math.ceil(n_per_group)

        # 总样本量
        if paired:
            n_total = n_per_group
        else:
            n_total = n_per_group * 2

        # 计算非中心性参数
        ncp = effect_size * math.sqrt(n_per_group)

        return {
            "n_per_group": n_per_group,
            "n_total": n_total,
            "effect_size": effect_size,
            "effect_size_label": PowerAnalysis._interpret_cohens_d(effect_size),
            "alpha": alpha,
            "power": power,
            "test_type": test_type,
            "paired": paired,
            "non_centrality_parameter": round(ncp, 4),
            "actual_power": round(
                PowerAnalysis._calculate_power_ttest(
                    n_per_group, effect_size, alpha, test_type
                ),
                6,
            ),
        }

    @staticmethod
    def sample_size_anova(
        effect_size: float = 0.25,
        n_groups: int = 3,
        alpha: float = 0.05,
        power: float = 0.8,
    ) -> dict[str, Any]:
        """ANOVA样本量计算

        Args:
            effect_size: Cohen's f效应量
            n_groups: 组数
            alpha: 显著性水平
            power: 统计功效
        """
        if effect_size <= 0:
            raise ToolException("效应量必须大于0", tool_name="power_analysis")
        if n_groups < 2:
            raise ToolException("至少需要2个组", tool_name="power_analysis")

        # 使用F检验的样本量公式
        z_alpha = PowerAnalysis._normal_quantile(1 - alpha / 2)
        z_beta = PowerAnalysis._normal_quantile(power)

        # 近似公式
        lambda_val = n_groups * effect_size**2
        n_per_group = math.ceil(((z_alpha + z_beta) ** 2) / lambda_val)
        n_total = n_per_group * n_groups

        df1 = n_groups - 1
        df2 = n_total - n_groups

        return {
            "n_per_group": n_per_group,
            "n_total": n_total,
            "effect_size_f": effect_size,
            "effect_size_label": PowerAnalysis._interpret_cohens_f(effect_size),
            "eta_squared": round(effect_size**2 / (effect_size**2 + 1), 6),
            "n_groups": n_groups,
            "alpha": alpha,
            "power": power,
            "df1": df1,
            "df2": df2,
            "actual_power": round(
                PowerAnalysis._calculate_power_anova(
                    n_per_group, n_groups, effect_size, alpha
                ),
                6,
            ),
        }

    @staticmethod
    def sample_size_correlation(
        r: float = 0.3,
        alpha: float = 0.05,
        power: float = 0.8,
        test_type: str = "two-sided",
    ) -> dict[str, Any]:
        """相关分析样本量计算"""
        if not 0 < abs(r) < 1:
            raise ToolException(
                "相关系数必须在-1到1之间（不含端点）", tool_name="power_analysis"
            )

        # Fisher z变换
        z_r = 0.5 * math.log((1 + r) / (1 - r))
        z_alpha = PowerAnalysis._normal_quantile(
            1 - alpha / 2 if test_type == "two-sided" else 1 - alpha
        )
        z_beta = PowerAnalysis._normal_quantile(power)

        n = math.ceil(((z_alpha + z_beta) / z_r) ** 2 + 3)

        return {
            "n": n,
            "correlation": r,
            "r_squared": round(r**2, 6),
            "alpha": alpha,
            "power": power,
            "test_type": test_type,
            "fisher_z": round(z_r, 4),
            "actual_power": round(
                PowerAnalysis._calculate_power_correlation(n, r, alpha, test_type), 6
            ),
        }

    @staticmethod
    def sample_size_chi2(
        w: float = 0.3, df: int = 1, alpha: float = 0.05, power: float = 0.8
    ) -> dict[str, Any]:
        """卡方检验样本量计算

        Args:
            w: Cohen's w效应量
            df: 自由度
        """
        if w <= 0:
            raise ToolException("效应量必须大于0", tool_name="power_analysis")

        z_alpha = PowerAnalysis._normal_quantile(1 - alpha / 2)
        z_beta = PowerAnalysis._normal_quantile(power)

        # 近似公式
        n = math.ceil(((z_alpha + z_beta) / w) ** 2)
        n = max(n, df + 1)  # 最小样本量约束

        return {
            "n": n,
            "effect_size_w": w,
            "effect_size_label": PowerAnalysis._interpret_cohens_w(w),
            "df": df,
            "alpha": alpha,
            "power": power,
            "chi2_critical": round(PowerAnalysis._chi2_critical(df, alpha), 4),
        }

    @staticmethod
    def sample_size_proportion(
        p1: float,
        p2: float,
        alpha: float = 0.05,
        power: float = 0.8,
        test_type: str = "two-sided",
    ) -> dict[str, Any]:
        """两比例比较样本量计算"""
        if not 0 < p1 < 1 or not 0 < p2 < 1:
            raise ToolException("比例必须在0和1之间", tool_name="power_analysis")

        z_alpha = PowerAnalysis._normal_quantile(
            1 - alpha / 2 if test_type == "two-sided" else 1 - alpha
        )
        z_beta = PowerAnalysis._normal_quantile(power)

        p_bar = (p1 + p2) / 2
        q_bar = 1 - p_bar

        n_per_group = math.ceil(
            (
                (
                    z_alpha * math.sqrt(2 * p_bar * q_bar)
                    + z_beta * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
                )
                / (p1 - p2)
            )
            ** 2
        )

        return {
            "n_per_group": n_per_group,
            "n_total": n_per_group * 2,
            "p1": p1,
            "p2": p2,
            "difference": round(abs(p1 - p2), 6),
            "alpha": alpha,
            "power": power,
            "test_type": test_type,
        }

    # ========== 功效分析 ==========

    @staticmethod
    def power_curve_ttest(
        effect_size: float = 0.5,
        alpha: float = 0.05,
        max_n: int = 200,
        test_type: str = "two-sided",
    ) -> dict[str, Any]:
        """t检验功效曲线数据"""
        curve = []
        for n in range(5, max_n + 1, 5):
            power = PowerAnalysis._calculate_power_ttest(
                n, effect_size, alpha, test_type
            )
            curve.append({"n": n, "power": round(power, 4)})

        # 找到达到目标功效的样本量
        target_power = 0.8
        target_n = None
        for point in curve:
            if point["power"] >= target_power:
                target_n = point["n"]
                break

        return {
            "effect_size": effect_size,
            "alpha": alpha,
            "target_power": target_power,
            "target_n": target_n,
            "curve": curve,
            "chart_config": {
                "chart_type": "line",
                "x": "n",
                "y": "power",
                "title": f"Power Curve (d={effect_size}, α={alpha})",
                "xlabel": "Sample Size per Group",
                "ylabel": "Statistical Power",
            },
        }

    @staticmethod
    def power_curve_anova(
        effect_size: float = 0.25,
        n_groups: int = 3,
        alpha: float = 0.05,
        max_n: int = 200,
    ) -> dict[str, Any]:
        """ANOVA功效曲线数据"""
        curve = []
        for n in range(5, max_n + 1, 5):
            power = PowerAnalysis._calculate_power_anova(
                n, n_groups, effect_size, alpha
            )
            curve.append(
                {"n_per_group": n, "n_total": n * n_groups, "power": round(power, 4)}
            )

        target_power = 0.8
        target_n = None
        for point in curve:
            if point["power"] >= target_power:
                target_n = point["n_per_group"]
                break

        return {
            "effect_size_f": effect_size,
            "n_groups": n_groups,
            "alpha": alpha,
            "target_power": target_power,
            "target_n_per_group": target_n,
            "curve": curve,
            "chart_config": {
                "chart_type": "line",
                "x": "n_per_group",
                "y": "power",
                "title": f"Power Curve (f={effect_size}, k={n_groups}, α={alpha})",
                "xlabel": "Sample Size per Group",
                "ylabel": "Statistical Power",
            },
        }

    @staticmethod
    def sensitivity_analysis(
        n_range: list[int] = None,
        alpha: float = 0.05,
        power: float = 0.8,
        test_type: str = "ttest",
    ) -> dict[str, Any]:
        """敏感性分析 - 不同样本量下的最小可检测效应量"""
        if n_range is None:
            n_range = list(range(10, 210, 10))

        results = []
        for n in n_range:
            # 反算效应量
            z_alpha = PowerAnalysis._normal_quantile(1 - alpha / 2)
            z_beta = PowerAnalysis._normal_quantile(power)
            d = (z_alpha + z_beta) / math.sqrt(n)
            results.append(
                {
                    "n": n,
                    "min_detectable_effect": round(d, 4),
                    "effect_label": PowerAnalysis._interpret_cohens_d(d),
                }
            )

        return {
            "alpha": alpha,
            "power": power,
            "test_type": test_type,
            "results": results,
            "chart_config": {
                "chart_type": "line",
                "x": "n",
                "y": "min_detectable_effect",
                "title": f"Sensitivity Analysis (α={alpha}, power={power})",
                "xlabel": "Sample Size per Group",
                "ylabel": "Minimum Detectable Effect (Cohen's d)",
            },
        }

    # ========== 内部计算方法 ==========

    @staticmethod
    def _calculate_power_ttest(
        n: int, effect_size: float, alpha: float, test_type: str = "two-sided"
    ) -> float:
        """计算t检验的实际功效"""
        z_alpha = PowerAnalysis._normal_quantile(
            1 - alpha / 2 if test_type == "two-sided" else 1 - alpha
        )
        ncp = effect_size * math.sqrt(n)
        z_crit = z_alpha - ncp
        power = 1 - PowerAnalysis._normal_cdf(z_crit)
        return max(0, min(1, power))

    @staticmethod
    def _calculate_power_anova(
        n_per_group: int, n_groups: int, effect_size: float, alpha: float
    ) -> float:
        """计算ANOVA的实际功效"""
        n_total = n_per_group * n_groups
        df1 = n_groups - 1
        df2 = n_total - n_groups
        lambda_val = n_per_group * n_groups * effect_size**2  # 非中心性参数

        # 近似
        (df1 * (1 + lambda_val / df1)) / df2 if df2 > 0 else 0
        # 简化近似
        z_alpha = PowerAnalysis._normal_quantile(1 - alpha / 2)
        z_power = (
            (math.sqrt(2 * lambda_val) - z_alpha * math.sqrt(2 * df1 - 1))
            / math.sqrt(2 * (df1 + lambda_val) - 1)
            if (2 * (df1 + lambda_val) - 1) > 0
            else 0
        )
        power = PowerAnalysis._normal_cdf(z_power)
        return max(0, min(1, power))

    @staticmethod
    def _calculate_power_correlation(
        n: int, r: float, alpha: float, test_type: str = "two-sided"
    ) -> float:
        """计算相关分析的实际功效"""
        z_r = 0.5 * math.log((1 + r) / (1 - r))
        se = 1 / math.sqrt(n - 3)
        z_alpha = PowerAnalysis._normal_quantile(
            1 - alpha / 2 if test_type == "two-sided" else 1 - alpha
        )
        z_power = z_r / se - z_alpha
        power = PowerAnalysis._normal_cdf(z_power)
        return max(0, min(1, power))

    @staticmethod
    def _chi2_critical(df: int, alpha: float) -> float:
        """χ²临界值近似"""
        # Wilson-Hilferty逆变换
        z = PowerAnalysis._normal_quantile(1 - alpha)
        return df * (1 - 2 / (9 * df) + z * math.sqrt(2 / (9 * df))) ** 3

    @staticmethod
    def _normal_quantile(p: float) -> float:
        """标准正态分位数（Beasley-Springer-Moro算法）"""
        if p <= 0:
            return -8.0
        if p >= 1:
            return 8.0

        # Rational approximation
        a = [
            0,
            -3.969683028665376e01,
            2.209460984245205e02,
            -2.759285104469687e02,
            1.383577518672690e02,
            -3.066479806614716e01,
            2.506628277459239e00,
        ]
        b = [
            0,
            -5.447609879822406e01,
            1.615858368580409e02,
            -1.556989798598866e02,
            6.680131188771972e01,
            -1.328068155288572e01,
        ]
        c = [
            0,
            -7.784894002430293e-03,
            -3.223964580411365e-01,
            -2.400758277161838e00,
            -2.549732539343734e00,
            4.374664141464968e00,
            2.938163982698783e00,
        ]
        d = [
            0,
            7.784695709041462e-03,
            3.224671290700398e-01,
            2.445134137142996e00,
            3.754408661907416e00,
        ]

        p_low = 0.02425
        p_high = 1 - p_low

        if p < p_low:
            q = math.sqrt(-2 * math.log(p))
            x = (
                ((((c[1] * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) * q + c[6]
            ) / ((((d[1] * q + d[2]) * q + d[3]) * q + d[4]) * q + 1)
        elif p <= p_high:
            q = p - 0.5
            r = q * q
            x = (
                (((((a[1] * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * r + a[6])
                * q
                / (((((b[1] * r + b[2]) * r + b[3]) * r + b[4]) * r + b[5]) * r + 1)
            )
        else:
            q = math.sqrt(-2 * math.log(1 - p))
            x = -(
                ((((c[1] * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) * q + c[6]
            ) / ((((d[1] * q + d[2]) * q + d[3]) * q + d[4]) * q + 1)

        return x

    @staticmethod
    def _normal_cdf(z: float) -> float:
        """标准正态CDF"""
        if z < -8:
            return 0.0
        if z > 8:
            return 1.0

        a1 = 0.254829592
        a2 = -0.284496736
        a3 = 1.421413741
        a4 = -1.453152027
        a5 = 1.061405429
        p = 0.3275911

        sign = 1 if z >= 0 else -1
        z = abs(z)
        t = 1.0 / (1.0 + p * z)
        y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(
            -z * z / 2.0
        )

        return 0.5 * (1.0 + sign * y)

    @staticmethod
    def _interpret_cohens_d(d: float) -> str:
        """解释Cohen's d效应量"""
        d = abs(d)
        if d < 0.2:
            return "negligible"
        elif d < 0.5:
            return "small"
        elif d < 0.8:
            return "medium"
        else:
            return "large"

    @staticmethod
    def _interpret_cohens_f(f: float) -> str:
        """解释Cohen's f效应量"""
        f = abs(f)
        if f < 0.1:
            return "negligible"
        elif f < 0.25:
            return "small"
        elif f < 0.4:
            return "medium"
        else:
            return "large"

    @staticmethod
    def _interpret_cohens_w(w: float) -> str:
        """解释Cohen's w效应量"""
        w = abs(w)
        if w < 0.1:
            return "negligible"
        elif w < 0.3:
            return "small"
        elif w < 0.5:
            return "medium"
        else:
            return "large"

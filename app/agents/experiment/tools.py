from typing import Any

import numpy as np

from app.utils.exceptions import ToolException
from app.utils.logger import get_logger

logger = get_logger("tools.experiment")


class ExperimentTools:
    """实验工具集"""

    # 常见实验设计类型
    DESIGN_TYPES = {
        "between": "被试间设计 - 不同组接受不同处理",
        "within": "被试内设计 - 所有组接受所有处理",
        "mixed": "混合设计 - 部分因素被试间，部分被试内",
        "factorial": "因子设计 - 多因素组合",
        "repeated": "重复测量设计 - 同一被试多次测量",
    }

    # 常见统计检验方法
    STATISTICAL_TESTS = {
        "ttest_independent": "独立样本t检验 - 两组均值比较",
        "ttest_paired": "配对样本t检验 - 前后测比较",
        "anova_one": "单因素方差分析 - 多组均值比较",
        "anova_two": "双因素方差分析 - 两因素交互作用",
        "chi_square": "卡方检验 - 分类变量关联",
        "correlation": "相关分析 - 变量关系",
        "regression": "回归分析 - 预测关系",
    }

    @staticmethod
    def design_experiment(
        goal: str, variables: list[str], design_type: str = "between"
    ) -> dict[str, Any]:
        """设计实验方案"""
        logger.info(f"设计实验: {goal}, 类型: {design_type}")

        if design_type not in ExperimentTools.DESIGN_TYPES:
            raise ToolException(
                (
                    f"不支持的设计类型: {design_type}，支持: "
                    f"{list(ExperimentTools.DESIGN_TYPES.keys())}"
                ),
                tool_name="design_experiment",
            )

        # 基础实验设计
        design = {
            "goal": goal,
            "design_type": design_type,
            "design_description": ExperimentTools.DESIGN_TYPES[design_type],
            "variables": {
                "independent": variables[:1] if variables else [],
                "dependent": variables[1:2] if len(variables) > 1 else [],
                "control": variables[2:] if len(variables) > 2 else [],
            },
            "groups": ExperimentTools._generate_groups(design_type, variables),
            "steps": ExperimentTools._generate_steps(design_type),
            "sample_size_recommendation": ExperimentTools._recommend_sample_size(
                design_type
            ),
            "ethical_considerations": [
                "获取伦理委员会批准",
                "获取参与者知情同意",
                "确保数据匿名化",
                "允许参与者随时退出",
            ],
        }

        return design

    @staticmethod
    def _generate_groups(
        design_type: str, variables: list[str]
    ) -> list[dict[str, Any]]:
        """生成实验组"""
        if design_type == "between":
            return [
                {"name": "控制组", "description": "不接受处理"},
                {"name": "实验组", "description": "接受处理"},
            ]
        elif design_type == "within":
            return [
                {"name": "前测", "description": "处理前测量"},
                {"name": "后测", "description": "处理后测量"},
            ]
        elif design_type == "factorial":
            groups = []
            for var in variables[:2]:
                groups.append({"name": f"{var}_水平1", "description": f"{var} 低水平"})
                groups.append({"name": f"{var}_水平2", "description": f"{var} 高水平"})
            return groups
        else:
            return [
                {"name": "组1", "description": "条件A"},
                {"name": "组2", "description": "条件B"},
            ]

    @staticmethod
    def _generate_steps(design_type: str) -> list[str]:
        """生成实验步骤"""
        base_steps = [
            "1. 明确研究假设",
            "2. 确定变量和测量指标",
            "3. 选择实验设计类型",
            "4. 确定样本量",
            "5. 准备实验材料",
            "6. 进行预实验",
            "7. 正式数据收集",
            "8. 数据清洗和分析",
            "9. 结果解释和报告",
        ]

        if design_type == "between":
            base_steps.insert(4, "随机分配被试到各组")
        elif design_type == "within":
            base_steps.insert(4, "平衡处理顺序")

        return base_steps

    @staticmethod
    def _recommend_sample_size(design_type: str) -> dict[str, Any]:
        """推荐样本量"""
        recommendations = {
            "between": {"min": 30, "recommended": 50, "per_group": 25},
            "within": {"min": 20, "recommended": 30, "per_condition": 15},
            "mixed": {"min": 40, "recommended": 60, "per_group": 20},
            "factorial": {"min": 20, "recommended": 30, "per_cell": 15},
            "repeated": {"min": 15, "recommended": 25, "per_timepoint": 15},
        }

        return recommendations.get(design_type, {"min": 30, "recommended": 50})

    @staticmethod
    def select_statistical_test(
        variable_type: str, group_count: int, paired: bool = False
    ) -> dict[str, Any]:
        """选择统计检验方法"""
        logger.info(
            f"选择统计检验: 变量类型={variable_type}, 组数={group_count}, 配对={paired}"
        )

        if variable_type == "continuous":
            if group_count == 2:
                test = "ttest_paired" if paired else "ttest_independent"
            else:
                test = "anova_one"
        elif variable_type == "categorical":
            test = "chi_square"
        else:
            test = "correlation"

        return {
            "recommended_test": test,
            "description": ExperimentTools.STATISTICAL_TESTS.get(test, ""),
            "assumptions": ExperimentTools._get_test_assumptions(test),
            "alternatives": ExperimentTools._get_alternative_tests(test),
        }

    @staticmethod
    def _get_test_assumptions(test: str) -> list[str]:
        """获取检验假设"""
        assumptions = {
            "ttest_independent": ["正态性", "方差齐性", "独立观测"],
            "ttest_paired": ["差值正态性", "配对观测"],
            "anova_one": ["正态性", "方差齐性", "独立观测"],
            "anova_two": ["正态性", "方差齐性", "独立观测"],
            "chi_square": ["期望频数>5", "独立观测"],
            "correlation": ["线性关系", "正态性", "无异常值"],
            "regression": ["线性", "正态性", "方差齐性", "独立性"],
        }
        return assumptions.get(test, [])

    @staticmethod
    def _get_alternative_tests(test: str) -> list[str]:
        """获取替代检验方法"""
        alternatives = {
            "ttest_independent": ["Mann-Whitney U检验", "Welch t检验"],
            "ttest_paired": ["Wilcoxon符号秩检验"],
            "anova_one": ["Kruskal-Wallis检验"],
            "chi_square": ["Fisher精确检验"],
            "correlation": ["Spearman相关", "Kendall相关"],
            "regression": ["稳健回归", "分位数回归"],
        }
        return alternatives.get(test, [])

    @staticmethod
    def optimize_parameters(
        historical_data: list[dict[str, Any]],
        target_metric: str = "score",
        method: str = "grid",
    ) -> dict[str, Any]:
        """优化参数"""
        logger.info(f"参数优化: 方法={method}, 数据量={len(historical_data)}")

        if not historical_data:
            return {"optimized_params": {}, "confidence": 0, "message": "无历史数据"}

        # 提取参数和结果
        all_params: dict[str, list[Any]] = {}
        best_score = float("-inf")
        best_params = {}

        for data in historical_data:
            params = data.get("params", {})
            score = data.get(target_metric, 0)

            # 记录最佳
            if score > best_score:
                best_score = score
                best_params = params

            # 收集所有参数值
            for param, value in params.items():
                if param not in all_params:
                    all_params[param] = []
                all_params[param].append((value, score))

        # 分析每个参数的最佳值
        optimized = {}
        param_importance = {}

        for param, values in all_params.items():
            # 按分数排序
            sorted_values = sorted(values, key=lambda x: x[1], reverse=True)
            optimized[param] = sorted_values[0][0]

            # 计算参数重要性（分数方差）
            scores = [v[1] for v in values]
            param_importance[param] = float(np.std(scores)) if len(scores) > 1 else 0

        # 归一化重要性
        total_importance = sum(param_importance.values())
        if total_importance > 0:
            param_importance = {
                k: v / total_importance for k, v in param_importance.items()
            }

        return {
            "optimized_params": optimized,
            "best_historical_params": best_params,
            "best_score": float(best_score),
            "param_importance": param_importance,
            "confidence": min(0.9, len(historical_data) / 20),  # 数据越多置信度越高
            "method": method,
        }

    @staticmethod
    def predict_result(
        params: dict[str, Any],
        historical_data: list[dict[str, Any]],
        target_metric: str = "score",
    ) -> dict[str, Any]:
        """预测结果"""
        logger.info(f"预测结果: {params}")

        if not historical_data:
            return {"prediction": {}, "confidence": 0, "message": "无历史数据"}

        # 计算相似度
        predictions = []
        weights = []

        for data in historical_data:
            data_params = data.get("params", {})
            similarity = ExperimentTools._calculate_similarity(params, data_params)

            if similarity > 0.3:  # 相似度阈值
                predictions.append(data.get(target_metric, 0))
                weights.append(similarity)

        if not predictions:
            return {
                "prediction": {target_metric: 0},
                "confidence": 0,
                "message": "无相似历史数据",
            }

        # 加权平均预测（新变量名：list 与 ndarray 不共用一个绑定）
        weights_arr = np.asarray(weights, dtype=float)
        predictions_arr = np.asarray(predictions, dtype=float)
        weighted_pred = np.average(predictions_arr, weights=weights_arr)

        # 计算置信区间
        std = np.std(predictions)
        confidence_interval = {
            "lower": float(weighted_pred - 1.96 * std),
            "upper": float(weighted_pred + 1.96 * std),
        }

        return {
            "prediction": {target_metric: float(weighted_pred)},
            "confidence": float(np.mean(weights)),
            "confidence_interval": confidence_interval,
            "based_on_samples": len(predictions),
        }

    @staticmethod
    def _calculate_similarity(
        params1: dict[str, Any], params2: dict[str, Any]
    ) -> float:
        """计算参数相似度"""
        common_keys = set(params1.keys()) & set(params2.keys())
        if not common_keys:
            return 0.0

        match_count = 0
        for key in common_keys:
            v1 = params1[key]
            v2 = params2[key]

            # 数值比较
            if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                if v1 == 0 and v2 == 0:
                    match_count += 1
                else:
                    diff = abs(v1 - v2) / max(abs(v1), abs(v2))
                    if diff < 0.25:  # 25%以内视为相似，兼顾数值波动与可用样本量
                        match_count += 1
            # 字符串比较
            elif v1 == v2:
                match_count += 1

        return match_count / len(common_keys)

    @staticmethod
    def calculate_power_analysis(
        effect_size: float,
        alpha: float = 0.05,
        power: float = 0.8,
        test_type: str = "two-sided",
        paired: bool = False,
    ) -> dict[str, Any]:
        """功效分析 - 委托 PowerAnalysis 服务计算精确样本量与实际功效

        向后兼容：保留 sample_size_per_group / total_sample_size / interpretation 键。
        """
        logger.info(
            f"功效分析: effect_size={effect_size}, alpha={alpha}, power={power}"
        )

        # 延迟导入避免循环依赖
        from app.services.power_analysis import PowerAnalysis

        try:
            pa = PowerAnalysis.sample_size_ttest(
                effect_size=effect_size,
                alpha=alpha,
                power=power,
                test_type=test_type,
                paired=paired,
            )
        except Exception as e:
            logger.warning(f"PowerAnalysis 服务调用失败，回退到简化公式: {e}")
            # 回退：简化公式
            z_alpha = 1.96
            z_beta = 0.84
            n_per_group = ((z_alpha + z_beta) ** 2 * 2) / (effect_size**2)
            return {
                "effect_size": effect_size,
                "alpha": alpha,
                "power": power,
                "sample_size_per_group": int(np.ceil(n_per_group)),
                "total_sample_size": int(np.ceil(n_per_group * 2)),
                "interpretation": ExperimentTools._interpret_effect_size(effect_size),
            }

        return {
            "effect_size": effect_size,
            "alpha": alpha,
            "power": power,
            "test_type": test_type,
            "paired": paired,
            "sample_size_per_group": pa["n_per_group"],
            "total_sample_size": pa["n_total"],
            "actual_power": pa.get("actual_power"),
            "effect_size_label": pa.get("effect_size_label"),
            "non_centrality_parameter": pa.get("non_centrality_parameter"),
            "interpretation": ExperimentTools._interpret_effect_size(effect_size),
        }

    @staticmethod
    def power_curve(
        effect_size: float = 0.5,
        alpha: float = 0.05,
        max_n: int = 200,
        test_type: str = "two-sided",
    ) -> dict[str, Any]:
        """功效曲线 - 不同样本量下的统计功效，委托 PowerAnalysis 服务"""
        from app.services.power_analysis import PowerAnalysis

        return PowerAnalysis.power_curve_ttest(
            effect_size=effect_size,
            alpha=alpha,
            max_n=max_n,
            test_type=test_type,
        )

    @staticmethod
    def sensitivity_analysis(
        n_range: list[int] | None = None,
        alpha: float = 0.05,
        power: float = 0.8,
        test_type: str = "ttest",
    ) -> dict[str, Any]:
        """敏感性分析 - 不同样本量下的最小可检测效应量，委托 PowerAnalysis 服务"""
        from app.services.power_analysis import PowerAnalysis

        return PowerAnalysis.sensitivity_analysis(
            n_range=n_range,
            alpha=alpha,
            power=power,
            test_type=test_type,
        )

    @staticmethod
    def _interpret_effect_size(effect_size: float) -> str:
        """解释效应量（Cohen's d 约定：0.2 小 / 0.5 中 / 0.8 大）"""
        if effect_size <= 0.2:
            return "小效应"
        elif effect_size < 0.5:
            return "中等效应"
        elif effect_size < 0.8:
            return "大效应"
        else:
            return "非常大的效应"

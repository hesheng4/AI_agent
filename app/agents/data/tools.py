from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]  # pandas-stubs 未安装

from app.utils.exceptions import ToolException
from app.utils.logger import get_logger

logger = get_logger("tools.data")

# 支持的文件格式
SUPPORTED_FORMATS = {".csv", ".xlsx", ".xls", ".json", ".parquet"}

# 上传目录
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


class DataTools:
    """数据工具集"""

    @staticmethod
    async def load_data(file_path: str) -> pd.DataFrame:
        """加载数据文件"""
        logger.info(f"加载数据: {file_path}")

        path = Path(file_path)

        if not path.exists():
            raise ToolException(f"文件不存在: {file_path}", tool_name="load_data")

        if path.suffix not in SUPPORTED_FORMATS:
            raise ToolException(
                f"不支持的文件格式: {path.suffix}，支持: {SUPPORTED_FORMATS}",
                tool_name="load_data",
            )

        try:
            if path.suffix == ".csv":
                df = pd.read_csv(path)
            elif path.suffix in (".xlsx", ".xls"):
                df = pd.read_excel(path)
            elif path.suffix == ".json":
                df = pd.read_json(path)
            elif path.suffix == ".parquet":
                df = pd.read_parquet(path)
            else:
                raise ToolException(
                    f"不支持的格式: {path.suffix}", tool_name="load_data"
                )

            logger.info(f"数据加载成功: {df.shape[0]}行 x {df.shape[1]}列")
            return df

        except pd.errors.EmptyDataError:
            raise ToolException("文件为空", tool_name="load_data")
        except pd.errors.ParserError as e:
            raise ToolException(f"文件解析失败: {str(e)}", tool_name="load_data")
        except Exception as e:
            logger.error(f"数据加载失败: {e}", exc_info=True)
            raise ToolException(f"数据加载失败: {str(e)}", tool_name="load_data")

    @staticmethod
    def clean_data(df: pd.DataFrame) -> pd.DataFrame:
        """清洗数据"""
        logger.info(f"清洗数据: {df.shape}")

        # 去重
        original_len = len(df)
        df = df.drop_duplicates()
        if len(df) < original_len:
            logger.info(f"去重: {original_len} -> {len(df)}")

        # 填充缺失值
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        categorical_cols = df.select_dtypes(include=["object", "string"]).columns

        # 数值列用中位数填充
        for col in numeric_cols:
            missing = df[col].isna().sum()
            if missing > 0:
                median_val = df[col].median()
                df[col] = df[col].fillna(median_val)
                logger.debug(f"{col}: 用中位数 {median_val} 填充 {missing} 个缺失值")

        # 分类列用众数填充
        for col in categorical_cols:
            missing = df[col].isna().sum()
            if missing > 0:
                mode_val = df[col].mode()
                fill_val = mode_val[0] if not mode_val.empty else "未知"
                df[col] = df[col].fillna(fill_val)
                logger.debug(f"{col}: 用众数 '{fill_val}' 填充 {missing} 个缺失值")

        logger.info(f"数据清洗完成: {df.shape}")
        return df

    @staticmethod
    def descriptive_statistics(df: pd.DataFrame) -> dict[str, Any]:
        """描述性统计"""
        logger.info("计算描述性统计")

        stats = {}
        numeric_cols = df.select_dtypes(include=[np.number]).columns

        for col in numeric_cols:
            stats[col] = {
                "count": int(df[col].count()),
                "mean": float(df[col].mean()),
                "std": float(df[col].std()),
                "min": float(df[col].min()),
                "25%": float(df[col].quantile(0.25)),
                "median": float(df[col].median()),
                "75%": float(df[col].quantile(0.75)),
                "max": float(df[col].max()),
                "skew": float(df[col].skew()),
                "kurtosis": float(df[col].kurtosis()),
            }

        # 分类列统计
        categorical_stats = {}
        categorical_cols = df.select_dtypes(include=["object", "string"]).columns
        for col in categorical_cols:
            value_counts = df[col].value_counts()
            categorical_stats[col] = {
                "unique": int(df[col].nunique()),
                "top": str(value_counts.index[0]) if len(value_counts) > 0 else None,
                "freq": int(value_counts.iloc[0]) if len(value_counts) > 0 else 0,
            }

        return {
            "numeric": stats,
            "categorical": categorical_stats,
            "shape": list(df.shape),
        }

    @staticmethod
    def correlation_analysis(
        df: pd.DataFrame, method: str = "pearson"
    ) -> dict[str, Any]:
        """相关性分析"""
        logger.info(f"相关性分析: method={method}")

        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) < 2:
            # 列数不足时返回错误信息，便于上层统一处理与前端展示
            return {
                "error": "至少需要2个数值列进行相关性分析",
                "numeric_columns_found": len(numeric_cols),
            }

        corr_matrix = df[numeric_cols].corr(method=method)

        # 找出高相关性对
        high_corr = []
        for i in range(len(corr_matrix.columns)):
            for j in range(i + 1, len(corr_matrix.columns)):
                col1 = corr_matrix.columns[i]
                col2 = corr_matrix.columns[j]
                corr_val = corr_matrix.iloc[i, j]
                if abs(corr_val) > 0.7:
                    high_corr.append(
                        {"col1": col1, "col2": col2, "correlation": float(corr_val)}
                    )

        return {
            "matrix": corr_matrix.to_dict(),
            "high_correlations": high_corr,
            "method": method,
        }

    @staticmethod
    def outlier_detection(df: pd.DataFrame, method: str = "iqr") -> dict[str, Any]:
        """异常值检测"""
        logger.info(f"异常值检测: method={method}")

        numeric_cols = df.select_dtypes(include=[np.number]).columns
        outliers: dict[str, dict[str, Any]] = {}

        for col in numeric_cols:
            if method == "iqr":
                Q1 = df[col].quantile(0.25)  # noqa: N806
                Q3 = df[col].quantile(0.75)  # noqa: N806
                IQR = Q3 - Q1  # noqa: N806
                lower = Q1 - 1.5 * IQR
                upper = Q3 + 1.5 * IQR
                outlier_mask = (df[col] < lower) | (df[col] > upper)
            elif method == "zscore":
                mean = df[col].mean()
                std = df[col].std()
                z_scores = np.abs((df[col] - mean) / std)
                outlier_mask = z_scores > 3
                lower = mean - 3 * std
                upper = mean + 3 * std
            else:
                raise ToolException(
                    f"不支持的方法: {method}", tool_name="outlier_detection"
                )

            outlier_count = outlier_mask.sum()
            if outlier_count > 0:
                outliers[col] = {
                    "count": int(outlier_count),
                    "percentage": float(outlier_count / len(df) * 100),
                    "lower_bound": float(lower),
                    "upper_bound": float(upper),
                    "outlier_values": [
                        float(v) for v in df.loc[outlier_mask, col].tolist()[:10]
                    ],
                }

        return {
            "method": method,
            "outliers": outliers,
            "total_outlier_rows": int(sum(v["count"] for v in outliers.values())),
        }

    @staticmethod
    def group_comparison(
        df: pd.DataFrame, group_col: str, value_col: str
    ) -> dict[str, Any]:
        """分组比较"""
        logger.info(f"分组比较: group={group_col}, value={value_col}")

        if group_col not in df.columns:
            raise ToolException(f"列不存在: {group_col}", tool_name="group_comparison")
        if value_col not in df.columns:
            raise ToolException(f"列不存在: {value_col}", tool_name="group_comparison")

        groups = df.groupby(group_col)[value_col]

        results = {}
        for name, group in groups:
            results[str(name)] = {
                "count": int(group.count()),
                "mean": float(group.mean()),
                "std": float(group.std()),
                "min": float(group.min()),
                "max": float(group.max()),
            }

        return {"group_col": group_col, "value_col": value_col, "groups": results}

    @staticmethod
    async def save_data(df: pd.DataFrame, file_path: str) -> str:
        """保存数据"""
        logger.info(f"保存数据: {file_path}")

        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if path.suffix == ".csv":
                df.to_csv(path, index=False)
            elif path.suffix in (".xlsx", ".xls"):
                df.to_excel(path, index=False)
            elif path.suffix == ".json":
                df.to_json(path, orient="records", force_ascii=False)
            elif path.suffix == ".parquet":
                df.to_parquet(path, index=False)
            else:
                raise ToolException(
                    f"不支持的格式: {path.suffix}", tool_name="save_data"
                )

            logger.info(f"数据保存成功: {path}")
            return str(path)

        except Exception as e:
            logger.error(f"数据保存失败: {e}", exc_info=True)
            raise ToolException(f"数据保存失败: {str(e)}", tool_name="save_data")

    @staticmethod
    def get_data_summary(df: pd.DataFrame) -> dict[str, Any]:
        """获取数据概览"""
        return {
            "shape": list(df.shape),
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "missing": {col: int(val) for col, val in df.isnull().sum().items()},
            "memory_usage": f"{df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB",
        }

    # ========== 统计增强分析（委托给 StatisticsEnhancer）==========

    @staticmethod
    def regression_analysis(
        df: pd.DataFrame, x_cols: list[str], y_col: str, multiple: bool = False
    ) -> dict[str, Any]:
        """回归分析 - 简单线性回归或多元线性回归"""
        from app.services.statistics import StatisticsEnhancer

        if not x_cols or not isinstance(x_cols, list):
            return {"error": "x_cols 必须是非空列表"}
        if not y_col:
            return {"error": "缺少 y_col 参数"}

        missing_cols = [c for c in x_cols + [y_col] if c not in df.columns]
        if missing_cols:
            return {"error": f"列不存在: {missing_cols}"}

        for col in x_cols + [y_col]:
            if not pd.api.types.is_numeric_dtype(df[col]):
                return {"error": f"列 {col} 不是数值类型"}

        subset = df[x_cols + [y_col]].dropna()
        if len(subset) < 3:
            return {"error": "回归分析至少需要3个有效数据点"}

        try:
            y = subset[y_col].astype(float).tolist()
            if multiple:
                x_vars = [subset[c].astype(float).tolist() for c in x_cols]
                return StatisticsEnhancer.multiple_regression(x_vars, y)
            else:
                if len(x_cols) != 1:
                    return {
                        "error": "简单线性回归需要恰好1个自变量，或设置 multiple=True"
                    }
                x = subset[x_cols[0]].astype(float).tolist()
                return StatisticsEnhancer.linear_regression(x, y)
        except Exception as e:
            logger.error(f"回归分析失败: {e}", exc_info=True)
            return {"error": f"回归分析失败: {str(e)}"}

    @staticmethod
    def anova_analysis(
        df: pd.DataFrame,
        group_col: str,
        value_col: str,
        two_way: bool = False,
        factor_b: str | None = None,
    ) -> dict[str, Any]:
        """方差分析 - 单因素或双因素"""
        from app.services.statistics import StatisticsEnhancer

        if not group_col or not value_col:
            return {"error": "缺少 group_col 或 value_col 参数"}

        required_cols = [group_col, value_col]
        if two_way:
            if not factor_b:
                return {"error": "双因素方差分析需要 factor_b 参数"}
            required_cols.append(factor_b)

        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            return {"error": f"列不存在: {missing_cols}"}

        if not pd.api.types.is_numeric_dtype(df[value_col]):
            return {"error": f"列 {value_col} 不是数值类型"}

        try:
            if two_way:
                subset = df[[group_col, factor_b, value_col]].dropna()
                if len(subset) < 4:
                    return {"error": "双因素方差分析数据不足"}
                data_list = [
                    {
                        group_col: str(row[group_col]),
                        factor_b: str(row[factor_b]),
                        value_col: float(row[value_col]),
                    }
                    for _, row in subset.iterrows()
                ]
                return StatisticsEnhancer.two_way_anova(
                    data_list, group_col, factor_b, value_col
                )
            else:
                subset = df[[group_col, value_col]].dropna()
                groups: dict[str, list[float]] = {}
                for name, group in subset.groupby(group_col):
                    groups[str(name)] = group[value_col].astype(float).tolist()
                if len(groups) < 2:
                    return {"error": "ANOVA至少需要2个组"}
                return StatisticsEnhancer.one_way_anova(groups)
        except Exception as e:
            logger.error(f"方差分析失败: {e}", exc_info=True)
            return {"error": f"方差分析失败: {str(e)}"}

    @staticmethod
    def nonparametric_test(
        df: pd.DataFrame, group_col: str, value_col: str, test: str = "mannwhitney"
    ) -> dict[str, Any]:
        """非参数检验 - Mann-Whitney U 或 Kruskal-Wallis H"""
        from app.services.statistics import StatisticsEnhancer

        if not group_col or not value_col:
            return {"error": "缺少 group_col 或 value_col 参数"}

        missing_cols = [c for c in [group_col, value_col] if c not in df.columns]
        if missing_cols:
            return {"error": f"列不存在: {missing_cols}"}

        if not pd.api.types.is_numeric_dtype(df[value_col]):
            return {"error": f"列 {value_col} 不是数值类型"}

        if test not in ("mannwhitney", "kruskal"):
            return {
                "error": f"不支持的非参数检验方法: {test}，支持: mannwhitney, kruskal"
            }

        try:
            subset = df[[group_col, value_col]].dropna()
            groups: dict[str, list[float]] = {}
            for name, group in subset.groupby(group_col):
                groups[str(name)] = group[value_col].astype(float).tolist()

            if test == "mannwhitney":
                if len(groups) != 2:
                    return {"error": "Mann-Whitney U检验需要恰好2个组"}
                group_values = list(groups.values())
                return StatisticsEnhancer.mann_whitney_u(
                    group_values[0], group_values[1]
                )
            else:  # kruskal
                if len(groups) < 2:
                    return {"error": "Kruskal-Wallis检验至少需要2个组"}
                return StatisticsEnhancer.kruskal_wallis(groups)
        except Exception as e:
            logger.error(f"非参数检验失败: {e}", exc_info=True)
            return {"error": f"非参数检验失败: {str(e)}"}

    @staticmethod
    def survival_analysis(
        df: pd.DataFrame, time_col: str, event_col: str, group_col: str | None = None
    ) -> dict[str, Any]:
        """生存分析 - Kaplan-Meier 估计"""
        from app.services.statistics import StatisticsEnhancer

        if not time_col or not event_col:
            return {"error": "缺少 time_col 或 event_col 参数"}

        required_cols = [time_col, event_col]
        if group_col:
            required_cols.append(group_col)

        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            return {"error": f"列不存在: {missing_cols}"}

        if not pd.api.types.is_numeric_dtype(df[time_col]):
            return {"error": f"列 {time_col} 不是数值类型"}

        try:
            subset = df[required_cols].dropna()
            if len(subset) < 2:
                return {"error": "生存分析至少需要2个观测值"}

            times = subset[time_col].astype(float).tolist()
            events = (
                pd.to_numeric(subset[event_col], errors="coerce").astype(int).tolist()
            )

            group = None
            if group_col:
                group = subset[group_col].astype(str).tolist()

            return StatisticsEnhancer.kaplan_meier(times, events, group)
        except Exception as e:
            logger.error(f"生存分析失败: {e}", exc_info=True)
            return {"error": f"生存分析失败: {str(e)}"}

    @staticmethod
    def chi_square_test(df: pd.DataFrame, row_col: str, col_col: str) -> dict[str, Any]:
        """卡方独立性检验 - 从两列构造列联表"""
        from app.services.statistics import StatisticsEnhancer

        if not row_col or not col_col:
            return {"error": "缺少 row_col 或 col_col 参数"}

        missing_cols = [c for c in [row_col, col_col] if c not in df.columns]
        if missing_cols:
            return {"error": f"列不存在: {missing_cols}"}

        try:
            subset = df[[row_col, col_col]].dropna()
            if len(subset) < 2:
                return {"error": "卡方检验数据不足"}

            contingency = pd.crosstab(subset[row_col], subset[col_col])
            if contingency.shape[0] < 2 or contingency.shape[1] < 2:
                return {"error": "列联表至少需要2行2列"}

            observed = contingency.values.tolist()
            return StatisticsEnhancer.chi_square_test(observed)
        except Exception as e:
            logger.error(f"卡方检验失败: {e}", exc_info=True)
            return {"error": f"卡方检验失败: {str(e)}"}

import json
import math
from typing import Any, cast

import numpy as np
import pandas as pd  # type: ignore[import-untyped]  # pandas-stubs 未安装

from app.agents.base import BaseAgent
from app.agents.data.prompts import ANALYSIS_SYSTEM_PROMPT, VISUALIZATION_SYSTEM_PROMPT
from app.agents.data.tools import DataTools
from app.utils.exceptions import AgentException, ValidationException
from app.utils.logger import get_logger

logger = get_logger("agent.data")


def _sanitize_for_json(obj: Any) -> Any:
    """递归清洗结果中的 NaN / numpy 类型，确保 JSON 可序列化（调用点按 dict 使用）"""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        return None if math.isnan(v) or math.isinf(v) else v
    if isinstance(obj, float):
        return None if math.isnan(obj) or math.isinf(obj) else obj
    return obj


class DataAgent(BaseAgent):
    # 数据分析解释属半确定性任务，低温保证结论可复现
    _DETERMINISTIC_TEMPERATURE = 0.0

    def __init__(self) -> None:
        super().__init__(
            name="data",
            tools=[
                "load_data",
                "clean_data",
                "descriptive_statistics",
                "correlation_analysis",
                "outlier_detection",
                "group_comparison",
            ],
        )
        self.tools_handler = DataTools()
        # 缓存任务分派表，统一 dict 风格
        self._handlers = {
            "analyze": self.analyze,
            "visualize": self.visualize,
            "upload": self.upload,
            "summary": self.get_summary,
        }

    async def process(self, request: dict[str, Any]) -> dict[str, Any]:
        task = str(request.get("task", ""))
        handler = self._handlers.get(task)
        if handler:
            return await handler(request)
        raise AgentException(
            f"未知任务类型: {task!r}，支持: analyze/visualize/upload/summary",
            self.name,
        )

    async def analyze(self, request: dict[str, Any]) -> dict[str, Any]:
        data = request.get("data")
        analysis_type = request.get("analysis_type", "descriptive")

        if data is None:
            raise ValidationException("缺少data字段")

        # 转换为DataFrame，按类型分派
        if isinstance(data, str):
            df = await self.tools_handler.load_data(data)
        elif isinstance(data, (list, dict)):
            df = pd.DataFrame(data)
        else:
            raise ValidationException(
                f"data 字段类型不支持: {type(data).__name__}，需 str/list/dict"
            )

        if df.empty:
            raise ValidationException("数据为空")

        # 清洗数据
        df = self.tools_handler.clean_data(df)

        # 根据分析类型执行
        if analysis_type == "descriptive":
            results = self.tools_handler.descriptive_statistics(df)
        elif analysis_type == "correlation":
            results = self.tools_handler.correlation_analysis(df)
        elif analysis_type == "outlier":
            results = self.tools_handler.outlier_detection(df)
        elif analysis_type == "group":
            group_col = request.get("group_col")
            value_col = request.get("value_col")
            if not group_col or not value_col:
                raise ValidationException("分组分析需要group_col和value_col参数")
            results = self.tools_handler.group_comparison(df, group_col, value_col)
        elif analysis_type == "regression":
            x_cols: Any = request.get("x_cols")
            y_col: Any = request.get("y_col")
            multiple = request.get("multiple", False)
            results = self.tools_handler.regression_analysis(
                df, x_cols, y_col, multiple=multiple
            )
        elif analysis_type == "anova":
            group_col = request.get("group_col")
            value_col = request.get("value_col")
            two_way = request.get("two_way", False)
            factor_b = request.get("factor_b")
            if not group_col or not value_col:
                raise ValidationException("方差分析需要group_col和value_col参数")
            results = self.tools_handler.anova_analysis(
                df, group_col, value_col, two_way=two_way, factor_b=factor_b
            )
        elif analysis_type == "nonparametric":
            group_col = request.get("group_col")
            value_col = request.get("value_col")
            test = request.get("test", "mannwhitney")
            if not group_col or not value_col:
                raise ValidationException("非参数检验需要group_col和value_col参数")
            results = self.tools_handler.nonparametric_test(
                df, group_col, value_col, test=test
            )
        elif analysis_type == "survival":
            time_col = request.get("time_col")
            event_col = request.get("event_col")
            group_col = request.get("group_col")
            if not time_col or not event_col:
                raise ValidationException("生存分析需要time_col和event_col参数")
            results = self.tools_handler.survival_analysis(
                df, time_col, event_col, group_col=group_col
            )
        elif analysis_type == "chi2":
            row_col = request.get("row_col")
            col_col = request.get("col_col")
            if not row_col or not col_col:
                raise ValidationException("卡方检验需要row_col和col_col参数")
            results = self.tools_handler.chi_square_test(df, row_col, col_col)
        else:
            results = {"error": f"不支持的分析类型: {analysis_type}"}

        # LLM解释（先清洗结果避免 NaN 导致 JSON 序列化失败）
        results = _sanitize_for_json(results)
        results_json = json.dumps(results, ensure_ascii=False, default=str)
        prompt = f"请用中文解释以下数据分析结果，给出专业见解：\n{results_json}"
        explanation = await self.call_llm(
            prompt,
            ANALYSIS_SYSTEM_PROMPT,
            temperature=self._DETERMINISTIC_TEMPERATURE,
        )

        return {
            "status": "success",
            "results": results,
            "explanation": explanation,
            "data_shape": list(df.shape),
            "analysis_type": analysis_type,
        }

    async def visualize(self, request: dict[str, Any]) -> dict[str, Any]:
        data = request.get("data")
        chart_type = request.get("chart_type", "bar")

        if data is None:
            raise ValidationException("缺少data字段")

        df = self._to_dataframe(data)

        prompt = (
            f"数据列：{list(df.columns)}，数据类型：{df.dtypes.to_dict()}，"
            f"请推荐最合适的{chart_type}图表配置，用中文回答。"
        )
        recommendation = await self.call_llm(
            prompt,
            VISUALIZATION_SYSTEM_PROMPT,
            temperature=self._DETERMINISTIC_TEMPERATURE,
        )

        return cast(
            "dict[str, Any]",
            _sanitize_for_json(
                {
                    "status": "success",
                    "chart_type": chart_type,
                    "columns": list(df.columns),
                    "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                    "recommendation": recommendation,
                }
            ),
        )

    async def upload(self, request: dict[str, Any]) -> dict[str, Any]:
        """数据上传处理"""
        data = request.get("data")
        filename = request.get("filename", "unknown")

        if data is None:
            raise ValidationException("缺少data字段")

        try:
            df = self._to_dataframe(data)
            summary = self.tools_handler.get_data_summary(df)

            return cast(
                "dict[str, Any]",
                _sanitize_for_json(
                    {"status": "success", "filename": filename, "summary": summary}
                ),
            )
        except Exception as e:
            raise AgentException(f"数据处理失败: {str(e)}", self.name)

    async def get_summary(self, request: dict[str, Any]) -> dict[str, Any]:
        """获取数据概览"""
        data = request.get("data")

        if data is None:
            raise ValidationException("缺少data字段")

        try:
            df = self._to_dataframe(data)
            summary = self.tools_handler.get_data_summary(df)

            return cast(
                "dict[str, Any]",
                _sanitize_for_json({"status": "success", "summary": summary}),
            )
        except Exception as e:
            raise AgentException(f"数据概览失败: {str(e)}", self.name)

    @staticmethod
    def _to_dataframe(data: Any) -> pd.DataFrame:
        """统一将 list/dict 转为 DataFrame，消除重复死分支"""
        if not isinstance(data, (list, dict)):
            raise ValidationException(
                f"data 字段类型不支持: {type(data).__name__}，需 list/dict"
            )
        return pd.DataFrame(data)

from unittest.mock import AsyncMock, patch

import numpy as np
import pandas as pd
import pytest

from app.agents.data.agent import DataAgent
from app.agents.data.tools import DataTools


@pytest.fixture
def data_agent():
    return DataAgent()


@pytest.fixture
def sample_df():
    return pd.DataFrame(
        {
            "age": [25, 30, 35, 40, 45, 50, 55, 60, 200],  # 200是异常值
            "salary": [5000, 7000, 9000, 11000, 13000, 15000, 17000, 19000, 50000],
            "score": [85, 90, 78, 92, 88, 95, 82, 87, 91],
            "category": ["A", "B", "A", "B", "A", "B", "A", "B", "A"],
        }
    )


@pytest.mark.asyncio
async def test_data_analyze_descriptive(data_agent, sample_df):
    """测试描述性统计分析"""
    with patch.object(data_agent, "call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "数据分析结果显示..."

        result = await data_agent.process(
            {
                "task": "analyze",
                "data": sample_df.to_dict(orient="records"),
                "analysis_type": "descriptive",
            }
        )

        assert result["status"] == "success"
        assert "results" in result
        assert "explanation" in result
        assert "data_shape" in result


@pytest.mark.asyncio
async def test_data_analyze_correlation(data_agent, sample_df):
    """测试相关性分析"""
    with patch.object(data_agent, "call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "变量间存在强相关性..."

        result = await data_agent.process(
            {
                "task": "analyze",
                "data": sample_df.to_dict(orient="records"),
                "analysis_type": "correlation",
            }
        )

        assert result["status"] == "success"
        assert "results" in result


@pytest.mark.asyncio
async def test_data_analyze_unknown_type(data_agent, sample_df):
    """测试未知分析类型"""
    with patch.object(data_agent, "call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "..."

        result = await data_agent.process(
            {
                "task": "analyze",
                "data": sample_df.to_dict(orient="records"),
                "analysis_type": "unknown",
            }
        )

        assert "error" in result["results"]


@pytest.mark.asyncio
async def test_data_visualize(data_agent, sample_df):
    """测试可视化建议"""
    with patch.object(data_agent, "call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "推荐使用柱状图..."

        result = await data_agent.process(
            {
                "task": "visualize",
                "data": sample_df.to_dict(orient="records"),
                "chart_type": "bar",
            }
        )

        assert result["status"] == "success"
        assert "chart_type" in result
        assert "recommendation" in result


# DataTools测试
def test_clean_data(sample_df):
    """测试数据清洗"""
    # 添加缺失值
    df = sample_df.copy()
    df.loc[0, "age"] = np.nan
    df.loc[1, "category"] = np.nan

    cleaned = DataTools.clean_data(df)

    # 检查缺失值被填充
    assert cleaned["age"].isna().sum() == 0
    assert cleaned["category"].isna().sum() == 0


def test_descriptive_statistics(sample_df):
    """测试描述性统计"""
    stats = DataTools.descriptive_statistics(sample_df)

    assert "numeric" in stats
    assert "categorical" in stats
    assert "age" in stats["numeric"]
    assert "mean" in stats["numeric"]["age"]
    assert "std" in stats["numeric"]["age"]


def test_correlation_analysis(sample_df):
    """测试相关性分析"""
    result = DataTools.correlation_analysis(sample_df)

    assert "matrix" in result
    assert "method" in result
    assert result["method"] == "pearson"


def test_correlation_insufficient_columns():
    """测试相关性分析-列数不足"""
    df = pd.DataFrame({"col1": [1, 2, 3]})
    result = DataTools.correlation_analysis(df)
    assert "error" in result


def test_outlier_detection(sample_df):
    """测试异常值检测"""
    result = DataTools.outlier_detection(sample_df)

    assert "method" in result
    assert "outliers" in result
    # age列有200这个异常值
    assert "age" in result["outliers"]
    assert result["outliers"]["age"]["count"] > 0


def test_group_comparison(sample_df):
    """测试分组比较"""
    result = DataTools.group_comparison(sample_df, "category", "score")

    assert "groups" in result
    assert "A" in result["groups"]
    assert "B" in result["groups"]
    assert "mean" in result["groups"]["A"]


def test_get_data_summary(sample_df):
    """测试数据概览"""
    summary = DataTools.get_data_summary(sample_df)

    assert "shape" in summary
    assert "columns" in summary
    assert "dtypes" in summary
    assert "missing" in summary

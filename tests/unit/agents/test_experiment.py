from unittest.mock import AsyncMock, patch

import pytest

from app.agents.experiment.agent import ExperimentAgent
from app.agents.experiment.tools import ExperimentTools


@pytest.fixture
def experiment_agent():
    return ExperimentAgent()


# Agent测试
@pytest.mark.asyncio
async def test_design_experiment_agent(experiment_agent):
    """测试实验设计Agent"""
    with patch.object(experiment_agent, "call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "Optimized experiment design..."

        result = await experiment_agent.process(
            {
                "task": "design",
                "research_goal": "Test new drug efficacy",
                "variables": ["dosage", "duration", "group_size"],
            }
        )

        assert "plan" in result
        assert "optimized_plan" in result


# Tools测试
def test_design_experiment_tools():
    """测试实验设计"""
    result = ExperimentTools.design_experiment(
        goal="研究温度对反应速率的影响",
        variables=["温度", "反应速率", "催化剂"],
        design_type="between",
    )

    assert result["goal"] == "研究温度对反应速率的影响"
    assert result["design_type"] == "between"
    assert "groups" in result
    assert "steps" in result
    assert "sample_size_recommendation" in result
    assert "ethical_considerations" in result
    assert len(result["groups"]) > 0


def test_design_experiment_types():
    """测试不同实验设计类型"""
    for design_type in ["between", "within", "mixed", "factorial", "repeated"]:
        result = ExperimentTools.design_experiment(
            goal="测试目标", variables=["变量A", "变量B"], design_type=design_type
        )
        assert result["design_type"] == design_type


def test_design_experiment_invalid_type():
    """测试无效的实验设计类型"""
    with pytest.raises(Exception) as exc_info:
        ExperimentTools.design_experiment(
            goal="测试目标", variables=["变量A"], design_type="invalid_type"
        )
    assert "不支持" in str(exc_info.value)


def test_select_statistical_test_continuous():
    """测试连续变量的统计检验选择"""
    result = ExperimentTools.select_statistical_test(
        variable_type="continuous", group_count=2, paired=False
    )

    assert result["recommended_test"] == "ttest_independent"
    assert "description" in result
    assert "assumptions" in result
    assert "alternatives" in result


def test_select_statistical_test_paired():
    """测试配对样本的统计检验选择"""
    result = ExperimentTools.select_statistical_test(
        variable_type="continuous", group_count=2, paired=True
    )

    assert result["recommended_test"] == "ttest_paired"


def test_select_statistical_test_anova():
    """测试多组比较的统计检验选择"""
    result = ExperimentTools.select_statistical_test(
        variable_type="continuous", group_count=3, paired=False
    )

    assert result["recommended_test"] == "anova_one"


def test_select_statistical_test_categorical():
    """测试分类变量的统计检验选择"""
    result = ExperimentTools.select_statistical_test(
        variable_type="categorical", group_count=2
    )

    assert result["recommended_test"] == "chi_square"


def test_optimize_parameters():
    """测试参数优化"""
    historical_data = [
        {"params": {"temp": 100, "pressure": 1}, "score": 80},
        {"params": {"temp": 150, "pressure": 2}, "score": 90},
        {"params": {"temp": 200, "pressure": 3}, "score": 85},
    ]

    result = ExperimentTools.optimize_parameters(historical_data, target_metric="score")

    assert "optimized_params" in result
    assert "best_historical_params" in result
    assert "best_score" in result
    assert "param_importance" in result
    assert "confidence" in result
    assert result["best_score"] == 90


def test_optimize_parameters_empty():
    """测试空数据的参数优化"""
    result = ExperimentTools.optimize_parameters([])

    assert result["optimized_params"] == {}
    assert result["confidence"] == 0


def test_predict_result():
    """测试结果预测"""
    historical_data = [
        {"params": {"temp": 100, "pressure": 1}, "score": 80, "result": {"yield": 0.8}},
        {"params": {"temp": 150, "pressure": 2}, "score": 90, "result": {"yield": 0.9}},
        {
            "params": {"temp": 200, "pressure": 3},
            "score": 85,
            "result": {"yield": 0.85},
        },
    ]

    result = ExperimentTools.predict_result(
        params={"temp": 120, "pressure": 1.5},
        historical_data=historical_data,
        target_metric="score",
    )

    assert "prediction" in result
    assert "confidence" in result
    assert "confidence_interval" in result


def test_predict_result_no_similar():
    """测试无相似数据的预测"""
    historical_data = [
        {"params": {"x": 1}, "score": 10},
    ]

    result = ExperimentTools.predict_result(
        params={"y": 2}, historical_data=historical_data
    )

    assert result["confidence"] == 0


def test_calculate_power_analysis():
    """测试功效分析"""
    result = ExperimentTools.calculate_power_analysis(
        effect_size=0.5, alpha=0.05, power=0.8
    )

    assert "sample_size_per_group" in result
    assert "total_sample_size" in result
    assert "interpretation" in result
    assert result["sample_size_per_group"] > 0
    assert result["total_sample_size"] > 0


def test_calculate_power_analysis_small_effect():
    """测试小效应量的功效分析"""
    result = ExperimentTools.calculate_power_analysis(effect_size=0.2)

    assert result["interpretation"] == "小效应"
    # 小效应需要更大样本量
    assert result["sample_size_per_group"] > 50


def test_calculate_power_analysis_large_effect():
    """测试大效应量的功效分析"""
    result = ExperimentTools.calculate_power_analysis(effect_size=0.8)

    assert result["interpretation"] == "非常大的效应"
    # 大效应需要较小样本量
    assert result["sample_size_per_group"] < 50

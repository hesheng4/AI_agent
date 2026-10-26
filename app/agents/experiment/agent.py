from typing import Any

from app.agents.base import BaseAgent
from app.agents.experiment.prompts import (
    DESIGN_SYSTEM_PROMPT,
    OPTIMIZE_SYSTEM_PROMPT,
    PREDICT_SYSTEM_PROMPT,
)
from app.agents.experiment.tools import ExperimentTools
from app.utils.exceptions import AgentException


class ExperimentAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="experiment", tools=["design", "optimize", "predict"])
        self.tools_handler = ExperimentTools()

    async def process(self, request: dict[str, Any]) -> dict[str, Any]:
        task = request.get("task")

        if task == "design":
            return await self.design(request)
        elif task == "optimize":
            return await self.optimize(request)
        elif task == "predict":
            return await self.predict(request)
        else:
            raise AgentException(f"未知任务类型: {task}", self.name)

    async def design(self, request: dict[str, Any]) -> dict[str, Any]:
        goal = request.get("research_goal", "")
        variables = request.get("variables", [])

        plan = self.tools_handler.design_experiment(goal, variables)

        # 注入功效分析支撑：用 request 中的 effect_size（默认 0.5）计算样本量与功效曲线
        # 解决"实验设计依赖经验，统计方法选择容易出错且无功效分析支撑"
        effect_size = request.get("effect_size", 0.5)
        try:
            power_analysis = ExperimentTools.calculate_power_analysis(
                effect_size=effect_size,
                alpha=request.get("alpha", 0.05),
                power=request.get("power", 0.8),
            )
            plan["power_analysis"] = power_analysis
            # 同步更新 sample_size_recommendation，让功效分析结果驱动样本量建议
            plan.setdefault("sample_size_recommendation", {})
            plan["sample_size_recommendation"]["per_group"] = power_analysis[
                "sample_size_per_group"
            ]
            plan["sample_size_recommendation"]["recommended"] = power_analysis[
                "total_sample_size"
            ]
            plan["sample_size_recommendation"]["actual_power"] = power_analysis.get(
                "actual_power"
            )

            # 附功效曲线，便于前端可视化样本量-功效关系
            plan["power_curve"] = ExperimentTools.power_curve(
                effect_size=effect_size,
                alpha=request.get("alpha", 0.05),
            )
        except Exception as e:
            # 功效分析失败不阻断实验设计主流程
            plan["power_analysis_error"] = str(e)

        prompt = (
            f"请优化以下实验设计：\n目标：{goal}\n变量：{variables}\n当前方案：{plan}"
        )
        optimized_plan = await self.call_llm(
            prompt, DESIGN_SYSTEM_PROMPT, temperature=0.0
        )

        return {"plan": plan, "optimized_plan": optimized_plan}

    async def optimize(self, request: dict[str, Any]) -> dict[str, Any]:
        historical_data = request.get("historical_data", [])

        result = self.tools_handler.optimize_parameters(historical_data)

        prompt = f"请解释以下参数优化结果：\n{result}"
        explanation = await self.call_llm(
            prompt, OPTIMIZE_SYSTEM_PROMPT, temperature=0.0
        )

        return {"result": result, "explanation": explanation}

    async def predict(self, request: dict[str, Any]) -> dict[str, Any]:
        params = request.get("params", {})
        historical_data = request.get("historical_data", [])

        prediction = self.tools_handler.predict_result(params, historical_data)

        prompt = f"请解释以下预测结果：\n参数：{params}\n预测：{prediction}"
        explanation = await self.call_llm(
            prompt, PREDICT_SYSTEM_PROMPT, temperature=0.0
        )

        return {"prediction": prediction, "explanation": explanation}

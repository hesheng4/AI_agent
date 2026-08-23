"""Nature-skills 驱动的学术润色 Agent

支持任务:
- polish: 润色文本（服务读者工作流，不改变论证结构）
- diagnose: 诊断失败模式（结构/句子/术语/证据弱化）
- terminology: 术语一致性检查与修正
- latex_layout: LaTeX 排版修复
- translate: 中译英学术润色
"""

from typing import Any

from app.agents.base import BaseAgent
from app.agents.polishing.prompts import (
    FAILURE_MODES,
    LATEX_LAYOUT_PROMPT,
    PAPER_TYPE_POLISH_FOCUS,
    POLISH_SYSTEM_PROMPT,
    POLISH_WORKFLOW_STEPS,
    STRUCTURE_DIAGNOSIS_PROMPT,
)
from app.utils.exceptions import AgentException


class PolishingAgent(BaseAgent):
    """Nature-skills 驱动的学术润色 Agent"""

    def __init__(self):
        super().__init__(
            name="polishing",
            tools=[
                "polish",
                "diagnose",
                "check_terminology",
                "fix_latex_layout",
                "detect_paper_type",
                "detect_language",
            ],
        )

    async def process(self, request: dict[str, Any]) -> dict[str, Any]:
        task = request.get("task", "polish")

        handlers = {
            "polish": self.polish,
            "diagnose": self.diagnose,
            "terminology": self.check_terminology,
            "latex_layout": self.fix_latex_layout,
            "translate": self.translate,
        }
        handler = handlers.get(task)
        if handler:
            return await handler(request)
        raise AgentException(f"未知任务类型: {task}", self.name)

    async def polish(self, request: dict[str, Any]) -> dict[str, Any]:
        """润色文本（Nature-skills 读者工作流驱动）"""
        content = request.get("content", "")
        paper_type = request.get("paper_type", "research")
        section = request.get("section", "")
        language = request.get("language") or self.detect_language(content)
        journal = request.get("journal", "generic")

        type_info = PAPER_TYPE_POLISH_FOCUS.get(
            paper_type, PAPER_TYPE_POLISH_FOCUS["research"]
        )

        prompt = (
            f"请润色以下学术文本：\n"
            f"论文类型：{type_info['label']}（润色重点：{type_info['polish_priority']}）\n"
        )
        if section:
            prompt += f"目标章节：{section}\n"
        prompt += f"语言方向：{'中译英' if language == 'zh-to-en' else '英文学术'}\n"
        prompt += f"期刊风格：{journal}\n\n{content}"

        polished = await self.call_llm(
            prompt,
            POLISH_SYSTEM_PROMPT,
            temperature=0.0,
            user_api_key=request.get("_user_api_key"),
            user_api_base_url=request.get("_user_api_base_url"),
            user_api_model=request.get("_user_api_model"),
        )
        return {"original": content, "polished": polished, "paper_type": paper_type}

    async def diagnose(self, request: dict[str, Any]) -> dict[str, Any]:
        """诊断失败模式"""
        content = request.get("content", "")
        paper_type = request.get("paper_type", "research")
        type_info = PAPER_TYPE_POLISH_FOCUS.get(
            paper_type, PAPER_TYPE_POLISH_FOCUS["research"]
        )

        prompt = (
            f"请诊断以下学术文本的失败模式：\n"
            f"论文类型：{type_info['label']}\n"
            f"重点检查：{'; '.join(type_info['key_checks'])}\n\n{content[:8000]}"
        )
        diagnosis = await self.call_llm(
            prompt,
            STRUCTURE_DIAGNOSIS_PROMPT,
            temperature=0.0,
            user_api_key=request.get("_user_api_key"),
            user_api_base_url=request.get("_user_api_base_url"),
            user_api_model=request.get("_user_api_model"),
        )
        return {"diagnosis": diagnosis, "paper_type": paper_type}

    async def check_terminology(self, request: dict[str, Any]) -> dict[str, Any]:
        """术语一致性检查"""
        content = request.get("content", "")
        prompt = (
            f"请检查以下学术文本的术语一致性，列出所有术语漂移：\n\n{content[:8000]}"
        )
        result = await self.call_llm(
            prompt,
            POLISH_SYSTEM_PROMPT,
            temperature=0.0,
            user_api_key=request.get("_user_api_key"),
            user_api_base_url=request.get("_user_api_base_url"),
            user_api_model=request.get("_user_api_model"),
        )
        return {"terminology_check": result}

    async def fix_latex_layout(self, request: dict[str, Any]) -> dict[str, Any]:
        """LaTeX 排版修复"""
        tex_source = request.get("tex_source", "")
        # 截断到安全边界：优先在 8000 字符内的最后一个换行/空白处截断，
        # 避免截断在 LaTeX 命令中间导致 LLM 收到不完整源码
        snippet = tex_source[:8000]
        if len(tex_source) > 8000:
            # 回退到最后一个空白字符（换行/空格），保证不切断命令
            boundary = snippet.rfind("\n")
            if boundary < 4000:  # 若换行回退过多，尝试空格
                boundary = snippet.rfind(" ")
            if boundary >= 4000:
                snippet = snippet[:boundary]
            snippet = snippet + "\n... [源码过长，已截断]"
        prompt = f"请诊断并修复以下 LaTeX 源码的排版问题：\n\n{snippet}"
        result = await self.call_llm(
            prompt,
            LATEX_LAYOUT_PROMPT,
            temperature=0.0,
            user_api_key=request.get("_user_api_key"),
            user_api_base_url=request.get("_user_api_base_url"),
            user_api_model=request.get("_user_api_model"),
        )
        return {"layout_fixes": result}

    async def translate(self, request: dict[str, Any]) -> dict[str, Any]:
        """中译英学术润色"""
        content = request.get("content", "")
        paper_type = request.get("paper_type", "research")
        type_info = PAPER_TYPE_POLISH_FOCUS.get(
            paper_type, PAPER_TYPE_POLISH_FOCUS["research"]
        )

        prompt = (
            f"请将以下中文学术文本翻译为 Nature 风格英文学术英语：\n"
            f"论文类型：{type_info['label']}\n\n{content}"
        )
        translated = await self.call_llm(
            prompt,
            POLISH_SYSTEM_PROMPT,
            temperature=0.0,
            user_api_key=request.get("_user_api_key"),
            user_api_base_url=request.get("_user_api_base_url"),
            user_api_model=request.get("_user_api_model"),
        )
        return {"original": content, "translated": translated}

    @staticmethod
    def detect_language(text: str) -> str:
        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        return "zh-to-en" if chinese_chars > len(text) * 0.3 else "en"

    @staticmethod
    def detect_paper_type(text: str) -> str:
        lower = text.lower()
        if any(k in lower for k in ["算法", "algorithm", "模型", "model"]):
            return "algorithmic"
        if any(k in lower for k in ["综述", "review", "meta-analys"]):
            return "review"
        if any(k in lower for k in ["假设", "hypothesis", "因果", "causal"]):
            return "hypothesis"
        if any(k in lower for k in ["方法", "method", "协议", "protocol"]):
            return "methods"
        return "research"

    WORKFLOW_STEPS = POLISH_WORKFLOW_STEPS
    FAILURE_MODES = FAILURE_MODES

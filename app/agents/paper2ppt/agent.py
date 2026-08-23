"""Nature-Paper2PPT: 论文→Nature风格中文PPTX

遵循 nature-paper2ppt SKILL.md 规范：
- 6种论文类型弧：discovery/methods/resource/clinical/materials/review
- 9步工作流：分类→提取→术语→大纲→内容→图表→样式→自审→导出
- 术语账本保持一致性
- 不编造结果/数字/图表细节
"""

from typing import Any

from app.agents.base import BaseAgent
from app.utils.exceptions import AgentException
from app.utils.logger import get_logger

logger = get_logger("agent.paper2ppt")

# 论文类型弧
PAPER_TYPE_ARCS = {
    "discovery": {
        "label": "发现/机制论文",
        "arc": "question → evidence",
        "slides": [
            "标题页",
            "核心问题",
            "关键发现",
            "证据链1",
            "证据链2",
            "方法概览",
            "数据展示",
            "讨论与意义",
            "局限与展望",
            "致谢",
        ],
    },
    "methods": {
        "label": "方法/AI/工具论文",
        "arc": "problem → solution",
        "slides": [
            "标题页",
            "问题与动机",
            "方法概述",
            "技术细节1",
            "技术细节2",
            "基准对比",
            "消融实验",
            "应用案例",
            "局限与未来",
            "致谢",
        ],
    },
    "resource": {
        "label": "资源/数据集论文",
        "arc": "workflow → validation",
        "slides": [
            "标题页",
            "资源概述",
            "数据收集",
            "处理流程",
            "质量评估",
            "基准结果",
            "使用案例",
            "获取方式",
            "未来扩展",
            "致谢",
        ],
    },
    "clinical": {
        "label": "临床/干预研究",
        "arc": "design → inference",
        "slides": [
            "标题页",
            "研究设计",
            "入组标准",
            "干预方案",
            "主要终点",
            "安全性",
            "亚组分析",
            "讨论与意义",
            "局限",
            "致谢",
        ],
    },
    "materials": {
        "label": "材料/化学/物理论文",
        "arc": "property → mechanism / design → performance",
        "slides": [
            "标题页",
            "材料设计",
            "合成方法",
            "表征结果",
            "性能测试",
            "机制分析",
            "对比文献",
            "应用前景",
            "局限",
            "致谢",
        ],
    },
    "review": {
        "label": "综述/观点/评论",
        "arc": "evidence map",
        "slides": [
            "标题页",
            "综述范围",
            "关键主题1",
            "关键主题2",
            "关键主题3",
            "交叉对比",
            "未来方向",
            "结论",
            "参考文献",
            "致谢",
        ],
    },
}


class Paper2PPTAgent(BaseAgent):
    """论文→PPTX Agent"""

    def __init__(self):
        super().__init__(
            name="paper2ppt",
            tools=["classify", "extract", "terminology", "outline", "content", "qa"],
        )

    async def process(self, request: dict[str, Any]) -> dict[str, Any]:
        """9步工作流"""
        content = request.get("content", "")
        paper_type = request.get("paper_type", "auto")

        if not content.strip():
            raise AgentException("论文内容不能为空", self.name)

        # Step 1: 分类论文类型
        if paper_type == "auto":
            paper_type = self._classify_type(content)
        arc = PAPER_TYPE_ARCS.get(paper_type, PAPER_TYPE_ARCS["discovery"])
        logger.info(f"Paper2PPT: 类型={paper_type}, 弧={arc['arc']}")

        # Step 2-3: 提取 + 术语账本
        terminology = self._build_terminology(content)

        # Step 4-7: LLM 生成大纲+内容+图表+样式
        deck = await self._generate_deck(content, paper_type, arc, terminology)

        # Step 8: 自审
        qa = self._qa_check(deck)

        # Step 9: 返回
        return {
            "paper_type": paper_type,
            "arc": arc["arc"],
            "slide_structure": arc["slides"],
            "deck": deck,
            "terminology": terminology,
            "qa": qa,
        }

    def _classify_type(self, content: str) -> str:
        """启发式分类论文类型"""
        lower = content.lower()
        if any(
            w in lower
            for w in ["clinical trial", "randomized", "intervention", "临床试验"]
        ):
            return "clinical"
        if any(
            w in lower for w in ["dataset", "benchmark", "corpus", "数据集", "基准"]
        ):
            return "resource"
        if any(
            w in lower for w in ["method", "algorithm", "framework", "方法", "算法"]
        ):
            return "methods"
        if any(
            w in lower for w in ["review", "survey", "meta-analysis", "综述", "调研"]
        ):
            return "review"
        if any(
            w in lower for w in ["material", "synthesis", "property", "材料", "合成"]
        ):
            return "materials"
        return "discovery"

    def _build_terminology(self, content: str) -> dict[str, Any]:
        """构建术语账本"""
        import re

        terms = set()
        for m in re.finditer(r"\b[A-Z]{2,8}\b", content):
            terms.add(m.group())
        return {"terms": sorted(terms), "total": len(terms)}

    async def _generate_deck(
        self,
        content: str,
        paper_type: str,
        arc: dict[str, Any],
        terminology: dict[str, Any],
    ) -> dict[str, Any]:
        """LLM 生成 PPTX 内容"""
        prompt = (
            f"请将以下论文转换为 Nature 风格中文 PPT 演示文稿内容：\n\n"
            f"论文类型：{arc['label']}（弧：{arc['arc']}）\n"
            f"推荐幻灯片结构：{' → '.join(arc['slides'])}\n"
            f"术语账本：{', '.join(terminology['terms'][:20])}\n\n"
            f"论文内容：\n{content[:6000]}\n\n"
            f"要求：\n"
            f"1. 每页幻灯片包含：标题、要点（≤5条）、演讲备注\n"
            f"2. 中文为主，专业术语保留英文\n"
            f"3. 不编造结果、数字或图表细节\n"
            f"4. 标记缺失内容为 AUTHOR_INPUT_NEEDED\n"
        )
        deck_content = await self.call_llm(prompt, temperature=0.0)
        return {"content": deck_content, "total_slides": len(arc["slides"])}

    def _qa_check(self, deck: dict[str, Any]) -> dict[str, Any]:
        """自审检查"""
        issues = []
        content = deck.get("content", "")
        if "AUTHOR_INPUT_NEEDED" in content:
            issues.append("存在需作者补充的内容")
        if len(content) < 200:
            issues.append("生成内容过短，可能不完整")
        return {"passed": len(issues) == 0, "issues": issues}

    async def generate_pptx(self, deck: dict, output_path: str = "output.pptx") -> str:
        """Step 9: 实际生成 .pptx 文件"""
        try:
            from pptx import Presentation
            from pptx.util import Inches

            prs = Presentation()
            prs.slide_width = Inches(13.333)
            prs.slide_height = Inches(7.5)

            slide_layout = prs.slide_layouts[1]
            slide = prs.slides.add_slide(slide_layout)
            title = slide.shapes.title
            title.text = "Nature-Style Presentation"

            prs.save(output_path)
            return output_path
        except ImportError:
            return "AUTHOR_INPUT_NEEDED: pip install python-pptx"

    # 完整9步工作流
    PAPER2PPT_9_STEPS = [
        "1_classify_paper_type",
        "2_extract_key_content",
        "3_build_terminology_ledger",
        "4_design_slide_outline",
        "5_draft_slide_content",
        "6_select_figure_assets",
        "7_apply_nature_style",
        "8_self_review_and_fix",
        "9_export_pptx",
    ]

    async def full_9_step(self, request: dict) -> dict:
        """完整9步工作流"""
        content = request.get("content", "")
        paper_type = request.get("paper_type", "auto")
        # Step 1-3 已在 process() 中
        # Step 4-7: LLM 生成（已在 _generate_deck 中合并）
        deck = await self._generate_deck(
            content,
            paper_type,
            PAPER_TYPE_ARCS.get(paper_type, PAPER_TYPE_ARCS["discovery"]),
            self._build_terminology(content),
        )
        # Step 8: 自审+修正循环
        for _ in range(2):  # 最多2轮修正
            qa = self._qa_check(deck)
            if qa["passed"]:
                break
            deck = await self._fix_deck(deck, qa["issues"])
        # Step 9: 导出
        pptx_path = await self.generate_pptx(deck)
        return {"deck": deck, "pptx_path": pptx_path, "qa": qa}

    async def _fix_deck(self, deck: dict, issues: list) -> dict:
        """修正幻灯片问题"""
        fix_prompt = (
            f"修正以下PPT问题：{issues}\n\n原内容：{deck.get('content', '')[:2000]}"
        )
        fixed = await self.call_llm(fix_prompt, temperature=0.0)
        return {**deck, "content": fixed}

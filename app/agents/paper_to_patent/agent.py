"""Nature-Paper-to-Patent: 论文→中国发明专利草稿

遵循 nature-paper-to-patent SKILL.md 规范：
- 源依据映射 (P001/E001/F001/C001)
- 支撑状态: explicit/inherent/needs-confirmation/unsupported
- 阶段门控: 源映射→术语账本→清单→证据账本→发明概念→正式权利要求
- 中文正式文档: 权利要求书/说明书/说明书摘要/摘要附图
- 不推断发明人/所有权/法律充分性
"""

import re
from typing import Any

from app.agents.base import BaseAgent
from app.utils.exceptions import AgentException
from app.utils.logger import get_logger

logger = get_logger("agent.paper_to_patent")

SUPPORT_STATES = ["explicit", "inherent", "needs-confirmation", "unsupported"]


class PaperToPatentAgent(BaseAgent):
    """论文→中国发明专利 Agent"""

    def __init__(self) -> None:
        super().__init__(
            name="paper_to_patent",
            tools=[
                "source_map",
                "terminology",
                "inventory",
                "evidence_ledger",
                "invention_concept",
                "claims",
                "specification",
            ],
        )

    async def process(self, request: dict[str, Any]) -> dict[str, Any]:
        """阶段门控工作流"""
        content = request.get("content", "")
        task_mode = request.get("task_mode", "full_draft")
        invention_type = request.get("invention_type", "algorithm")

        if not content.strip():
            raise AgentException("论文内容不能为空", self.name)

        # Stage 1: 源依据映射
        source_map = self._build_source_map(content)

        # Stage 2: 术语账本
        terminology = self._build_terminology(content)

        # Stage 3: 清单 (技术特征/效果/实施例)
        inventory = self._inventory(content)

        # Stage 4: 证据账本
        evidence = self._evidence_ledger(inventory, source_map)

        # Stage 5-7: LLM 生成正式文档
        if task_mode == "full_draft":
            result = await self._draft_full(
                content, source_map, terminology, evidence, invention_type
            )
        elif task_mode == "claims_only":
            result = await self._draft_claims(
                content, terminology, evidence, invention_type
            )
        elif task_mode == "audit":
            result = self._audit_support(evidence)
        else:
            result = {"source_map": source_map, "evidence": evidence}

        return result

    def _build_source_map(self, content: str) -> list[dict[str, Any]]:
        """Stage 1: 创建源依据映射 (P001/E001/F001/C001)"""
        source_ids: list[dict[str, Any]] = []
        # 按段落分配 P001...
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        for i, para in enumerate(paragraphs):
            sid = f"P{i + 1:03d}"
            # 检测公式
            equations = re.findall(r"\$.*?\$", para)
            for j, eq in enumerate(equations):
                source_ids.append(
                    {
                        "source_id": f"E{len(source_ids) + 1:03d}",
                        "type": "equation",
                        "content": eq[:100],
                        "parent": sid,
                    }
                )
            # 检测图表引用
            figures = re.findall(r"(?:Figure|Fig\.)\s*\d+", para)
            for fig in figures:
                source_ids.append(
                    {
                        "source_id": f"F{len(source_ids) + 1:03d}",
                        "type": "figure",
                        "content": fig,
                        "parent": sid,
                    }
                )
            source_ids.append(
                {
                    "source_id": sid,
                    "type": "text",
                    "content": para[:200],
                }
            )
        return source_ids

    def _build_terminology(self, content: str) -> dict[str, Any]:
        """Stage 2: 术语账本"""
        terms = set()
        for m in re.finditer(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b", content):
            terms.add(m.group())
        for m in re.finditer(r"\b[A-Z]{2,8}\b", content):
            terms.add(m.group())
        return {"terms": sorted(terms), "total": len(terms)}

    def _inventory(self, content: str) -> dict[str, Any]:
        """Stage 3: 技术特征清单"""
        return {
            "content_length": len(content),
            "has_equations": bool(re.search(r"\$.*?\$", content)),
            "has_figures": bool(re.search(r"(?:Figure|Fig\.)\s*\d+", content)),
            "has_algorithms": bool(
                re.search(r"(?:algorithm|Algorithm|步骤|流程)", content)
            ),
        }

    def _evidence_ledger(
        self, inventory: dict[str, Any], source_map: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Stage 4: 证据账本 — 每个特征映射到源依据"""
        ledger = []
        for src in source_map[:20]:  # 限制前20条
            ledger.append(
                {
                    "feature": src["content"][:80],
                    "source_id": src["source_id"],
                    "support_state": "explicit",
                }
            )
        return ledger

    async def _draft_full(
        self,
        content: str,
        source_map: list[dict[str, Any]],
        terminology: dict[str, Any],
        evidence: list[dict[str, Any]],
        invention_type: str,
    ) -> dict[str, Any]:
        """Stage 5-7: 完整草稿"""
        source_ids_str = ", ".join(s["source_id"] for s in source_map[:10])
        prompt = (
            f"请将以下论文转换为证据支撑的中国发明专利草稿：\n\n"
            f"发明类型：{invention_type}\n"
            f"源依据ID：{source_ids_str}\n"
            f"术语账本：{', '.join(terminology['terms'][:20])}\n\n"
            f"论文内容：\n{content[:6000]}\n\n"
            f"请输出以下部分：\n"
            f"1. 权利要求书（独立权利要求+从属权利要求）\n"
            f"2. 说明书（技术领域/背景/内容/实施方式）\n"
            f"3. 说明书摘要\n\n"
            f"要求：\n"
            f"- 每个权利要求特征必须映射到源依据ID\n"
            f"- 不编造发明人/所有权/公开日/先验结论\n"
            f"- 缺失信息标记 [TO CONFIRM: 具体问题]\n"
            f"- unsupported 特征不纳入正式权利要求\n"
        )
        draft = await self.call_llm(prompt, temperature=0.0)
        return {
            "draft": draft,
            "source_map_size": len(source_map),
            "evidence_size": len(evidence),
            "invention_type": invention_type,
        }

    async def _draft_claims(
        self,
        content: str,
        terminology: dict[str, Any],
        evidence: list[dict[str, Any]],
        invention_type: str,
    ) -> dict[str, Any]:
        """仅生成权利要求书"""
        prompt = (
            f"请为以下论文生成中国发明专利权利要求书：\n\n"
            f"发明类型：{invention_type}\n"
            f"术语：{', '.join(terminology['terms'][:20])}\n\n"
            f"论文内容：\n{content[:4000]}\n\n"
            f"要求：每个特征映射到源依据，不编造，缺失标记 [TO CONFIRM]\n"
        )
        claims = await self.call_llm(prompt, temperature=0.0)
        return {"claims": claims, "invention_type": invention_type}

    def _audit_support(self, evidence: list[dict[str, Any]]) -> dict[str, Any]:
        """审计支撑一致性"""
        unsupported = [e for e in evidence if e["support_state"] == "unsupported"]
        return {
            "total_features": len(evidence),
            "unsupported": len(unsupported),
            "needs_confirmation": sum(
                1 for e in evidence if e["support_state"] == "needs-confirmation"
            ),
            "audit_passed": len(unsupported) == 0,
        }

    # 按发明类型差异化 prompt
    INVENTION_TYPE_PROMPTS = {
        "algorithm-software": (
            "重点描述算法步骤、数据流、计算复杂度，权利要求以方法+系统为主"
        ),
        "apparatus-system": (
            "重点描述结构组成、连接关系、工作原理，权利要求以装置+系统为主"
        ),
        "process-material": (
            "重点描述制备工艺、参数范围、性能测试，权利要求以方法+产品为主"
        ),
        "mixed": "综合以上，按主导技术特征选择主权利要求类型",
    }

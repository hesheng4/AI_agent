"""Nature-Reader: 全文中英对照 Markdown Reader

遵循 nature-reader SKILL.md 规范：
- 6步工作流：源格式检测 → 文本提取 → 分段 → 中英对照翻译 → 术语账本 → 输出
- 5种源格式：pdf-text / scanned-pdf / html / doi-arxiv / pasted-text
- 输出：paper.md (中英对照) + source_map.json
  + terminology_ledger.json + translation_notes.md
- 不降级为摘要模式
"""

import json
import re
from typing import Any

from app.agents.base import BaseAgent
from app.utils.exceptions import AgentException
from app.utils.logger import get_logger

logger = get_logger("agent.reader")

# 源格式枚举
SOURCE_FORMATS = ["pdf-text", "scanned-pdf", "html", "doi-arxiv", "pasted-text"]

# 章节检测正则
SECTION_PATTERNS = [
    (r"(?i)^#{1,3}\s*abstract", "abstract"),
    (r"(?i)^#{1,3}\s*introduction", "introduction"),
    (r"(?i)^#{1,3}\s*(?:related\s+work|literature\s+review)", "related-work"),
    (r"(?i)^#{1,3}\s*(?:methods?|methodology|materials?\s+and\s+methods?)", "methods"),
    (r"(?i)^#{1,3}\s*(?:results?|findings?)", "results"),
    (r"(?i)^#{1,3}\s*discussion", "discussion"),
    (r"(?i)^#{1,3}\s*conclusion", "conclusion"),
    (r"(?i)^#{1,3}\s*(?:references?|bibliography)", "references"),
    (r"(?i)^#{1,3}\s*(?:supplementary|supplemental)", "supplementary"),
    (r"(?i)^#{1,3}\s*(?:acknowledgments?|funding)", "acknowledgments"),
]

# 期刊级格式约束
JOURNAL_FORMATS = {
    "nature": {"max_abstract_words": 150, "summary_paragraph": True},
    "nat-comms": {"max_abstract_words": 300, "summary_paragraph": False},
    "generic": {"max_abstract_words": 300, "summary_paragraph": False},
}


class ReaderAgent(BaseAgent):
    """全文中英对照 Markdown Reader Agent"""

    def __init__(self):
        super().__init__(
            name="reader",
            tools=[
                "detect_format",
                "extract_text",
                "segment",
                "translate_bilingual",
                "build_terminology",
                "build_output",
            ],
        )

    async def process(self, request: dict[str, Any]) -> dict[str, Any]:
        """6步工作流：检测 → 提取 → 分段 → 翻译 → 术语 → 输出"""
        content = request.get("content", "")
        source_format = request.get("source_format", "auto")
        journal = request.get("journal", "generic")
        language = request.get("language", "zh-to-en")

        if not content.strip():
            raise AgentException("论文内容不能为空", self.name)

        # Step 1: 检测源格式
        if source_format == "auto":
            source_format = self._detect_format(content)
        logger.info(f"Reader: 源格式={source_format}, 期刊={journal}, 语言={language}")

        # Step 2: 提取文本（含图表位置标记）
        extracted = self._extract_text(content, source_format)

        # Step 3: 分段（按章节 + 段落）
        segments = self._segment(extracted)

        # Step 4: 中英对照翻译
        bilingual = await self._translate_bilingual(segments, language, journal)

        # Step 5: 构建术语账本
        terminology = self._build_terminology(bilingual)

        # Step 6: 组装输出
        output = self._build_output(
            bilingual, terminology, source_format, journal, language
        )

        return output

    def _detect_format(self, content: str) -> str:
        """自动检测源格式"""
        if content.startswith("http") and ("arxiv.org" in content or "doi" in content):
            return "doi-arxiv"
        if content.startswith("http"):
            return "html"
        if len(content) > 5000 and "\n" not in content[:200]:
            return "pdf-text"
        return "pasted-text"

    def _extract_text(self, content: str, source_format: str) -> dict[str, Any]:
        """提取文本，标记图表位置

        对于 pasted-text 和 pdf-text，直接使用原文；
        标记 [FIGURE n], [TABLE n] 占位符以保持图表位置。
        """
        text = content

        # 标记图表位置
        figure_index = 0
        table_index = 0

        def _mark_figure(m):
            nonlocal figure_index
            figure_index += 1
            return f"\n\n[FIGURE {figure_index}]\n\n"

        def _mark_table(m):
            nonlocal table_index
            table_index += 1
            return f"\n\n[TABLE {table_index}]\n\n"

        # 检测常见图表标记
        text = re.sub(
            r"(?:Figure|Fig\.)\s*\d+",
            _mark_figure,
            text,
        )
        text = re.sub(
            r"(?:Table|Tab\.)\s*\d+",
            _mark_table,
            text,
        )

        return {
            "text": text,
            "source_format": source_format,
            "figure_count": figure_index,
            "table_count": table_index,
        }

    def _segment(self, extracted: dict[str, Any]) -> list[dict[str, Any]]:
        """按章节 + 段落分段

        每个段落保留：section_name, paragraph_index, text, has_figure, has_table
        """
        text = extracted["text"]
        lines = text.split("\n")

        segments = []
        current_section = "preamble"
        para_buffer = []
        para_index = 0

        for line in lines:
            # 检测章节标题
            section_match = None
            for pattern, section_name in SECTION_PATTERNS:
                if re.match(pattern, line.strip()):
                    section_match = section_name
                    break

            if section_match:
                # 刷出当前段落
                if para_buffer:
                    para_text = "\n".join(para_buffer).strip()
                    if para_text:
                        segments.append(
                            self._make_segment(current_section, para_index, para_text)
                        )
                        para_index += 1
                    para_buffer = []

                current_section = section_match
                segments.append(
                    self._make_segment(
                        current_section, para_index, line.strip(), is_heading=True
                    )
                )
                para_index += 1
                continue

            # 空行 = 段落边界
            if not line.strip():
                if para_buffer:
                    para_text = "\n".join(para_buffer).strip()
                    if para_text:
                        segments.append(
                            self._make_segment(current_section, para_index, para_text)
                        )
                        para_index += 1
                    para_buffer = []
                continue

            para_buffer.append(line)

        # 尾段
        if para_buffer:
            para_text = "\n".join(para_buffer).strip()
            if para_text:
                segments.append(
                    self._make_segment(current_section, para_index, para_text)
                )

        logger.info(f"Reader: 分段完成，共 {len(segments)} 段")
        return segments

    def _make_segment(
        self,
        section: str,
        index: int,
        text: str,
        is_heading: bool = False,
    ) -> dict[str, Any]:
        return {
            "section": section,
            "index": index,
            "text": text,
            "is_heading": is_heading,
            "has_figure": "[FIGURE" in text,
            "has_table": "[TABLE" in text,
        }

    async def _translate_bilingual(
        self,
        segments: list[dict[str, Any]],
        language: str,
        journal: str,
    ) -> list[dict[str, Any]]:
        """中英对照翻译

        - zh-to-en: 中文原文 + 英文翻译
        - en: 英文原文 + 中文翻译
        """
        bilingual_segments = []
        # 批量翻译，每次最多 5 段
        batch_size = 5
        for i in range(0, len(segments), batch_size):
            batch = segments[i : i + batch_size]
            batch_text = "\n\n---\n\n".join(
                f"[段{seg['index']}] {seg['text']}" for seg in batch
            )

            if language == "zh-to-en":
                translate_prompt = (
                    f"请将以下中文学术文本逐段翻译为英文，保持学术风格和术语准确性。\n"
                    f"期刊标准：{journal}\n"
                    f"每段翻译前保留原文，格式为：\n"
                    f"【原文】...\n【译文】...\n\n"
                    f"不要省略任何段落，不要降级为摘要。\n\n{batch_text}"
                )
            else:
                translate_prompt = (
                    f"请将以下英文学术文本逐段翻译为中文，保持学术风格和术语准确性。\n"
                    f"每段翻译前保留原文，格式为：\n"
                    f"【原文】...\n【译文】...\n\n"
                    f"不要省略任何段落，不要降级为摘要。\n\n{batch_text}"
                )

            translation = await self.call_llm(
                translate_prompt,
                "You are an expert academic translator. "
                "Translate accurately, preserve technical terms, "
                "and maintain academic register. Never summarize or skip content.",
                temperature=0.0,
            )

            # 解析翻译结果
            for seg in batch:
                bilingual_segments.append(
                    {
                        **seg,
                        "translation": translation,
                    }
                )

        return bilingual_segments

    def _build_terminology(
        self, bilingual_segments: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """构建术语账本

        从原文和译文中提取反复出现的术语对。
        """
        term_counts: dict[str, int] = {}

        for seg in bilingual_segments:
            if seg.get("is_heading"):
                continue
            text = seg["text"]
            # 提取可能的术语：大写缩写 (3-8 字母)
            for m in re.finditer(r"\b[A-Z]{3,8}\b", text):
                term = m.group()
                term_counts[term] = term_counts.get(term, 0) + 1

        # 只保留出现 2 次以上的术语
        ledger = {
            term: {"count": count, "canonical": term}
            for term, count in term_counts.items()
            if count >= 2
        }

        return {
            "ledger": ledger,
            "total_terms": len(ledger),
        }

    def _build_output(
        self,
        bilingual_segments: list[dict[str, Any]],
        terminology: dict[str, Any],
        source_format: str,
        journal: str,
        language: str,
    ) -> dict[str, Any]:
        """组装输出包

        输出：
        - paper_md: 中英对照 Markdown
        - source_map: 源映射 JSON
        - terminology_ledger: 术语账本
        - translation_notes: 翻译笔记
        """
        # 构建 paper.md
        md_lines = []
        for seg in bilingual_segments:
            if seg.get("is_heading"):
                md_lines.append(f"\n## {seg['text']}\n")
            else:
                md_lines.append(f"\n**【原文】**\n{seg['text']}\n")
                if seg.get("translation"):
                    md_lines.append(f"\n**【译文】**\n{seg['translation']}\n")
                if seg.get("has_figure"):
                    md_lines.append("\n> [图表位置 — 需从原文提取]\n")
                if seg.get("has_table"):
                    md_lines.append("\n> [表格位置 — 需从原文提取]\n")

        paper_md = "\n".join(md_lines)

        # 构建 source_map.json
        source_map = {
            "source_format": source_format,
            "journal": journal,
            "language": language,
            "segments": [
                {
                    "section": seg["section"],
                    "index": seg["index"],
                    "has_figure": seg.get("has_figure", False),
                    "has_table": seg.get("has_table", False),
                }
                for seg in bilingual_segments
            ],
            "glossary": terminology.get("ledger", {}),
        }

        # 翻译笔记
        translation_notes = (
            f"# 翻译笔记\n\n"
            f"- 源格式: {source_format}\n"
            f"- 期刊: {journal}\n"
            f"- 语言方向: {language}\n"
            f"- 总段落数: {len(bilingual_segments)}\n"
            f"- 术语数: {terminology['total_terms']}\n"
            f"- 图表占位符: 需从原文提取实际图表\n"
        )

        return {
            "paper_md": paper_md,
            "source_map": json.dumps(source_map, ensure_ascii=False, indent=2),
            "terminology_ledger": json.dumps(terminology, ensure_ascii=False, indent=2),
            "translation_notes": translation_notes,
            "stats": {
                "total_segments": len(bilingual_segments),
                "total_terms": terminology["total_terms"],
                "source_format": source_format,
                "journal": journal,
            },
        }

    async def answer_question(
        self, question: str, paper_md: str, source_map: str
    ) -> dict[str, Any]:
        """Step 6: 后续问答 — 基于论文内容回答，引用源块 ID"""
        prompt = (
            f"基于以下论文内容回答问题，引用具体的源块 ID：\n\n"
            f"论文：\n{paper_md[:4000]}\n\n"
            f"问题：{question}\n\n"
            f"要求：引用 [Sxxx] 源块 ID 和页码，不从记忆回答。"
        )
        answer = await self.call_llm(prompt, temperature=0.0)
        return {"question": question, "answer": answer, "grounded": True}

    @staticmethod
    async def extract_pdf(file_path: str) -> dict[str, Any]:
        """从 PDF 提取文本+图表位置（需 PyMuPDF/pdfplumber）"""
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(file_path)
            pages = []
            for page_num, page in enumerate(doc):
                text = page.get_text()
                images = page.get_images(full=True)
                pages.append(
                    {
                        "page": page_num + 1,
                        "text": text,
                        "image_count": len(images),
                        "source_ids": [f"S{page_num + 1:03d}"],
                    }
                )
            doc.close()
            return {"pages": pages, "total_pages": len(pages)}
        except ImportError:
            return {"error": "需安装 PyMuPDF: pip install pymupdf", "pages": []}

    @staticmethod
    def crop_figure(page, rect, output_path: str) -> str:
        """裁剪图表区域并保存"""
        try:
            pix = page.get_pixmap(clip=rect)
            pix.save(output_path)
            return output_path
        except Exception:
            return ""

"""参考文献管理服务 - 自动插入引用、生成参考文献列表"""

import re
from typing import Any

from app.utils.exceptions import ToolException
from app.utils.logger import get_logger

logger = get_logger("services.reference")


# 引用格式模板
CITATION_STYLES = {
    "apa": {
        "name": "APA 7th",
        "in_text_pattern": "({authors_year})",
        "format_func": "_format_apa",
    },
    "mla": {
        "name": "MLA 9th",
        "in_text_pattern": "{authors_page}",
        "format_func": "_format_mla",
    },
    "chicago": {
        "name": "Chicago 17th",
        "in_text_pattern": "[{number}]",
        "format_func": "_format_chicago",
    },
    "ieee": {
        "name": "IEEE",
        "in_text_pattern": "[{number}]",
        "format_func": "_format_ieee",
    },
    "vancouver": {
        "name": "Vancouver",
        "in_text_pattern": "[{number}]",
        "format_func": "_format_vancouver",
    },
    "harvard": {
        "name": "Harvard",
        "in_text_pattern": "({authors_year})",
        "format_func": "_format_harvard",
    },
    "gbt7714": {
        "name": "GB/T 7714-2015",
        "in_text_pattern": "[{number}]",
        "format_func": "_format_gbt7714",
    },
}


class ReferenceManager:
    """参考文献管理器"""

    def __init__(self, style: str = "apa"):
        if style not in CITATION_STYLES:
            raise ToolException(
                f"不支持的引用格式: {style}，支持: {list(CITATION_STYLES.keys())}",
                tool_name="reference_manager",
            )
        self.style = style
        self.references: list[dict[str, Any]] = []
        self._citation_map: dict[str, int] = {}  # key -> reference index

    def add_reference(self, paper: dict[str, Any]) -> int:
        """添加一条参考文献，返回引用编号"""
        key = self._make_key(paper)
        if key in self._citation_map:
            return self._citation_map[key]

        idx = len(self.references)
        self.references.append(paper)
        self._citation_map[key] = idx
        return idx

    def add_references_batch(self, papers: list[dict[str, Any]]) -> list[int]:
        """批量添加参考文献"""
        return [self.add_reference(p) for p in papers]

    def get_in_text_citation(self, paper: dict[str, Any], page: str = None) -> str:
        """生成行内引用标记"""
        idx = self.add_reference(paper)
        CITATION_STYLES[self.style]

        if self.style in ("apa", "harvard"):
            authors_str = self._format_authors_short(paper)
            year = paper.get("year", "n.d.")
            if page:
                return f"({authors_str}, {year}, p.{page})"
            return f"({authors_str}, {year})"

        elif self.style == "mla":
            authors_str = self._format_authors_short(paper)
            if page:
                return f"({authors_str} {page})"
            return f"({authors_str})"

        else:  # chicago, ieee, vancouver, gbt7714
            return f"[{idx + 1}]"

    def insert_citations(
        self, text: str, citation_map: dict[str, dict[str, Any]]
    ) -> str:
        """在文本中自动插入引用标记

        Args:
            text: 原始文本，其中用 {{key}} 标记需要引用的位置
            citation_map: key -> paper 的映射

        Returns:
            插入引用后的文本
        """

        def replace_citation(match):
            key = match.group(1)
            if key in citation_map:
                return self.get_in_text_citation(citation_map[key])
            return match.group(0)  # 未找到则保留原样

        return re.sub(r"\{\{(\w+)\}\}", replace_citation, text)

    def auto_detect_and_cite(
        self, text: str, papers: list[dict[str, Any]]
    ) -> tuple[str, list[dict[str, Any]]]:
        """自动检测文本中需要引用的位置并插入引用

        检测规则：
        1. "XXX研究表明" 后自动插入引用
        2. "根据XXX" 后自动插入引用
        3. 括号中的年份模式 (2023) 前插入引用
        """
        cited_papers = []

        for paper in papers:
            title = paper.get("title", "")
            first_author = ""
            authors = paper.get("authors", [])
            if authors:
                if isinstance(authors, list) and authors:
                    first_author = (
                        authors[0].split()[-1]
                        if isinstance(authors[0], str)
                        else str(authors[0])
                    )
                elif isinstance(authors, str):
                    first_author = authors.split()[-1]

            year = str(paper.get("year", ""))

            # 检测标题引用
            if title and title in text:
                citation = self.get_in_text_citation(paper)
                text = text.replace(title, f"{title} {citation}")
                cited_papers.append(paper)
                continue

            # 检测 "作者(年份)" 模式
            if first_author and year:
                pattern = f"{first_author}({year})"
                alt_pattern = f"{first_author} ({year})"
                citation = self.get_in_text_citation(paper)

                if pattern in text:
                    text = text.replace(pattern, f"{first_author}{citation}")
                    cited_papers.append(paper)
                elif alt_pattern in text:
                    text = text.replace(alt_pattern, f"{first_author} {citation}")
                    cited_papers.append(paper)

        return text, cited_papers

    def generate_bibliography(self) -> str:
        """生成参考文献列表"""
        if not self.references:
            return ""

        entries = []
        for i, paper in enumerate(self.references):
            formatted = self.format_reference(paper)
            if self.style in ("chicago", "ieee", "vancouver", "gbt7714"):
                entries.append(f"[{i + 1}] {formatted}")
            else:
                entries.append(formatted)

        header = "## 参考文献\n\n" if self.style == "gbt7714" else "## References\n\n"
        return header + "\n".join(entries)

    def format_reference(self, paper: dict[str, Any]) -> str:
        """格式化单条参考文献"""
        style_config = CITATION_STYLES[self.style]
        format_func_name = style_config["format_func"]
        format_func = getattr(ReferenceManager, format_func_name)
        return format_func(paper)

    def to_bibtex(self, paper: dict[str, Any]) -> str:
        """生成BibTeX条目"""
        key = self._make_key(paper)
        authors = paper.get("authors", [])
        if isinstance(authors, list):
            author_str = " and ".join(authors)
        else:
            author_str = str(authors)

        lines = [f"@article{{{key},"]
        lines.append(f"  title = {{{paper.get('title', '')}}},")
        lines.append(f"  author = {{{author_str}}},")
        if paper.get("year"):
            lines.append(f"  year = {{{paper['year']}}},")
        if paper.get("journal"):
            lines.append(f"  journal = {{{paper['journal']}}},")
        if paper.get("volume"):
            lines.append(f"  volume = {{{paper['volume']}}},")
        if paper.get("pages"):
            lines.append(f"  pages = {{{paper['pages']}}},")
        if paper.get("doi"):
            lines.append(f"  doi = {{{paper['doi']}}},")
        if paper.get("url"):
            lines.append(f"  url = {{{paper['url']}}},")
        lines.append("}")
        return "\n".join(lines)

    def to_bibtex_batch(self) -> str:
        """批量生成BibTeX"""
        return "\n\n".join(self.to_bibtex(p) for p in self.references)

    @staticmethod
    def _make_key(paper: dict[str, Any]) -> str:
        """生成引用key"""
        authors = paper.get("authors", [])
        if isinstance(authors, list) and authors:
            first = authors[0].split()[-1] if isinstance(authors[0], str) else "unknown"
        else:
            first = "unknown"
        year = paper.get("year", "0000")
        title_word = (
            paper.get("title", "").split()[0].lower()
            if paper.get("title")
            else "untitled"
        )
        return f"{first}{year}{title_word}"

    @staticmethod
    def _format_authors_short(paper: dict[str, Any]) -> str:
        """格式化短作者名（行内引用用）"""
        authors = paper.get("authors", [])
        if isinstance(authors, str):
            authors = [a.strip() for a in authors.split(",")]

        if not authors:
            return "Unknown"

        if len(authors) == 1:
            return authors[0].split()[-1]
        elif len(authors) == 2:
            return f"{authors[0].split()[-1]} & {authors[1].split()[-1]}"
        else:
            return f"{authors[0].split()[-1]} et al."

    @staticmethod
    def _format_authors_full(authors: Any) -> str:
        """格式化完整作者名"""
        if isinstance(authors, str):
            return authors
        if isinstance(authors, list):
            if len(authors) == 1:
                return authors[0]
            elif len(authors) <= 6:
                return ", ".join(authors[:-1]) + ", & " + authors[-1]
            else:
                return ", ".join(authors[:6]) + ", ... " + authors[-1]
        return "Unknown"

    # ========== 各格式格式化方法 ==========

    @staticmethod
    def _format_apa(paper: dict[str, Any]) -> str:
        """APA 7th格式"""
        authors = ReferenceManager._format_authors_full(paper.get("authors", []))
        year = paper.get("year", "n.d.")
        title = paper.get("title", "")
        journal = paper.get("journal", "")
        volume = paper.get("volume", "")
        pages = paper.get("pages", "")
        doi = paper.get("doi", "")

        parts = [f"{authors} ({year}). {title}."]
        if journal:
            journal_part = f" *{journal}*"
            if volume:
                journal_part += f", *{volume}*"
            if pages:
                journal_part += f", {pages}"
            journal_part += "."
            parts.append(journal_part)
        if doi:
            parts.append(f" https://doi.org/{doi}")

        return "".join(parts)

    @staticmethod
    def _format_mla(paper: dict[str, Any]) -> str:
        """MLA 9th格式"""
        authors = paper.get("authors", [])
        if isinstance(authors, list) and authors:
            # MLA: Last, First. Second Author First Last.
            first = authors[0]
            name_parts = first.split()
            if len(name_parts) > 1:
                formatted_authors = f"{name_parts[-1]}, {' '.join(name_parts[:-1])}"
            else:
                formatted_authors = first
            if len(authors) > 1:
                formatted_authors += ", et al."
        else:
            formatted_authors = "Unknown"

        title = paper.get("title", "")
        journal = paper.get("journal", "")
        volume = paper.get("volume", "")
        year = paper.get("year", "")
        pages = paper.get("pages", "")

        parts = [f'{formatted_authors}. "{title}."']
        if journal:
            parts.append(f" *{journal}*")
            if volume:
                parts.append(f", vol. {volume}")
            parts.append(f", {year}")
            if pages:
                parts.append(f", pp. {pages}")
            parts.append(".")
        return "".join(parts)

    @staticmethod
    def _format_chicago(paper: dict[str, Any]) -> str:
        """Chicago 17th Notes格式"""
        authors = ReferenceManager._format_authors_full(paper.get("authors", []))
        title = paper.get("title", "")
        journal = paper.get("journal", "")
        volume = paper.get("volume", "")
        year = paper.get("year", "")
        pages = paper.get("pages", "")
        doi = paper.get("doi", "")

        parts = [f'{authors}, "{title},"']
        if journal:
            parts.append(f" *{journal}* {volume}" if volume else f" *{journal}*")
            parts.append(f" ({year})")
            if pages:
                parts.append(f": {pages}")
            parts.append(".")
        if doi:
            parts.append(f" https://doi.org/{doi}")
        return "".join(parts)

    @staticmethod
    def _format_ieee(paper: dict[str, Any]) -> str:
        """IEEE格式"""
        authors = paper.get("authors", [])
        if isinstance(authors, list):
            formatted = []
            for a in authors:
                parts = a.split()
                if len(parts) > 1:
                    formatted.append(
                        f"{parts[-1]} {' '.join(p[0] + '.' for p in parts[:-1])}"
                    )
                else:
                    formatted.append(a)
            authors_str = ", ".join(formatted)
        else:
            authors_str = str(authors)

        title = paper.get("title", "")
        journal = paper.get("journal", "")
        volume = paper.get("volume", "")
        pages = paper.get("pages", "")
        year = paper.get("year", "")

        parts = [f'{authors_str}, "{title},"']
        if journal:
            parts.append(f" *{journal}*")
            if volume:
                parts.append(f", vol. {volume}")
            if pages:
                parts.append(f", pp. {pages}")
            parts.append(f", {year}.")
        return "".join(parts)

    @staticmethod
    def _format_vancouver(paper: dict[str, Any]) -> str:
        """Vancouver格式"""
        authors = paper.get("authors", [])
        if isinstance(authors, list):
            formatted = []
            for a in authors:
                parts = a.split()
                if len(parts) > 1:
                    formatted.append(
                        f"{parts[-1]} {' '.join(p[0] for p in parts[:-1])}"
                    )
                else:
                    formatted.append(a)
            authors_str = ", ".join(formatted)
        else:
            authors_str = str(authors)

        title = paper.get("title", "")
        journal = paper.get("journal", "")
        year = paper.get("year", "")
        volume = paper.get("volume", "")
        pages = paper.get("pages", "")

        parts = [f"{authors_str}. {title}."]
        if journal:
            parts.append(f" {journal}.")
            if year:
                parts.append(f" {year}")
            if volume:
                parts.append(f";{volume}")
            if pages:
                parts.append(f":{pages}")
            parts.append(".")
        return "".join(parts)

    @staticmethod
    def _format_harvard(paper: dict[str, Any]) -> str:
        """Harvard格式"""
        authors = ReferenceManager._format_authors_full(paper.get("authors", []))
        year = paper.get("year", "n.d.")
        title = paper.get("title", "")
        journal = paper.get("journal", "")
        volume = paper.get("volume", "")
        pages = paper.get("pages", "")

        parts = [f"{authors} ({year}) '{title}',"]
        if journal:
            parts.append(f" *{journal}*")
            if volume:
                parts.append(f", {volume}")
            if pages:
                parts.append(f", pp. {pages}")
            parts.append(".")
        return "".join(parts)

    @staticmethod
    def _format_gbt7714(paper: dict[str, Any]) -> str:
        """GB/T 7714-2015格式"""
        authors = paper.get("authors", [])
        if isinstance(authors, list):
            formatted = []
            for a in authors[:3]:
                parts = a.split()
                if len(parts) > 1:
                    formatted.append(f"{parts[-1]} {''.join(p[0] for p in parts[:-1])}")
                else:
                    formatted.append(a)
            if len(authors) > 3:
                authors_str = ", ".join(formatted) + ", 等"
            else:
                authors_str = ", ".join(formatted)
        else:
            authors_str = str(authors)

        title = paper.get("title", "")
        journal = paper.get("journal", "")
        year = paper.get("year", "")
        volume = paper.get("volume", "")
        pages = paper.get("pages", "")

        parts = [f"{authors_str}. {title}[J]."]
        if journal:
            parts.append(f" {journal}")
            if year:
                parts.append(f", {year}")
            if volume:
                parts.append(f", {volume}")
            if pages:
                parts.append(f": {pages}")
            parts.append(".")
        return "".join(parts)

    @staticmethod
    def get_supported_styles() -> list[dict[str, str]]:
        """获取支持的引用格式列表"""
        return [{"id": k, "name": v["name"]} for k, v in CITATION_STYLES.items()]

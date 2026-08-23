from unittest.mock import AsyncMock, patch

import pytest

from app.agents.writing.agent import WritingAgent
from app.agents.writing.tools import WritingTools


@pytest.fixture
def writing_agent():
    return WritingAgent()


# Agent测试
@pytest.mark.asyncio
async def test_create_outline(writing_agent):
    """测试大纲生成"""
    with patch.object(writing_agent, "call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "1. Introduction\n2. Literature Review..."

        result = await writing_agent.process(
            {"task": "outline", "topic": "Machine Learning in Healthcare"}
        )

        assert "template" in result
        assert "optimized_outline" in result


# Tools测试
def test_create_outline_template():
    """测试大纲模板创建"""
    outline = WritingTools.create_outline_template("深度学习研究")

    assert outline["title"] == "深度学习研究"
    assert len(outline["sections"]) == 6
    assert outline["sections"][0]["title"] == "引言"
    assert "estimated_pages" in outline
    assert "word_count_range" in outline


def test_create_outline_custom_sections():
    """测试自定义章节数量"""
    outline = WritingTools.create_outline_template("测试主题", sections=3)
    assert len(outline["sections"]) == 3


def test_check_grammar():
    """测试语法检查"""
    text = "This is very very very good stuff. " * 3
    issues = WritingTools.check_grammar(text)

    assert isinstance(issues, list)
    # 应该检测到重复词和口语化词汇
    issue_types = [i["type"] for i in issues]
    assert "repetition" in issue_types or "style" in issue_types


def test_check_grammar_long_sentence():
    """测试长句子检测"""
    # 创建一个超长句子
    long_sentence = " ".join(["word"] * 50) + "."
    issues = WritingTools.check_grammar(long_sentence)

    # 应该检测到句子过长
    readability_issues = [i for i in issues if i["type"] == "readability"]
    assert len(readability_issues) > 0


def test_format_academic_text():
    """测试学术文本格式化"""
    text = "This  is   a  test...   with   multiple   spaces."
    formatted = WritingTools.format_academic_text(text)

    # 应该修复多余空格
    assert "  " not in formatted
    # 应该修复多余点号
    assert "..." not in formatted


def test_format_academic_text_quotes():
    """测试引号格式化"""
    text = "He said \"hello\" and 'goodbye'."
    formatted = WritingTools.format_academic_text(text)

    assert '"' in formatted or '"' in formatted


def test_count_words():
    """测试字数统计"""
    text = "这是一个测试句子。This is a test sentence."
    stats = WritingTools.count_words(text)

    assert "chinese_characters" in stats
    assert "english_words" in stats
    assert "total_characters" in stats
    assert "paragraphs" in stats
    assert "sentences" in stats
    assert "estimated_reading_time" in stats

    assert stats["chinese_characters"] > 0
    assert stats["english_words"] > 0


def test_count_words_multiple_paragraphs():
    """测试多段落字数统计"""
    text = "第一段。\n\n第二段。\n\n第三段。"
    stats = WritingTools.count_words(text)

    assert stats["paragraphs"] == 3


def test_suggest_transitions():
    """测试过渡词建议"""
    # 对比语境
    suggestions = WritingTools.suggest_transitions("however, the result")
    assert len(suggestions) > 0

    # 因果语境
    suggestions = WritingTools.suggest_transitions("therefore, we can see")
    assert len(suggestions) > 0


def test_suggest_transitions_auto():
    """测试自动过渡词建议"""
    suggestions = WritingTools.suggest_transitions("adding more information")
    assert isinstance(suggestions, list)


def test_generate_references_section():
    """测试参考文献生成"""
    papers = [
        {
            "title": "Paper 1",
            "authors": ["Author A"],
            "year": 2024,
            "journal": "Journal A",
        },
        {
            "title": "Paper 2",
            "authors": ["Author B"],
            "year": 2023,
            "journal": "Journal B",
        },
    ]

    refs = WritingTools.generate_references_section(papers, style="apa")

    assert "## 参考文献" in refs
    assert "[1]" in refs
    assert "[2]" in refs
    assert "Author A" in refs
    assert "Paper 1" in refs


def test_polish_sentence():
    """测试句子润色建议"""
    result = WritingTools.polish_sentence("The the the result is good.")

    assert "original" in result
    assert "suggestions" in result
    assert "word_count" in result


def test_polish_sentence_short():
    """测试短句润色"""
    result = WritingTools.polish_sentence("Good.")

    assert isinstance(result["suggestions"], list)
    # 短句应该有扩展建议

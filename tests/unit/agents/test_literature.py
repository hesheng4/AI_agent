from unittest.mock import AsyncMock, patch

import pytest

from app.agents.literature.agent import LiteratureAgent
from app.utils.exceptions import AgentException, ValidationException


@pytest.fixture
def literature_agent():
    return LiteratureAgent()


@pytest.mark.asyncio
async def test_literature_search(literature_agent):
    """测试文献搜索"""
    with patch.object(literature_agent, "call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "deep learning, neural networks, medical imaging"

        with patch(
            "app.agents.literature.tools.LiteratureTools.search_papers",
            new_callable=AsyncMock,
        ) as mock_search:
            mock_search.return_value = [
                {
                    "id": "paper_1",
                    "title": "Test Paper",
                    "authors": ["Author 1"],
                    "abstract": "Test abstract",
                    "year": 2024,
                    "journal": "Test Journal",
                }
            ]

            result = await literature_agent.process(
                {"task": "search", "query": "machine learning", "filters": {}}
            )

            assert result["status"] == "success"
            assert "papers" in result
            assert "suggestions" in result
            assert result["total_results"] > 0


@pytest.mark.asyncio
async def test_literature_search_missing_query(literature_agent):
    """测试缺少query的搜索"""
    with pytest.raises(ValidationException) as exc_info:
        await literature_agent.process({"task": "search"})
    assert "缺少必填字段" in str(exc_info.value)


@pytest.mark.asyncio
async def test_literature_read(literature_agent):
    """测试文献阅读"""
    with patch.object(literature_agent, "call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "这是一篇关于深度学习的论文..."

        result = await literature_agent.process(
            {
                "task": "read",
                "content": (
                    "This is a test paper content about"
                    " deep learning and neural networks. "
                )
                * 10,
            }
        )

        assert result["status"] == "success"
        assert "analysis" in result


@pytest.mark.asyncio
async def test_literature_read_short_content(literature_agent):
    """测试过短的文献内容"""
    with pytest.raises(ValidationException) as exc_info:
        await literature_agent.process({"task": "read", "content": "短内容"})
    assert "过短" in str(exc_info.value)


@pytest.mark.asyncio
async def test_literature_summarize(literature_agent, sample_papers):
    """测试文献总结"""
    with patch.object(literature_agent, "call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = ["总结1", "总结2", "综合综述"]

        result = await literature_agent.process(
            {"task": "summarize", "papers": sample_papers}
        )

        assert result["status"] == "success"
        assert "summaries" in result
        assert "review" in result
        assert result["total_processed"] == 2


@pytest.mark.asyncio
async def test_literature_summarize_empty_papers(literature_agent):
    """测试空文献列表的总结"""
    with pytest.raises(ValidationException) as exc_info:
        await literature_agent.process({"task": "summarize", "papers": []})
    assert "为空" in str(exc_info.value)


@pytest.mark.asyncio
async def test_literature_unknown_task(literature_agent):
    """测试未知任务类型"""
    with pytest.raises(AgentException) as exc_info:
        await literature_agent.process({"task": "unknown_task"})
    assert "未知任务类型" in str(exc_info.value)


@pytest.mark.asyncio
async def test_literature_missing_task(literature_agent):
    """测试缺少task字段"""
    with pytest.raises(ValidationException) as exc_info:
        await literature_agent.process({})
    assert "缺少task字段" in str(exc_info.value)

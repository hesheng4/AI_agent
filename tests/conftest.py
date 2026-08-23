import httpx
import pytest
from httpx import ASGITransport

from app.main import app


@pytest.fixture
async def client():
    """测试客户端（使用 ASGITransport，兼容新版 httpx）"""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_user():
    """模拟用户"""
    return {"id": "test_user_123", "email": "test@example.com", "username": "测试用户"}


@pytest.fixture
def sample_papers():
    """示例文献列表"""
    return [
        {
            "id": "paper_1",
            "title": "Machine Learning in Healthcare",
            "authors": ["Author A"],
            "abstract": "Abstract 1...",
            "year": 2023,
            "journal": "Journal A",
        },
        {
            "id": "paper_2",
            "title": "Deep Learning Applications",
            "authors": ["Author B"],
            "abstract": "Abstract 2...",
            "year": 2024,
            "journal": "Journal B",
        },
    ]


@pytest.fixture
def sample_dataframe():
    """示例数据"""
    import pandas as pd

    return pd.DataFrame(
        {
            "age": [25, 30, 35, 40, 45, 50, 55, 60],
            "salary": [5000, 7000, 9000, 11000, 13000, 15000, 17000, 19000],
            "department": ["IT", "HR", "IT", "Finance", "HR", "IT", "Finance", "HR"],
            "score": [85, 90, 78, 92, 88, 95, 82, 87],
        }
    )

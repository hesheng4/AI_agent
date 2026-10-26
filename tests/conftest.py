import httpx
import pytest
from httpx import ASGITransport

from app.main import app


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """每个用例前清空全局内存限流器。

    e2e 套件每个用例各自注册登录，全量运行（约 40+ 次 login）会触及
    IP 级登录限流（20/分钟），导致排在后面的用例 429 失败。
    清空后套件顺序无关、可重复。
    """
    from app.core import rate_limit as rl

    backend = getattr(rl.rate_limiter, "_backend", None) or rl.rate_limiter
    requests_store = getattr(backend, "_requests", None)
    if isinstance(requests_store, dict):
        requests_store.clear()
    yield


@pytest.fixture
async def client():
    """测试客户端（使用 ASGITransport，兼容新版 httpx）"""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def db_isolated_client(tmp_path):
    """临时 sqlite 隔离客户端：重置 engine + 建表 + 进程内 ASGI 请求。

    e2e / performance 测试专用——避免注册/登录用例污染开发数据库
    （research_agent.db），测试结束恢复原 engine。
    """
    import app.core.database as dbmod

    db_file = tmp_path / "isolated.db"
    await dbmod.reset_engine(f"sqlite+aiosqlite:///{db_file}")
    async with dbmod.engine.begin() as conn:
        await conn.run_sync(dbmod.Base.metadata.create_all)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await dbmod.reset_engine(None)  # 恢复 settings.DATABASE_URL


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

"""E2E 局部夹具：运行记录存储隔离（E6）"""

import pytest

from app.core import runs


@pytest.fixture
def runs_dir(tmp_path, monkeypatch):
    """隔离 data/runs/ 到临时目录，防污染真实存储"""
    d = tmp_path / "runs"
    monkeypatch.setattr(runs, "_RUNS_DIR", d)
    return d

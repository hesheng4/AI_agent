"""E2E：实验设计纯计算端点（credibility-convergence 覆盖缺口清偿）

experiment.py 5 个端点中 statistical-test / power-analysis 走
ExperimentTools 纯计算（零 LLM），可直接 HTTP 全链路验证数值正确性。
"""

import math
import uuid

import pytest

pytestmark = pytest.mark.e2e

_PASSWORD = "Passw0rd!e2e"


async def _auth_headers(client) -> dict[str, str]:
    token = uuid.uuid4().hex
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"exp_{token[:12]}@example.com",
            "username": f"u_{token[:10]}",
            "password": _PASSWORD,
        },
    )
    assert resp.status_code == 200, resp.text
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": f"exp_{token[:12]}@example.com", "password": _PASSWORD},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_statistical_test_recommendation(db_isolated_client):
    """连续变量两组独立 → 应推荐 t 检验族"""
    headers = await _auth_headers(db_isolated_client)
    resp = await db_isolated_client.post(
        "/api/v1/experiment/statistical-test",
        headers=headers,
        json={"variable_type": "continuous", "group_count": 2, "paired": False},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "success"
    rec = body["recommendation"]
    assert rec  # 有推荐内容
    text = str(rec)
    assert "t" in text.lower() or "检验" in text


@pytest.mark.asyncio
async def test_statistical_test_categorical_three_groups(db_isolated_client):
    """分类变量三组 → 卡方检验"""
    headers = await _auth_headers(db_isolated_client)
    resp = await db_isolated_client.post(
        "/api/v1/experiment/statistical-test",
        headers=headers,
        json={"variable_type": "categorical", "group_count": 3},
    )
    assert resp.status_code == 200, resp.text
    assert "chi" in str(resp.json()).lower() or "卡方" in str(resp.json())


@pytest.mark.asyncio
async def test_power_analysis_sample_size_matches_formula(db_isolated_client):
    """独立两样本 t 检验样本量：d=0.5, α=0.05, power=0.8
    → 闭式解 2(z_{0.975}+z_{0.8})²/d² ≈ 63.77 → 向上取整 64/组"""
    headers = await _auth_headers(db_isolated_client)
    resp = await db_isolated_client.post(
        "/api/v1/experiment/power-analysis",
        headers=headers,
        json={"effect_size": 0.5, "alpha": 0.05, "power": 0.8},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "success"
    result = body["result"]
    text = str(result)
    # 手写实现与教科书闭式解对齐（golden 测试已锁定 ±1），
    # HTTP 层验证响应包含合法样本量数字
    n_values = [
        v
        for v in _extract_numbers(result)
        if 10 <= v <= 1000 and float(v).is_integer()
    ]
    assert n_values, f"响应中未找到样本量数字: {text}"
    assert any(abs(n - 64) <= 2 for n in n_values), f"样本量偏离闭式解 64: {n_values}"


@pytest.mark.asyncio
async def test_power_analysis_monotonic_in_effect_size(db_isolated_client):
    """效应量越大所需样本量越小（单调性）"""
    headers = await _auth_headers(db_isolated_client)
    sizes = []
    for d in (0.2, 0.5, 0.8):
        resp = await db_isolated_client.post(
            "/api/v1/experiment/power-analysis",
            headers=headers,
            json={"effect_size": d, "alpha": 0.05, "power": 0.8},
        )
        assert resp.status_code == 200, resp.text
        nums = [
            v
            for v in _extract_numbers(resp.json()["result"])
            if 5 <= v <= 5000 and float(v).is_integer()
        ]
        assert nums, f"d={d} 未找到样本量"
        sizes.append(min(nums))  # 最小整数候选 = 每组样本量
    assert sizes[0] > sizes[1] > sizes[2], f"样本量未随效应量单调下降: {sizes}"


def _extract_numbers(obj) -> list[float]:
    """递归提取 JSON 结构中的所有数字"""
    if isinstance(obj, bool):
        return []
    if isinstance(obj, (int, float)):
        return [float(obj)]
    if isinstance(obj, dict):
        out: list[float] = []
        for v in obj.values():
            out.extend(_extract_numbers(v))
        return out
    if isinstance(obj, list):
        out = []
        for v in obj:
            out.extend(_extract_numbers(v))
        return out
    if isinstance(obj, str):
        # 从字符串字段里抽取整数（如 "每需 64 样本/组"）
        import re

        return [float(m) for m in re.findall(r"\b(\d{1,5})\b", obj)]
    return []


# math 导入保留给潜在精确断言扩展使用
_ = math

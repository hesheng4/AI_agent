"""E6 运行记录 API 守卫：列表/详情/404/跨用户隔离/非 failed 状态 409

设计契约: docs/plans/workflow-error-recovery-v1.md
runs 记录按 user 隔离（路径含 user_id），resume 仅允许 failed 状态。
全链路恢复用例（失败 → checkpoint → resume 全绿）见 test_workflow_chain.py。
"""

import uuid

import pytest

from app.core.runs import create_run, finalize_run

pytestmark = pytest.mark.e2e


async def _register_and_login(client) -> tuple[str, dict]:
    token = uuid.uuid4().hex
    email, username = f"e2e_{token[:12]}@example.com", f"u_{token[:10]}"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": "Passw0rd!e2e"},
    )
    assert reg.status_code == 200, reg.text
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Passw0rd!e2e"},
    )
    assert login.status_code == 200, login.text
    access = login.json()["access_token"]
    return reg.json()["id"], {"Authorization": f"Bearer {access}"}


def _seed_failed_run(user_id: str) -> object:
    rec = create_run(
        user_id,
        {"kind": "template", "template_id": "revise"},
        {"task": "x"},
        [
            {"agent": "reader", "request": {"task": "t1"}, "dependencies": []},
            {
                "agent": "reviewer",
                "request": {"task": "t2"},
                "dependencies": ["reader"],
            },
        ],
    )
    rec.step_finished("reader", status="success", result={"paper_md": "ok"})
    rec.step_finished(
        "reviewer", status="failed", error="boom", failure_class="transient"
    )
    finalize_run(
        user_id, rec.run_id, status="failed", error="工作流在步骤 reviewer 处终止"
    )
    return rec


@pytest.mark.asyncio
async def test_runs_list_detail_and_user_isolation(db_isolated_client, runs_dir):
    """列表/详情/404/跨用户隔离；凭据与 _ 前缀内部字段不落盘"""
    client = db_isolated_client
    user_id, headers = await _register_and_login(client)

    empty = await client.get("/api/v1/coordinator/runs", headers=headers)
    assert empty.status_code == 200
    assert empty.json() == {"runs": []}

    rec = _seed_failed_run(user_id)

    listed = await client.get("/api/v1/coordinator/runs", headers=headers)
    assert listed.status_code == 200
    runs_list = listed.json()["runs"]
    assert len(runs_list) == 1 and runs_list[0]["run_id"] == rec.run_id
    assert runs_list[0]["status"] == "failed"

    detail = await client.get(f"/api/v1/coordinator/runs/{rec.run_id}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "failed"
    assert "_user_api_key" not in body["request"]

    # 跨用户：他人 run 一律 404（user 隔离）
    _, other_headers = await _register_and_login(client)
    stranger = await client.get(
        f"/api/v1/coordinator/runs/{rec.run_id}", headers=other_headers
    )
    assert stranger.status_code == 404

    missing = await client.get("/api/v1/coordinator/runs/000000000000", headers=headers)
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_resume_rejects_non_failed_status(db_isolated_client, runs_dir):
    """仅 failed 可恢复；succeeded → 409"""
    client = db_isolated_client
    user_id, headers = await _register_and_login(client)
    rec = create_run(
        user_id,
        {"kind": "workflow", "workflow_id": "a" * 12},
        {},
        [{"agent": "reader", "request": {"task": "t"}, "dependencies": []}],
    )
    finalize_run(user_id, rec.run_id, status="succeeded")
    resp = await client.post(
        f"/api/v1/coordinator/runs/{rec.run_id}/resume", headers=headers
    )
    assert resp.status_code == 409

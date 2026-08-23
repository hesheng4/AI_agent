"""昇腾子系统核心模块单测（体检报告 P2-15）

adaptation / profiling / debugging 约 9,600 行此前仅有 6 个用例。
本文件覆盖三个纯 Python 层面的关键面：
- adaptation：会话生命周期（create/get/list/step1）+ 算子扫描
- profiling._validate_path_safety：shell 注入防护
- debugging._validate_session_id：路径穿越防护
所有用例不依赖 NPU，可在 Windows 开发机运行。
"""

import pytest

from app.core.adaptation import (
    AdaptationStatus,
    StepStatus,
    _check_cuda_fallback,
    _scan_operators,
    create_session,
    get_session,
    list_sessions,
    step1_collect_context,
)
from app.core.debugging import DebugSessionManager
from app.core.profiling import _validate_path_safety

# ---------------------------------------------------------------------------
# adaptation：会话生命周期
# ---------------------------------------------------------------------------


def test_create_session_hf_id_no_fs_check():
    """HuggingFace ID（非本地路径）不做文件系统存在性检查。"""
    session = create_session("Qwen/Qwen2.5-0.5B-Instruct", "qwen-test")
    assert session.model_path == "Qwen/Qwen2.5-0.5B-Instruct"
    assert session.model_name == "qwen-test"
    assert session.features == ["generate", "chat"]
    assert get_session(session.id) is session
    assert any(s["id"] == session.id for s in list_sessions())


def test_create_session_empty_path_rejected():
    with pytest.raises(ValueError, match="model_path"):
        create_session("   ", "x")


def test_create_session_missing_local_path_rejected():
    with pytest.raises(FileNotFoundError):
        create_session("./definitely_missing_model_dir_xyz", "x")


def test_step1_happy_path_advances_state():
    session = create_session("org/model-x", "x")
    step = step1_collect_context(
        session.id, {"implementation_root": "/repo", "vllm_path": "/vllm"}
    )
    assert step.status == StepStatus.PASSED
    assert session.current_step == 2
    assert session.status == AdaptationStatus.IN_PROGRESS
    assert step.result["implementation_root"] == "/repo"


def test_step1_unknown_session_rejected():
    with pytest.raises(ValueError, match="会话不存在"):
        step1_collect_context("no-such-session-id")


# ---------------------------------------------------------------------------
# adaptation：算子扫描
# ---------------------------------------------------------------------------


def test_scan_operators_detects_triton():
    """triton 标记行（import / @triton.jit）都会记入 triton_ops。"""
    code = (
        "import triton\n"
        "import triton.language as tl\n"
        "\n"
        "@triton.jit\n"
        "def fused_kernel(x):\n"
        "    pass\n"
    )
    result = _scan_operators(code)
    # import 行与装饰器行各产生一个条目（命名 triton_kernel_line_N）
    assert len(result["triton_ops"]) == 3


def test_scan_operators_cuda_with_and_without_fallback():
    """有 fallback 证据（.cpu()/is_available）→ with；完全无证据 → without。"""
    with_fb = "y = x.cuda()\nif not torch.cuda.is_available():\n    y = y.cpu()"
    without_fb = "def forward(x):\n    z = w.cuda()\n    return z + x"

    r1 = _scan_operators(with_fb)
    assert r1["cuda_with_fallback"], r1
    assert not r1["cuda_without_fallback"]

    r2 = _scan_operators(without_fb)
    assert r2["cuda_without_fallback"], r2
    assert not r2["cuda_with_fallback"]


def test_check_cuda_fallback_outside_window_is_false():
    """fallback 证据超出 ±20 行窗口时应判定无 fallback。"""
    lines = ["z = w.cuda()"] + ["    pad = 0"] * 45 + ["    y = t.cpu()"]
    assert _check_cuda_fallback(lines, 0) is False
    # 在窗口内则判定有 fallback
    assert _check_cuda_fallback(["z = w.cuda()", "y = t.cpu()"], 0) is True


# ---------------------------------------------------------------------------
# profiling：路径注入防护
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        "model;rm -rf /",
        "model`id`",
        "path|x",
        "path$HOME",
        "a&b",
        "a!b",
        "a<b",
        "p\nq",
    ],
)
def test_validate_path_safety_rejects_shell_chars(bad):
    with pytest.raises(ValueError, match="禁止字符|空字节"):
        _validate_path_safety(bad)


def test_validate_path_safety_accepts_normal_paths():
    assert _validate_path_safety("/models/Qwen2.5-72B") == "/models/Qwen2.5-72B"
    assert _validate_path_safety("relative/path.pt") == "relative/path.pt"
    assert _validate_path_safety("") == ""
    with pytest.raises(ValueError, match="必须是字符串"):
        _validate_path_safety(123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# debugging：session_id 穿越防护
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad", ["../etc/passwd", "..\\windows\\system32", "sess.v2", "a/b", "a b", ""]
)
def test_validate_session_id_rejects_traversal(bad):
    with pytest.raises(ValueError, match="非法 session_id|不能为空"):
        DebugSessionManager._validate_session_id(bad)


@pytest.mark.parametrize("ok", ["sess-001", "debug_20260823", "ABC123"])
def test_validate_session_id_accepts_normal_ids(ok):
    assert DebugSessionManager._validate_session_id(ok) == ok

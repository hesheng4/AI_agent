"""回归：get_vllm_install_guide 字符串误当函数调用（credibility-convergence 批次二）

历史缺陷：guide.verification 赋值中 "# 验证 NPU 可见性\\n"("python -c ...")
把字符串字面量当函数调用 → 运行到该函数必抛 TypeError: 'str' object
is not callable。本意为相邻字符串拼接。
"""

from app.core.toolchain import get_vllm_install_guide


def test_install_guide_builds_without_crash():
    """指南构造不再抛 TypeError，且三段验证命令齐全"""
    guide = get_vllm_install_guide()
    assert "vllm_ascend" in guide.verification
    assert "torch_npu" in guide.verification
    assert "NPU 可用" in guide.verification
    # 修复前括号错位会把 f-string 大括号吞进命令；断言命令行完整
    assert "torch.npu.is_available()" in guide.verification
    assert "torch.npu.device_count()" in guide.verification

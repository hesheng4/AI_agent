#!/usr/bin/env python
"""mypy 基线生成与增量校验。

设计要点
--------
1. **基线粒度是「文件 : 错误总数」，不是「文件 : 行号 : 错误码」**。
   加类型注解会移动行号，行号级基线在机械批次合并后会产生大面积假漂移，
   让门禁失去意义。文件级计数对行位移免疫，同时仍能表达「这个文件在涨还是在降」。

2. **只做增量，不做全量清零**。
   存量（2026-09-07 实测 890 条）是已知债务，冻结在基线里；
   CI 只要求「被改动的文件错误数不上升」，新增文件必须为 0。

3. **基线必须单调不增**。
   每合并一批修复后重跑 `gen` 重写基线，数字只能降不能升。

用法
----
    # 重新生成基线（每次合并修复批次后执行）
    python scripts/gen_mypy_baseline.py

    # 校验：全量对比，任何文件错误数上升即退出码 1
    python scripts/gen_mypy_baseline.py --check

    # 校验：只对比指定文件（CI 传 diff 文件列表）
    python scripts/gen_mypy_baseline.py --check --files app/main.py app/core/cache.py

    # 校验：从 stdin 读文件列表（配合 git diff --name-only）
    git diff --name-only origin/master | python scripts/gen_mypy_baseline.py --check --stdin
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASELINE = REPO_ROOT / "reports" / "mypy-baseline.txt"
DEFAULT_TARGET = "app"

# mypy --no-pretty 输出形如：app\main.py:417: error: Incompatible types ...  [assignment]
ERROR_RE = re.compile(r"^(?P<file>.+?):(?P<line>\d+): error: .*?\[(?P<code>[a-z0-9-]+)\]\s*$")
# 汇总行：Found 890 errors in 112 files (checked 146 source files)
SUMMARY_RE = re.compile(r"^Found (?P<n>\d+) errors?")


def run_mypy(target: str) -> list[str]:
    """执行 mypy，返回原始输出行。"""
    proc = subprocess.run(
        [sys.executable, "-m", "mypy", target, "--no-pretty", "--hide-error-context"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return (proc.stdout or "").splitlines()


def normalize(path_str: str) -> str:
    """Windows 反斜杠统一为正斜杠，去掉开头的 ./，保证跨平台稳定。"""
    p = path_str.strip().replace("\\", "/")
    return p[2:] if p.startswith("./") else p


def collect(target: str) -> tuple[Counter, int]:
    """统计每个文件的 mypy 错误数，返回 (Counter, 总数)。"""
    counts: Counter = Counter()
    total = 0
    for raw in run_mypy(target):
        m = ERROR_RE.match(raw)
        if m:
            counts[normalize(m.group("file"))] += 1
            continue
        s = SUMMARY_RE.match(raw.strip())
        if s:
            total = int(s.group("n"))
    return counts, total or sum(counts.values())


def write_baseline(counts: Counter, total: int, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# mypy 基线 —— 由 scripts/gen_mypy_baseline.py 生成，请勿手工编辑",
        "# 格式：<文件>:<该文件的 mypy 错误数>；首行为基线总数",
        "# 规则：改动文件的错误数不得高于本基线；新增文件必须为 0；基线总数单调不增",
        f"# total {total}",
    ]
    lines += [f"{f}:{c}" for f, c in sorted(counts.items())]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_baseline(path: Path) -> tuple[dict[str, int], int]:
    counts: dict[str, int] = {}
    total = 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            if raw.startswith("# total "):
                total = int(raw.split()[2])
            continue
        file_part, _, num = raw.rpartition(":")
        counts[normalize(file_part)] = int(num)
    return counts, total


def cmd_gen(target: str, out: Path) -> int:
    counts, total = collect(target)
    write_baseline(counts, total, out)
    print(f"[baseline] 已写入 {out.relative_to(REPO_ROOT)}")
    print(f"[baseline] 文件数 {len(counts)} | 错误总数 {total}")
    return 0


def cmd_check(target: str, out: Path, files: list[str] | None) -> int:
    if not out.exists():
        print(f"[check] 基线不存在：{out}，请先执行 gen", file=sys.stderr)
        return 2

    base_counts, base_total = read_baseline(out)
    cur_counts, cur_total = collect(target)

    wanted = None
    if files:
        wanted = {normalize(f) for f in files if f.strip()}

    regressions: list[tuple[str, int, int]] = []
    for f, cur in sorted(cur_counts.items()):
        if wanted is not None and f not in wanted:
            continue
        base = base_counts.get(f, 0)  # 新文件基数为 0
        if cur > base:
            regressions.append((f, base, cur))

    if regressions:
        print("[check] ❌ 以下文件的 mypy 错误数高于基线：")
        for f, base, cur in regressions:
            print(f"    {f}: 基线 {base} → 当前 {cur} (+{cur - base})")
        return 1

    if cur_total > base_total:
        print(
            f"[check] ❌ 基线总数上升：{base_total} → {cur_total} "
            f"（+{cur_total - base_total}），违反单调不增",
        )
        return 1

    scope = f"限定 {len(wanted)} 个文件" if wanted else "全量"
    print(f"[check] ✅ 通过（{scope}）：无文件错误数上升，总数 {cur_total} ≤ 基线 {base_total}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="mypy 基线生成与增量校验")
    ap.add_argument("--check", action="store_true", help="校验模式（默认生成模式）")
    ap.add_argument("--files", nargs="*", help="只校验这些文件（CI 传 diff 列表）")
    ap.add_argument("--stdin", action="store_true", help="从 stdin 读取待校验文件列表")
    ap.add_argument("--target", default=DEFAULT_TARGET, help="mypy 检查目标，默认 app")
    ap.add_argument("--baseline", default=str(DEFAULT_BASELINE), help="基线文件路径")
    args = ap.parse_args()

    out = Path(args.baseline).resolve()
    files = list(args.files or [])
    if args.stdin:
        files += sys.stdin.read().splitlines()

    if args.check:
        return cmd_check(args.target, out, files or None)
    return cmd_gen(args.target, out)


if __name__ == "__main__":
    raise SystemExit(main())

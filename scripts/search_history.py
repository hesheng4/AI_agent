#!/usr/bin/env python3
"""昇腾历史记录搜索脚本

遵循 ascend-history-to-skill skill 规范 Step 2:
搜索 Codex / Claude Code / OpenCode / Cursor 历史记录，
提取目标模型的适配、优化、验证记录。

用法:
    python scripts/search_history.py --model esm2 --stage adapt,optimize
    python scripts/search_history.py --model esm2 --keyword torch_npu --keyword TASK_QUEUE_ENABLE
    python scripts/search_history.py --model esm2 --output json
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.history_to_skill import (
    HistorySource,
    discover_history_roots,
    extract_skill_material,
    filter_high_value_hits,
    normalize_model_name,
    search_history,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="昇腾历史记录搜索 (ascend-history-to-skill Step 2)"
    )
    parser.add_argument(
        "--model", required=True, help="目标模型名，如 esm2、DiffSBDD、Boltz2"
    )
    parser.add_argument(
        "--stage",
        default="adapt,optimize",
        help="阶段过滤 (逗号分隔)，默认 adapt,optimize",
    )
    parser.add_argument(
        "--keyword", action="append", default=[], help="额外搜索关键词 (可多次使用)"
    )
    parser.add_argument(
        "--source",
        action="append",
        default=None,
        choices=["codex", "claude-code", "opencode", "cursor"],
        help="限制搜索来源 (可多次使用)",
    )
    parser.add_argument(
        "--root", action="append", default=[], help="额外搜索路径 (可多次使用)"
    )
    parser.add_argument(
        "--exclude", action="append", default=[], help="排除关键词 (可多次使用)"
    )
    parser.add_argument(
        "--max-hits", type=int, default=100, help="最大命中数 (default: 100)"
    )
    parser.add_argument(
        "--output",
        choices=["markdown", "json"],
        default="markdown",
        help="输出格式 (default: markdown)",
    )
    parser.add_argument("--filter-only", action="store_true", help="仅显示高价值证据")
    parser.add_argument(
        "--material", action="store_true", help="同时输出整理后的 Skill 素材"
    )
    parser.add_argument("--variants", action="store_true", help="显示模型名变体")
    parser.add_argument(
        "--discover-roots", action="store_true", help="仅显示可用历史记录根目录"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # 显示模型名变体
    if args.variants:
        variants = normalize_model_name(args.model)
        print("模型名变体:")
        for v in variants:
            print(f"  - {v}")
        return

    # 发现历史根目录
    sources = None
    if args.source:
        sources = [HistorySource(s) for s in args.source]

    if args.discover_roots:
        roots = discover_history_roots(sources, args.root or None)
        if not roots:
            print("未找到任何历史记录根目录")
            print("可使用 --root 参数手动指定路径")
        else:
            print("可用历史记录根目录:")
            for src, paths in roots.items():
                print(f"  [{src.value}]")
                for p in paths:
                    print(f"    - {p}")
        return

    # 解析阶段
    stages = [s.strip() for s in args.stage.split(",")]

    # 搜索
    hits = search_history(
        model_name=args.model,
        stages=stages,
        keywords=args.keyword or None,
        sources=sources,
        extra_roots=args.root or None,
        exclude_terms=args.exclude or None,
        max_hits=args.max_hits,
    )

    # 过滤
    if args.filter_only:
        hits = filter_high_value_hits(hits)

    # 输出
    if args.output == "json":
        output_data = {
            "model": args.model,
            "stages": stages,
            "hits_count": len(hits),
            "hits": [h.to_dict() for h in hits],
        }
        if args.material and hits:
            material = extract_skill_material(args.model, hits)
            output_data["material"] = material.to_dict()
        print(json.dumps(output_data, indent=2, ensure_ascii=False))
    else:
        print("=" * 60)
        print(f"昇腾历史搜索: {args.model}")
        print("=" * 60)
        print("阶段: {}".format(", ".join(stages)))
        print(f"命中: {len(hits)} 条")
        print("")

        for i, hit in enumerate(hits):
            print(f"--- Hit {i + 1} ---")
            print(f"来源: {hit.source.value}")
            print(f"路径: {hit.file_path}")
            print(f"评分: {hit.score:.1f}")
            print(f"证据: {hit.evidence_level.value}")
            print("关键词: {}".format(", ".join(hit.keywords[:5])))
            print(f"内容预览: {hit.content[:200]}...")
            print("")

        if args.material and hits:
            material = extract_skill_material(args.model, hits)
            print("=" * 60)
            print("Skill 素材摘要")
            print("=" * 60)
            print(json.dumps(material.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

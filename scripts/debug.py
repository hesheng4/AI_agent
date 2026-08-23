#!/usr/bin/env python3
"""系统化调试 CLI

遵循 systematic-debugging skill 规范四阶段流程。

用法:
    # 快速诊断
    python scripts/debug.py diagnose "ImportError: No module named 'torch_npu'"

    # 创建调试会话
    python scripts/debug.py session create --title "vLLM 启动失败"

    # Phase 1: 根因调查
    python scripts/debug.py phase1 read-error --session debug_20250101_1 --error "error text"
    python scripts/debug.py phase1 repro --session debug_20250101_1 --steps "step1" "step2"
    python scripts/debug.py phase1 recent-changes --session debug_20250101_1
    python scripts/debug.py phase1 summarize --session debug_20250101_1 --summary "根因是..."

    # Phase 2: 模式分析
    python scripts/debug.py phase2 working-example --session debug_20250101_1 --desc "xxx 工作正常"

    # Phase 3: 假设测试
    python scripts/debug.py phase3 hypothesize --session debug_20250101_1 --statement "X是根因" --because "Y"
    python scripts/debug.py phase3 test --session debug_20250101_1 --id 1 --result confirmed

    # Phase 4: 实施
    python scripts/debug.py phase4 failing-test --session debug_20250101_1 --desc "测试X"
    python scripts/debug.py phase4 apply-fix --session debug_20250101_1 --desc "修复X" --passed

    # 查看报告
    python scripts/debug.py report --session debug_20250101_1

    # 检查红旗
    python scripts/debug.py red-flags --session debug_20250101_1
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.debugging import (
    DebugSessionManager,
    FixImplementer,
    HypothesisTester,
    PatternAnalyzer,
    RootCauseInvestigator,
    generate_debug_report,
    quick_diagnose,
)


def main():
    parser = argparse.ArgumentParser(description="系统化调试 CLI")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # diagnose
    diag_parser = subparsers.add_parser("diagnose", help="快速诊断错误信息")
    diag_parser.add_argument("error_text", help="错误信息")

    # session
    sess_parser = subparsers.add_parser("session", help="会话管理")
    sess_sub = sess_parser.add_subparsers(dest="sess_action")
    create_parser = sess_sub.add_parser("create", help="创建会话")
    create_parser.add_argument("--title", default="", help="会话标题")
    sess_sub.add_parser("list", help="列出会话")
    show_parser = sess_sub.add_parser("show", help="查看会话")
    show_parser.add_argument("--session", required=True, help="会话 ID")

    # phase1
    p1_parser = subparsers.add_parser("phase1", help="Phase 1: 根因调查")
    p1_sub = p1_parser.add_subparsers(dest="p1_action")
    p1_sub.add_parser("checklist", help="Phase 1 检查清单")

    read_err = p1_sub.add_parser("read-error", help="阅读错误信息")
    read_err.add_argument("--session", required=True, help="会话 ID")
    read_err.add_argument("--error", required=True, help="错误文本")

    parse_trace = p1_sub.add_parser("parse-trace", help="解析堆栈跟踪")
    parse_trace.add_argument("--session", required=True, help="会话 ID")
    parse_trace.add_argument("--trace", required=True, help="堆栈跟踪文本")

    repro = p1_sub.add_parser("repro", help="记录复现步骤")
    repro.add_argument("--session", required=True, help="会话 ID")
    repro.add_argument("--steps", nargs="+", required=True, help="复现步骤")

    recent = p1_sub.add_parser("recent-changes", help="检查最近变更")
    recent.add_argument("--session", required=True, help="会话 ID")
    recent.add_argument("--repo", default=".", help="仓库路径")

    boundary = p1_sub.add_parser("boundary", help="收集边界证据")
    boundary.add_argument("--session", required=True, help="会话 ID")
    boundary.add_argument("--component", required=True, help="组件名")
    boundary.add_argument("--input", default=None, help="输入数据")
    boundary.add_argument("--output", default=None, help="输出数据")

    trace_rc = p1_sub.add_parser("trace-root", help="追溯根因")
    trace_rc.add_argument("--session", required=True, help="会话 ID")
    trace_rc.add_argument("--error-point", required=True, help="错误位置")
    trace_rc.add_argument("--bad-value", required=True, help="错误值")
    trace_rc.add_argument("--expected-value", required=True, help="期望值")

    summarize = p1_sub.add_parser("summarize", help="总结根因 (Phase 1 完成)")
    summarize.add_argument("--session", required=True, help="会话 ID")
    summarize.add_argument("--summary", required=True, help="根因总结")

    # phase2
    p2_parser = subparsers.add_parser("phase2", help="Phase 2: 模式分析")
    p2_sub = p2_parser.add_subparsers(dest="p2_action")

    working = p2_sub.add_parser("working-example", help="添加工作示例")
    working.add_argument("--session", required=True, help="会话 ID")
    working.add_argument("--desc", required=True, help="示例描述")
    working.add_argument("--path", default="", help="代码路径")

    deps = p2_sub.add_parser("dependencies", help="分析依赖")
    deps.add_argument("--session", required=True, help="会话 ID")
    deps.add_argument("--file", required=True, help="目标文件")

    # phase3
    p3_parser = subparsers.add_parser("phase3", help="Phase 3: 假设测试")
    p3_sub = p3_parser.add_subparsers(dest="p3_action")

    hypo = p3_sub.add_parser("hypothesize", help="形成假设")
    hypo.add_argument("--session", required=True, help="会话 ID")
    hypo.add_argument("--statement", required=True, help="假设陈述")
    hypo.add_argument("--because", default="", help="原因")

    test_h = p3_sub.add_parser("test", help="测试假设")
    test_h.add_argument("--session", required=True, help="会话 ID")
    test_h.add_argument("--id", type=int, required=True, help="假设 ID")
    test_h.add_argument(
        "--result", required=True, choices=["confirmed", "rejected", "inconclusive"]
    )
    test_h.add_argument("--desc", default="", help="测试描述")
    test_h.add_argument("--change", default="", help="最小变更")

    next_action = p3_sub.add_parser("next-action", help="获取下一步")
    next_action.add_argument("--session", required=True, help="会话 ID")

    # phase4
    p4_parser = subparsers.add_parser("phase4", help="Phase 4: 实施")
    p4_sub = p4_parser.add_subparsers(dest="p4_action")

    fail_test = p4_sub.add_parser("failing-test", help="创建失败测试")
    fail_test.add_argument("--session", required=True, help="会话 ID")
    fail_test.add_argument("--desc", required=True, help="测试描述")

    apply_fix = p4_sub.add_parser("apply-fix", help="应用修复")
    apply_fix.add_argument("--session", required=True, help="会话 ID")
    apply_fix.add_argument("--desc", required=True, help="修复描述")
    apply_fix.add_argument("--root-cause", required=True, help="针对的根因")
    apply_fix.add_argument("--passed", action="store_true", help="修复后测试通过")
    apply_fix.add_argument("--broken", action="store_true", help="破坏了其他测试")

    question = p4_sub.add_parser("question-arch", help="质疑架构")
    question.add_argument("--session", required=True, help="会话 ID")
    question.add_argument("--discussion", required=True, help="架构讨论")

    # report
    report_parser = subparsers.add_parser("report", help="生成调试报告")
    report_parser.add_argument("--session", required=True, help="会话 ID")

    # red-flags
    flags_parser = subparsers.add_parser("red-flags", help="检查红旗")
    flags_parser.add_argument("--session", required=True, help="会话 ID")

    args = parser.parse_args()
    manager = DebugSessionManager()

    if args.command == "diagnose":
        result = quick_diagnose(args.error_text)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.command == "session":
        if args.sess_action == "create":
            session = manager.create_session(args.title)
            print(json.dumps(session.to_dict(), indent=2, ensure_ascii=False))
        elif args.sess_action == "list":
            print(json.dumps(manager.list_sessions(), indent=2, ensure_ascii=False))
        elif args.sess_action == "show":
            session = manager.get_session(args.session)
            if session:
                print(json.dumps(session.to_dict(), indent=2, ensure_ascii=False))
            else:
                print(f"会话不存在: {args.session}")
        return

    # 以下命令需要 session
    def get_session(sid):
        s = manager.get_session(sid)
        if not s:
            print(f"会话不存在: {sid}")
            sys.exit(1)
        return s

    if args.command == "phase1":
        if args.p1_action == "read-error":
            session = get_session(args.session)
            inv = RootCauseInvestigator(session)
            evidence = inv.read_error_message(args.error)
            print(json.dumps(evidence.to_dict(), indent=2, ensure_ascii=False))

        elif args.p1_action == "parse-trace":
            session = get_session(args.session)
            inv = RootCauseInvestigator(session)
            evidence = inv.parse_stack_trace(args.trace)
            print(json.dumps(evidence.to_dict(), indent=2, ensure_ascii=False))

        elif args.p1_action == "repro":
            session = get_session(args.session)
            inv = RootCauseInvestigator(session)
            inv.add_reproduction_steps(args.steps)
            print(json.dumps({"repro_steps": args.steps}, indent=2, ensure_ascii=False))

        elif args.p1_action == "recent-changes":
            session = get_session(args.session)
            inv = RootCauseInvestigator(session)
            changes = inv.check_recent_changes(args.repo)
            print(json.dumps(changes, indent=2, ensure_ascii=False))

        elif args.p1_action == "boundary":
            session = get_session(args.session)
            inv = RootCauseInvestigator(session)
            evidence = inv.gather_boundary_evidence(
                args.component,
                args.input,
                args.output,
            )
            print(json.dumps(evidence.to_dict(), indent=2, ensure_ascii=False))

        elif args.p1_action == "trace-root":
            session = get_session(args.session)
            inv = RootCauseInvestigator(session)
            trace = inv.trace_root_cause(
                args.error_point,
                args.bad_value,
                args.expected_value,
                [],
            )
            print(json.dumps(trace.to_dict(), indent=2, ensure_ascii=False))

        elif args.p1_action == "summarize":
            session = get_session(args.session)
            inv = RootCauseInvestigator(session)
            inv.summarize_root_cause(args.summary)
            p1_complete = inv.is_phase1_complete()
            print(
                json.dumps(
                    {
                        "root_cause_summary": args.summary,
                        "phase1_complete": p1_complete,
                        "current_phase": session.current_phase.value,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )

        elif args.p1_action == "checklist":
            print("Phase 1 检查清单:")
            print("  [ ] 仔细阅读错误信息 (不要跳过)")
            print("  [ ] 一致地复现 (可靠触发?)")
            print("  [ ] 检查最近变更 (git diff/log)")
            print("  [ ] 收集多组件边界证据")
            print("  [ ] 追溯数据流 (从错误点到源头)")
            print("  [ ] 总结根因 (WHAT 和 WHY)")

    elif args.command == "phase2":
        if args.p2_action == "working-example":
            session = get_session(args.session)
            analyzer = PatternAnalyzer(session)
            analyzer.add_working_example(args.desc, args.path)
            print(json.dumps({"added": True}, indent=2, ensure_ascii=False))

        elif args.p2_action == "dependencies":
            session = get_session(args.session)
            analyzer = PatternAnalyzer(session)
            analysis = analyzer.analyze_dependencies(args.file)
            print(json.dumps(analysis, indent=2, ensure_ascii=False))

    elif args.command == "phase3":
        if args.p3_action == "hypothesize":
            session = get_session(args.session)
            tester = HypothesisTester(session)
            h = tester.form_hypothesis(args.statement, args.because)
            print(json.dumps(h.to_dict(), indent=2, ensure_ascii=False))

        elif args.p3_action == "test":
            session = get_session(args.session)
            tester = HypothesisTester(session)
            h = tester.test_hypothesis(args.id, args.desc, args.change, args.result)
            print(json.dumps(h.to_dict(), indent=2, ensure_ascii=False))

        elif args.p3_action == "next-action":
            session = get_session(args.session)
            tester = HypothesisTester(session)
            action = tester.get_next_action()
            print(json.dumps({"next_action": action}, indent=2, ensure_ascii=False))

    elif args.command == "phase4":
        if args.p4_action == "failing-test":
            session = get_session(args.session)
            impl = FixImplementer(session)
            attempt = impl.create_failing_test(args.desc)
            print(json.dumps(attempt.to_dict(), indent=2, ensure_ascii=False))

        elif args.p4_action == "apply-fix":
            session = get_session(args.session)
            impl = FixImplementer(session)
            attempt = impl.apply_fix(
                args.root_cause,
                args.desc,
                args.passed,
                args.broken,
            )
            flags = RootCauseInvestigator(session).check_red_flags()
            print(
                json.dumps(
                    {
                        **attempt.to_dict(),
                        "red_flags": flags,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )

        elif args.p4_action == "question-arch":
            session = get_session(args.session)
            impl = FixImplementer(session)
            impl.question_architecture(args.discussion)
            print(
                json.dumps(
                    {
                        "architecture_questioned": True,
                        "recommendation": "停止修复，与团队讨论架构方案",
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )

    elif args.command == "report":
        session = get_session(args.session)
        report = generate_debug_report(session)
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))

    elif args.command == "red-flags":
        session = get_session(args.session)
        inv = RootCauseInvestigator(session)
        flags = inv.check_red_flags()
        print(
            json.dumps(
                {
                    "red_flags": flags,
                    "architecture_questioned": session.architecture_questioned,
                },
                indent=2,
                ensure_ascii=False,
            )
        )

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

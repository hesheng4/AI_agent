# 系统化调试快速参考

## 铁律

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

## 四阶段流程

```
Phase 1: Root Cause ──→ Phase 2: Pattern ──→ Phase 3: Hypothesis ──→ Phase 4: Implementation
  仔细读错误              找工作示例            单一假设                失败测试先行
  一致复现                对比差异              最小测试                单点修复
  查变更                  理解依赖              验证后继续              3+失败→质疑架构
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/debugging/status` | 模块状态 |
| GET | `/api/v1/debugging/sessions` | 列出会话 |
| POST | `/api/v1/debugging/sessions` | 创建会话 |
| GET | `/api/v1/debugging/sessions/{id}` | 查看会话 |
| POST | `/api/v1/debugging/phase1/read-error` | Phase 1: 读错误 |
| POST | `/api/v1/debugging/phase1/parse-trace` | Phase 1: 解析堆栈 |
| POST | `/api/v1/debugging/phase1/repro-steps` | Phase 1: 复现步骤 |
| POST | `/api/v1/debugging/phase1/recent-changes` | Phase 1: 检查变更 |
| POST | `/api/v1/debugging/phase1/boundary-evidence` | Phase 1: 边界证据 |
| POST | `/api/v1/debugging/phase1/trace-root-cause` | Phase 1: 追溯根因 |
| POST | `/api/v1/debugging/phase1/summarize-root-cause` | Phase 1: 总结 |
| POST | `/api/v1/debugging/phase2/working-example` | Phase 2: 工作示例 |
| POST | `/api/v1/debugging/phase2/compare` | Phase 2: 对比 |
| POST | `/api/v1/debugging/phase2/dependencies` | Phase 2: 依赖分析 |
| POST | `/api/v1/debugging/phase3/hypothesis` | Phase 3: 形成假设 |
| POST | `/api/v1/debugging/phase3/test-hypothesis` | Phase 3: 测试假设 |
| GET | `/api/v1/debugging/phase3/next-action/{id}` | Phase 3: 下一步 |
| POST | `/api/v1/debugging/phase4/failing-test` | Phase 4: 失败测试 |
| POST | `/api/v1/debugging/phase4/apply-fix` | Phase 4: 应用修复 |
| POST | `/api/v1/debugging/phase4/question-architecture` | Phase 4: 质疑架构 |
| POST | `/api/v1/debugging/quick-diagnose` | 快速诊断 |
| GET | `/api/v1/debugging/report/{id}` | 调试报告 |
| GET | `/api/v1/debugging/red-flags/{id}` | 红旗检查 |
| GET | `/api/v1/debugging/quick-reference` | 快速参考 |

## CLI 用法

```bash
# 快速诊断
python scripts/debug.py diagnose "ImportError: No module named 'torch_npu'"

# 创建会话
python scripts/debug.py session create --title "vLLM 启动失败"

# Phase 1
python scripts/debug.py phase1 read-error --session ID --error "error text"
python scripts/debug.py phase1 repro --session ID --steps "step1" "step2"
python scripts/debug.py phase1 recent-changes --session ID
python scripts/debug.py phase1 summarize --session ID --summary "根因是..."

# Phase 2
python scripts/debug.py phase2 working-example --session ID --desc "xxx 工作正常"

# Phase 3
python scripts/debug.py phase3 hypothesize --session ID --statement "X是根因" --because "Y"
python scripts/debug.py phase3 test --session ID --id 1 --result confirmed

# Phase 4
python scripts/debug.py phase4 failing-test --session ID --desc "测试X"
python scripts/debug.py phase4 apply-fix --session ID --desc "修复X" --root-cause "根因" --passed

# 报告与红旗
python scripts/debug.py report --session ID
python scripts/debug.py red-flags --session ID
```

## Phase 检查清单

| Phase | 必须完成 | 才能进入下一阶段 |
|-------|---------|-----------------|
| 1. Root Cause | 有错误证据 + 复现步骤 + 根因总结 | Phase 2 |
| 2. Pattern | 有工作示例或差异对比 | Phase 3 |
| 3. Hypothesis | 有确认的假设 | Phase 4 |
| 4. Implementation | 失败测试 → 修复 → 验证通过 | 完成 |

## 红旗 — 命中必须停止

| 红旗 | 含义 |
|------|------|
| "Quick fix for now" | 必须先调查根因 |
| "Just try X" | 猜测不是调试 |
| "Multiple changes at once" | 无法隔离原因 |
| "Skip the test" | 无测试的修复不可靠 |
| 3+ 修复失败 | 质疑架构，不要继续修 |

## 常见错误类型诊断

| 错误类型 | 建议调查 |
|---------|---------|
| ImportError | pip list, conda info, sys.path |
| FileNotFoundError | ls -la, pwd, readlink |
| ConnectionError | curl health, ss -tlnp, iptables |
| TimeoutError | ping, top, 增加超时 |
| MemoryError | free -h, npu-smi, 减小 batch_size |

## 防御性借口 → 现实

| 借口 | 现实 |
|------|------|
| "问题简单，不需要流程" | 简单问题也有根因 |
| "紧急，没时间" | 系统化比瞎试更快 |
| "先试试这个" | 第一个修复定基调 |
| "确认后再写测试" | 无测试的修不了 |
| "一次改多个" | 无法隔离哪个有效 |
| "再试一次修复" | 3+失败 = 架构问题 |

# 昇腾历史转 Skill 快速参考

## 流程

```
1. 明确目标 ──→ 2. 搜索历史 ──→ 3. 过滤证据 ──→ 4. 整理素材 ──→ 5. 生成 Skill ──→ 6. 验证
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/history-to-skill/status` | 模块状态 |
| GET | `/api/v1/history-to-skill/variants/{model_name}` | Step 1: 模型名变体 |
| GET | `/api/v1/history-to-skill/roots` | Step 2: 发现历史根目录 |
| POST | `/api/v1/history-to-skill/search` | Step 2-3: 搜索+过滤 |
| POST | `/api/v1/history-to-skill/generate` | Step 5: 生成 Skill |
| POST | `/api/v1/history-to-skill/run` | 一键完整流程 (1-6) |
| POST | `/api/v1/history-to-skill/validate` | Step 6: 验证 Skill |
| GET | `/api/v1/history-to-skill/quick-reference` | 快速参考 |

## CLI 搜索

```bash
# 基本搜索
python scripts/search_history.py --model esm2 --stage adapt,optimize

# 带关键词
python scripts/search_history.py --model esm2 --keyword torch_npu --keyword TASK_QUEUE_ENABLE

# 指定来源
python scripts/search_history.py --model esm2 --source codex --source claude-code

# 额外搜索路径
python scripts/search_history.py --model esm2 --root /path/to/history

# 输出 JSON
python scripts/search_history.py --model esm2 --output json

# 仅高价值证据 + 素材提取
python scripts/search_history.py --model esm2 --filter-only --material

# 模型名变体
python scripts/search_history.py --model esm2 --variants

# 发现根目录
python scripts/search_history.py --model esm2 --discover-roots
```

## 支持的历史来源

| 来源 | 默认路径 |
|------|----------|
| Codex | `~/.codex/sessions`, `~/.codex/history` |
| Claude Code | `~/.claude/projects`, `~/.claude/sessions` |
| OpenCode | `~/.opencode/sessions`, `~/.local/share/opencode` |
| Cursor | `~/.cursor/sessions`, `~/Library/Application Support/Cursor/...` |

## 证据等级

| 等级 | 含义 | 评分权重 |
|------|------|----------|
| `verified` | 已验证，有运行输出 | 最高 |
| `likely` | 有代码修改，无明确输出 | 高 |
| `discussion` | 仅讨论 | 低 |
| `unverified` | 未验证 | 最低 |

## 过滤规则

**优先保留：**
- 明确的环境创建与依赖安装命令
- 已落地的代码修改点、脚本路径、关键参数
- 真实跑通的验证命令和输出产物
- 有数字的性能对比、精度对比、benchmark 结论
- 真实报错及对应修复

**降权/丢弃：**
- 只有用户提问、没有执行结果的片段
- 纯 brainstorming、没有落地命令的讨论
- 与目标模型无关、只共享"昇腾"关键词的记录
- 被后续记录推翻的旧方案

## Skill 输出结构

```
~/.codex/skills/<model-skill-name>/
├── SKILL.md              # 主 Skill 文件
├── scripts/
│   ├── verify.sh         # 验证脚本
│   └── setup_env.sh      # 环境变量脚本
└── references/
    └── hits_summary.json # 原始命中摘要
```

## Skill 素材提取

从历史记录中自动提取：

| 类别 | 提取内容 |
|------|----------|
| 环境信息 | Python/PyTorch/torch_npu/CANN 版本、conda 环境名 |
| 适配步骤 | CUDA API 替换、第三方库修复、分布式约束 |
| 优化步骤 | 运行时环境变量、benchmark 结果 |
| 验证步骤 | 测试/评估/benchmark 命令 |
| 常见问题 | 错误信息和修复方案 |

# Skills 去重完成报告 (2026-08-15)

目录：`C:\Users\yangy\.atomcode\skills`

## 结果总览

- 初始技能数：**228** 个技能目录（含 1 个 `skills.sh.json` 数据文件、`_references` 知识库）
- 当前技能数：**152** 个（全部为独立功能，已无同功能重复项）
- 共移除：**76** 个（其中 12 个移入回收目录可恢复，其余已删除）

## 删除记录

完整逐条记录见 `C:\Users\yangy\.atomcode\skills\.deleted_skills_20260814.txt`，分四轮：

| 轮次 | 数量 | 说明 |
|---|---|---|
| 第 1 轮 (08-14) | 22 | 明确同功能组，保留一项（如 design-system-generator→theme-factory、frontend-design→frontend-ui-engineering 等） |
| 第 2 轮 (08-15) | 11+1 | 空壳目录（无 SKILL.md 不可加载）及 component-interface-design |
| 第 3 轮 (08-15) | 12 | 移入 `~/.atomcode/.trash-skills-20260814`（可恢复）：academic-figures、agent-skills-hub、ai4s-main、capability-architect、document-chat-interface、interactive-component-creator、planning-documentation、protocol-implementation-framework、skills-hub、writing-skills、grill-me、grill-with-docs |
| 第 4 轮 (08-15) | 11 | 补录此前未记日志的删除项（ascend-optimization、browser-testing-with-devtools、capability-documentation、dispatching-parallel-agents、frontend-ui-engineering、impeccable、knowledge-distribution、research-management、skills.sh.json、subagent-driven-development、webapp-testing） |

## 保留原则

每组同功能技能仅保留一项，优先保留：功能更全、维护活跃、与自研主线（数学建模/昇腾 AI4S/Nature 论文）配套的技能。例如：

- TDD → `test-driven-development`
- 调试 → `systematic-debugging`
- 浏览器 → `agent-browser`
- 文档格式 → `docx` / `pptx` / `xlsx` / `pdf`（各保留一个）
- 技能管理 → `skill-creator` + `using-agent-skills`
- 前端 UI → `ui-ux-pro-max` / `web-artifacts-builder` / `react-bits-artisan`
- 昇腾迁移 → `ai4s-basic` + 各模型专属技能
- 论文流水线 → `paper-spine-*` 套件、`nature-*` 套件（套件内子技能各司其职，不视为重复）

## 边界说明（保留但功能相近）

以下技能功能相近但侧重点不同，保留未删；如仍需精简可在回收目录恢复后自行取舍：

- `find-skills`（安装外部技能） vs `using-agent-skills`（调用本地技能）
- `brand-guidelines`（Anthropic 品牌规范） vs `identity-framework`（品牌身份体系）
- `canvas-design`（海报/静态作品） vs `visual-composition`（版式构图） vs `visual-quality-improver`（图像增强）

## 恢复方法

第 3 轮删除项仍保存在 `~/.atomcode/.trash-skills-20260814/`，如需恢复，将该目录下的技能文件夹复制回 `C:\Users\yangy\.atomcode\skills\` 即可。

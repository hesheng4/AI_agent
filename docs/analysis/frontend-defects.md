# 前端缺陷分析

## 一、功能缺失 — 13 模块无前端

| 模块 | 后端端点 | 影响 |
|------|---------|------|
| reader | `/reader/read-full` | 论文精读断链 |
| reviewer | `/reviewer/assess`, `quick-check` | 审稿能力零暴露 |
| response | `/response/draft`, `audit`, `revise` | 审稿回复流程断 |
| citation | `/citation/add`, `verify`, `format-references` | 引用管理缺失 |
| figure | `/figure/create-contract`, `apply-style`, `qa-check` | 图表合同制缺失 |
| paper2ppt | `/paper2ppt/generate` | 论文转PPT不可用 |
| paper-to-patent | `/paper-to-patent/draft` | 论文转专利不可用 |
| coordinator | `/coordinator/route`, `capability-map`, `workflow-templates` | 智能路由入口缺失 |
| export | `/export/csv/json/bibtex/ris/markdown` | 导出终点缺失 |
| cover | `/cover` | 封面生成缺 |
| methods | `/methods` | 方法论写作缺 |
| submission-package | `/submission-package` | 投稿打包缺 |
| polishing | `/polishing` | 独立端点未接 |
| stats | `/stats` | 统计模块缺 |

## 二、API 层不完整

| 模块 | 已接 | 缺失 |
|------|------|------|
| literature | search, read | summarize, citations, references, network×5, graph×7 |
| writing | outline, polish, check | generate, word-count, structure, terminology, evidence, detect-type, export-latex |
| data | analyze | visualize, upload |
| experiment | design, powerAnalysis | optimize, predict, statistical-test |

## 三、架构缺陷

| 缺陷 | 位置 | 说明 |
|------|------|------|
| 无全局错误边界 | App.tsx | 白屏无兜底 |
| 无请求取消 | 全部页面 | 卸载后 setState → 内存泄漏+竞态 |
| 无请求去重/缓存 | Library/Network | 重复请求无合并 |
| 状态全在组件内 | 每个页面 | 切换tab/tab丢失结果，无全局store |
| 无乐观更新 | Library | 操作等待后端返回才刷新 |
| types.ts 不完整 | 13模块 | Request/Response 类型未定义 |
| api.ts 大量 Record | ascend 8模块 | 返回值无类型约束 |

## 四、交互缺陷

| 缺陷 | 页面 | 说明 |
|------|------|------|
| 数据输入仅JSON | DataAnalysis | 无文件上传CSV/Excel |
| 无分页 | Library | 大量文献全加载 |
| 无排序 | Library | 无时间/标题/引用排序 |
| 引用网无可视化 | Network | nodes+edges 仅 JSON.stringify |
| 写作无连贯流程 | Writing | outline→generate→polish 割裂 |
| 润色无diff | Writing | 原文/润色无高亮差异 |
| 无草稿保存 | Writing | 刷新丢内容 |
| 无批量操作 | Library | 无多选删除/导出/打标签 |
| 删除用原生confirm | Library | 风格不统一 |
| Profile无密码修改 | Profile | 后端有但前端未接 |
| Profile无API连通测试 | Profile | 后端有但前端未接 |

## 五、导航缺陷

| 缺陷 | 说明 |
|------|------|
| 侧栏缺13个页面入口 | NAV_GROUPS 仅 6+9=15 项 |
| 无全局搜索/命令面板 | coordinator 能力未暴露 |
| 无面包屑导航 | 深层页面无路径 |

## 六、安全缺陷

| 缺陷 | 说明 |
|------|------|
| JWT 存 localStorage | XSS 可窃取 |
| 无 token 过期前端感知 | 401 仅清 token 无 refresh |
| API key 明文过前端 | 虽遮盖但POST明文 |

## 七、性能缺陷

| 缺陷 | 说明 |
|------|------|
| 无代码分割 | 首屏全量 JS |
| 无骨架屏 | Loading 仅转圈 |
| Library 全量加载 | 无虚拟滚动 |
| Network JSON 大序列化 | 数千节点卡顿 |

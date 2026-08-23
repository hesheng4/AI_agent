# 优化与实现需求清单

## 分批方案

### 第 1 批（核心链路打通）

| # | 功能 | 说明 |
|---|------|------|
| F1-core | reader/reviewer/response/citation/export/coordinator 模块 | API层+类型+页面 |
| F2 | 补全 literature(13)/writing(7)/data(2)/experiment(3) 缺失端点 | API层补全 |
| F3 | 引用网络可视化 | 力导向图替代 JSON.stringify |
| F4 | 写作流水线 | outline→generate→polish→check 串联 |

### 第 2 批（体验提升）

| # | 功能 | 说明 |
|---|------|------|
| F5 | 数据上传 | CSV/Excel 文件上传 |
| F6 | Library 分页+排序+批量操作 | 虚拟滚动、多选、批量操作 |
| F7 | 全局请求层重构 | SWR/React Query 缓存+去重+请求取消 |
| F8 | 润色 diff 高亮 | 标记增删改 |
| F9 | 草稿自动保存 | localStorage 自动暂存 |
| F10 | 导航补全+全局搜索 | 侧栏加入口，coordinator 命令面板 |

### 第 3 批（基建补强）

| # | 功能 | 说明 |
|---|------|------|
| F1-rest | figure/paper2ppt/paper-to-patent/cover/methods/submission-package/polishing/stats | 剩余模块 |
| F11 | 全局错误边界 | React ErrorBoundary |
| F12 | 代码分割 | React.lazy |
| F13 | JWT 安全加固 | 内存 token + httpOnly refresh |

## 约束
- 技术栈：React 18 + TypeScript + Tailwind + Framer Motion
- 网络图：react-force-graph-2d 或 @antv/g6
- 请求层：swr 或 @tanstack/react-query
- 不改后端 API 契约
- 不加 SSR，不换 UI 框架，不做国际化

## 不做项
- 后端 API 改造
- OAuth 登录
- 移动端适配
- 国际化

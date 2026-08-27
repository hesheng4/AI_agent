# 研究Agent平台 (Research Agent Platform)

高等教育科研效率提升AI Agent平台

## 功能特性

### 🤖 AI Agent 模块（20+ Agent，分两大工作台）

#### 科研工作台

| 模块 | Agent | 功能 | 状态 |
|------|-------|------|------|
| 智能路由 | `coordinator` | 任务规划 + Agent 调度 + 上游结果注入下游（`_inject_upstream`） | ✅ |
| 文献检索 | `literature` | Semantic Scholar/arXiv 搜索、AI 总结、引用格式化 | ✅ |
| 论文精读 | `reader` | 分章节深度解读、结构化摘要、批判性问题 | ✅ |
| 文献库 | `library`（Service） | 收藏管理、分类标签、收藏标记、阅读笔记、统一 LibraryService 状态同步 | ✅ |
| 引用网络 | `citation` | 引用图谱、共引分析、影响力识别、研究脉络、前沿检测、聚类分析、时间线 | ✅ |
| 数据分析 | `data` / `data_agent` / `stats` | 描述统计、相关分析、回归、方差分析、非参数检验、生存分析、卡方检验、统计审计 | ✅ |
| 论文写作 | `writing` | 大纲生成、语法检查、AI 润色、引用管理、多格式导出 | ✅ |
| 实验设计 | `experiment` | 方案设计、统计检验推荐、参数优化、功效分析、功效曲线、敏感性分析 | ✅ |
| 模拟审稿 | `reviewer` | 期刊级多角色审稿模拟、修改建议 | ✅ |
| 审稿回复 | `response` | 逐条审稿意见回复生成 | ✅ |
| 图表合同 | `figure` | 科研图表生成、图注规范 | ✅ |
| Cover Letter | `cover` | 投稿信件智能生成 | ✅ |
| 方法论 | `methods` | 研究方法章节撰写 | ✅ |
| 专业润色 | `polishing` | 学术语言润色、降重 | ✅ |
| 论文转 PPT | `paper2ppt` | 论文一键转演示文稿 | ✅ |
| 论文转专利 | `paper_to_patent` | 研究成果专利化撰写 | ✅ |
| 投稿打包 | `submission_package` | 期刊投稿材料整合打包 | ✅ |
| 数据可用性 | `submission_package` | 数据可用性声明生成 | ✅ |
| 数据导出 | — | CSV / BibTeX / RIS / Word / LaTeX / 多格式论文导出 | ✅ |
| 计费管理 | — | 套餐限制、用量统计、API 调用频率控制 | ✅ |

#### 昇腾工作台（本地化推理）

| 模块 | Agent / 核心 | 功能 | 状态 |
|------|------|------|------|
| 环境概览 | `ascend` | NPU 环境检测、设备管理、资源监控 | ✅ |
| 模型适配 | `adaptation` | 远程/昇腾模型切换、适配层封装 | ✅ |
| 精度对齐 | `alignment` | 远程 vs 本地推理精度对齐验证 | ✅ |
| 性能采集 | `profiling` | NPU 性能数据采集 | ✅ |
| 性能调优 | `perf_tuning` | 推理性能参数调优 | ✅ |
| 推理工具链 | `toolchain` | vLLM-Ascend 工具链集成 | ✅ |
| 模型验证 | `validator` | 模型推理质量验证 | ✅ |
| 调试辅助 | `debugging` | NPU 推理调试支持 | ✅ |
| 历史转技能 | `history_to_skill` | 历史记录转可复用技能 | ✅ |

### 🔧 系统特性

- ✅ 错误处理 + 自动重试
- ✅ **双后端缓存**（内存 / Redis）+ LLM缓存，支持多实例部署与优雅降级
- ✅ **双后端限流**（内存 / Redis ZSET+Lua 滑动窗口），支持多实例
- ✅ **Alembic 数据库迁移**（async env + render_as_batch，SQLite 兼容）
- ✅ 并行Agent执行 + Agent 间结果传递（coordinator `_inject_upstream`）
- ✅ 向量检索 (Milvus)
- ✅ 日志系统
- ✅ **前端界面**（React 18 + TypeScript + Tailwind CSS + React Bits 动画组件）
- ✅ 安全认证 (JWT + 密码哈希)
- ✅ **统一 LibraryService**（文献/分类/标签/引用/笔记/统计 6 子服务，完整状态同步）
- ✅ 文献收藏状态同步（搜索结果与文献库联动）

## 快速开始

### 方式一：本地开发

```bash
# 1. 克隆项目
git clone <repository-url>
cd research-agent-platform

# 2. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate  # Windows

# 3. 安装后端依赖
pip install -r requirements.txt
# 或
poetry install

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，配置 OPENAI_API_KEY

# 5. （可选）构建前端
cd frontend
npm install
npm run build    # 构建到 frontend/dist/
cd ..

# 6. 启动服务
make run
# 或
uvicorn app.main:app --reload

# 7. 访问
# 前端: http://localhost:8000
# API文档: http://localhost:8000/docs
```

### 前端开发模式（热更新）

```bash
cd frontend
npm install      # 首次安装依赖
npm run dev      # 启动 Vite 开发服务器 http://localhost:5173
                  # 自动代理 /api 到后端 http://localhost:8000
npm run build    # 构建生产版本到 dist/
npm run preview  # 预览构建产物
```

### 方式二：Docker部署

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 文件

# 2. 启动服务
make docker-up
# 或
docker-compose up -d

# 3. 查看状态
make docker-ps

# 4. 查看日志
make docker-logs
```

## 项目结构

```
research-agent-platform/
├── app/                        # 应用代码
│   ├── agents/                 # AI Agent 模块（20+ Agent）
│   │   ├── base.py            # Agent 基类
│   │   ├── registry.py        # Agent 自动注册（目录扫描，manifest 不参与运行时）
│   │   ├── coordinator/       # 协调器（规划+调度+Agent 间结果传递）
│   │   ├── literature/        # 文献 Agent（搜索+总结+引用）
│   │   ├── reader/            # 论文精读 Agent
│   │   ├── citation/          # 引用网络 Agent（图谱/共引/聚类/前沿/脉络）
│   │   ├── data/              # 数据 Agent（统计+回归+方差+非参数+生存+卡方）
│   │   ├── data_agent/        # 数据 Agent（增强版）
│   │   ├── stats/             # 统计审计 Agent
│   │   ├── writing/           # 写作 Agent（大纲+润色+语法+引用+导出）
│   │   ├── experiment/        # 实验 Agent（设计+优化+功效分析+功效曲线+敏感性）
│   │   ├── reviewer/          # 模拟审稿 Agent
│   │   ├── response/          # 审稿回复 Agent
│   │   ├── figure/            # 图表合同 Agent
│   │   ├── cover/             # Cover Letter Agent
│   │   ├── methods/           # 方法论 Agent
│   │   ├── polishing/         # 专业润色 Agent
│   │   ├── paper2ppt/         # 论文转 PPT Agent
│   │   ├── paper_to_patent/   # 论文转专利 Agent
│   │   └── submission_package/# 投稿打包 Agent（含数据可用性声明）
│   ├── api/                   # API 路由
│   │   ├── deps.py            # 依赖注入（认证、数据库）
│   │   └── v1/               # v1 版本
│   │       ├── auth.py        # 认证（注册/登录）
│   │       ├── coordinator.py # 智能路由
│   │       ├── literature.py  # 文献检索
│   │       ├── library.py     # 文献库管理（调用 LibraryService）
│   │       ├── citation.py    # 引用管理
│   │       ├── reader.py      # 论文精读
│   │       ├── data.py        # 数据分析
│   │       ├── stats.py       # 统计审计
│   │       ├── writing.py     # 论文写作
│   │       ├── experiment.py  # 实验设计
│   │       ├── reviewer.py    # 模拟审稿
│   │       ├── response_api.py # 审稿回复
│   │       ├── figure.py      # 图表合同
│   │       ├── cover.py       # Cover Letter
│   │       ├── methods.py     # 方法论
│   │       ├── polishing.py   # 专业润色
│   │       ├── paper2ppt.py   # 论文转 PPT
│   │       ├── paper_to_patent.py # 论文转专利
│   │       ├── submission_package.py # 投稿打包
│   │       ├── data_availability.py # 数据可用性声明
│   │       ├── export.py      # 数据导出
│   │       ├── billing.py     # 计费管理
│   │       ├── ascend.py      # 昇腾 NPU 适配
│   │       ├── adaptation.py  # 模型适配
│   │       ├── alignment.py   # 精度对齐
│   │       ├── profiling.py   # 性能采集
│   │       ├── perf_tuning.py # 性能调优
│   │       ├── debugging.py   # 调试辅助
│   │       ├── toolchain.py   # 推理工具链
│   │       ├── validator.py   # 模型验证
│   │       └── history_to_skill.py # 历史记录转技能
│   ├── core/                  # 核心模块
│   │   ├── cache.py          # 缓存（CacheBackend ABC + Memory + Redis + 工厂）
│   │   ├── rate_limit.py     # 限流（RateLimiterBackend ABC + Memory + Redis ZSET+Lua）
│   │   ├── redis_client.py   # Redis 连接池管理
│   │   ├── database.py       # 数据库
│   │   ├── security.py       # 安全（JWT/密码哈希）
│   │   ├── billing.py        # 计费引擎
│   │   ├── vector_store.py   # 向量存储
│   │   ├── ascend.py         # 昇腾 NPU 核心
│   │   ├── adaptation.py     # 模型适配核心
│   │   ├── alignment.py      # 粀度对齐核心
│   │   ├── profiling.py      # 性能采集核心
│   │   ├── perf_tuning.py    # 性能调优核心
│   │   ├── debugging.py      # 调试核心
│   │   ├── toolchain.py      # 工具链核心
│   │   ├── validator.py      # 验证核心
│   │   └── history_to_skill.py # 历史记录转技能核心
│   ├── models/                # 数据模型
│   │   ├── user.py           # 用户模型
│   │   ├── billing.py        # 计费模型
│   │   ├── library.py        # 文献库模型（PaperCollection/Category/Tag/Citation/Note）
│   │   └── types.py          # 共享类型定义
│   ├── services/              # 业务服务层
│   │   ├── library_service.py    # 统一 LibraryService（6 子服务 + 状态同步）
│   │   ├── citation_network.py   # 引用网络分析（图谱/共引/聚类/前沿/脉络）
│   │   ├── power_analysis.py     # 功效分析（样本量/功效/效应量）
│   │   ├── statistics.py         # 统计增强（回归/方差/非参数/生存/卡方）
│   │   ├── reference.py          # 引用管理
│   │   ├── chart.py              # 图表生成
│   │   └── auth.py              # 认证服务
│   ├── utils/                 # 工具类
│   │   ├── llm.py            # LLM 客户端（远程/昇腾双后端）
│   │   ├── embedding.py      # Embedding
│   │   ├── latex_engine.py   # LaTeX 引擎
│   │   ├── logger.py         # 日志
│   │   ├── exceptions.py     # 异常定义
│   │   └── export.py         # 导出工具
│   ├── config.py              # 配置（含 CACHE_BACKEND/RATE_LIMIT_BACKEND/MIGRATION_ON_STARTUP）
│   └── main.py                # 入口（含 Alembic 迁移 + Redis 启停）
├── frontend/                  # 前端（React 18 + TypeScript + Vite + Tailwind）
│   ├── src/
│   │   ├── main.tsx          # React 入口
│   │   ├── App.tsx           # 根组件（路由）
│   │   ├── auth.tsx          # 认证上下文
│   │   ├── api.ts            # API 客户端封装
│   │   ├── types.ts          # 共享类型
│   │   ├── index.css         # 全局样式 + 设计系统
│   │   ├── components/       # 组件库
│   │   │   ├── Layout.tsx        # 主布局（顶部一体化导航 + 命令面板）
│   │   │   ├── CommandPalette.tsx # ⌘K 命令面板
│   │   │   ├── ConfirmDialog.tsx # 确认对话框
│   │   │   ├── ErrorBoundary.tsx # 错误边界
│   │   │   ├── Skeleton.tsx      # 骨架屏
│   │   │   ├── CountUp.tsx      # 数字滚动动画
│   │   │   ├── ui.tsx           # UI 基础组件
│   │   │   ├── Aurora.tsx        # WebGL 极光背景
│   │   │   ├── DecryptedText.tsx # 文字解密动画
│   │   │   ├── BlurText.tsx      # 模糊揭示动画
│   │   │   ├── Dock.tsx          # macOS 风格放大导航栏
│   │   │   └── StarBorder.tsx    # 星光流动边框
│   │   ├── pages/            # 页面（25+ 路由）
│   │   │   ├── Coordinator.tsx  Literature.tsx  Reader.tsx  Library.tsx
│   │   │   ├── Network.tsx  Citation.tsx  DataAnalysis.tsx  Writing.tsx
│   │   │   ├── Reviewer.tsx  Response.tsx  Experiment.tsx  Figure.tsx
│   │   │   ├── CoverLetter.tsx  MethodsPage.tsx  StatsPage.tsx  PolishingPage.tsx
│   │   │   ├── Paper2PPT.tsx  PaperToPatent.tsx  SubmissionPackage.tsx
│   │   │   ├── DataAvailability.tsx  Export.tsx  Login.tsx  Profile.tsx
│   │   │   └── ascend/         # 昇腾子页面（9 个）
│   │   └── sections/
│   │       └── Hero.tsx          # Hero 区（整合 5 个 React Bits 组件）
│   ├── index.html            # HTML 模板
│   ├── index_legacy.html     # 旧 Alpine.js 版本（备份）
│   ├── package.json          # npm 依赖
│   ├── vite.config.ts        # Vite 配置
│   ├── tsconfig.json         # TypeScript 配置
│   ├── tailwind.config.ts    # Tailwind 配置（墨观设计系统）
│   └── dist/                 # 构建产物（FastAPI 服务此目录）
├── migrations/                # Alembic 数据库迁移
│   ├── env.py                # async env（render_as_batch，SQLite 兼容）
│   ├── script.py.mako        # 迁移模板
│   └── versions/
│       └── 6ab33371ef5b_initial_baseline.py  # 初始 baseline（8 表 + 10 索引）
├── alembic.ini                # Alembic 配置
├── tests/                     # 测试
│   ├── unit/                 # 单元测试
│   ├── integration/          # 集成测试
│   ├── e2e/                  # 端到端测试
│   ├── performance/          # 性能测试
│   └── alignment/            # 精度对齐测试数据
├── scripts/                   # 脚本
│   ├── deploy.sh             # 部署脚本
│   ├── monitor.sh            # 监控脚本
│   ├── check_npu_env.py      # NPU 环境检测
│   ├── compare_inference.py  # 推理对比
│   ├── run_perf_tuning.py    # 性能调优脚本
│   ├── run_profiling.py      # 性能采集脚本
│   ├── validate_profiling_env.py # 采集环境验证
│   └ validator.py            # 模型验证脚本
├── uploads/                   # 上传文件
├── docker-compose.yml         # Docker 配置
├── docker-compose.ascend.yml # 昇腾 NPU Docker 配置
├── Dockerfile                 # Docker 镜像
├── Dockerfile.ascend          # 昇腾 NPU Docker 镜像
├── Makefile                   # 常用命令
├── requirements.txt           # Python 依赖
└── pyproject.toml             # 项目配置
```

## API接口

### 认证接口

```bash
# 注册
POST /api/v1/auth/register
{
  "username": "testuser",
  "email": "test@example.com",
  "password": "password123"
}

# 登录
POST /api/v1/auth/login
{
  "username": "test@example.com",
  "password": "password123"
}
```

### 文献检索接口

```bash
# 搜索文献
POST /api/v1/literature/search
Authorization: Bearer <token>
{
  "query": "deep learning medical imaging",
  "filters": {}
}

# 文献总结
POST /api/v1/literature/read
Authorization: Bearer <token>
{
  "content": "文献内容..."
}
```

### 文献库接口

> 所有文献库操作通过统一 `LibraryService` 处理，自动维护状态同步：
> - 添加/更新/删除文献时自动维护标签 `usage_count` 与分类 `paper_count`
> - 删除分类时该分类下文献自动改为 `uncategorized`
> - 删除标签时自动从所有文献的标签列表移除
> - 删除文献时级联清理阅读笔记与引用关系
> - 添加引用关系时自动从文献库回填标题

```bash
# 添加文献到文献库
POST /api/v1/library/papers
Authorization: Bearer <token>
{
  "paper_id": "external-paper-id",
  "title": "论文标题",
  "authors": ["作者1", "作者2"],
  "year": 2024,
  "abstract": "摘要...",
  "tags": ["深度学习"],
  "category": "医学影像"
}

# 获取文献库列表（支持 category/tag/favorite/search 过滤）
GET /api/v1/library/papers?category=深度学习&tag=重要&favorite=1&search=transformer
Authorization: Bearer <token>

# 获取单篇文献（支持数据库ID或外部paper_id）
GET /api/v1/library/papers/{paper_id}
Authorization: Bearer <token>

# 更新文献（收藏、标签等，支持双ID查找）
PUT /api/v1/library/papers/{paper_id}
Authorization: Bearer <token>
{
  "is_favorite": 1,
  "tags": ["深度学习", "医学影像"]
}

# 删除文献（支持数据库ID或外部paper_id，级联清理笔记与引用）
DELETE /api/v1/library/papers/{paper_id}
Authorization: Bearer <token>
```

### 分类与标签接口

```bash
# 创建分类
POST /api/v1/library/categories
Authorization: Bearer <token>
{ "name": "深度学习" }

# 列出分类
GET /api/v1/library/categories
Authorization: Bearer <token>

# 创建标签
POST /api/v1/library/tags
Authorization: Bearer <token>
{ "name": "重要" }

# 列出标签
GET /api/v1/library/tags
Authorization: Bearer <token>
```

### 引用网络接口

```bash
# 添加引用关系
POST /api/v1/library/citations
Authorization: Bearer <token>
{ "citing_paper_id": 1, "cited_paper_id": 2 }

# 引用图谱
POST /api/v1/library/citations/network/graph
Authorization: Bearer <token>
{ "paper_ids": [1, 2, 3] }

# 共引分析
POST /api/v1/library/citations/network/co-citation
Authorization: Bearer <token>

# 影响力分析
POST /api/v1/library/citations/network/influential
Authorization: Bearer <token>

# 研究脉络
POST /api/v1/library/citations/network/lineage
Authorization: Bearer <token>

# 前沿检测
POST /api/v1/library/citations/network/frontier
Authorization: Bearer <token>

# 聚类分析
POST /api/v1/library/citations/network/clusters
Authorization: Bearer <token>

# 引用时间线
GET /api/v1/library/citations/network/timeline/{paper_id}
Authorization: Bearer <token>
```

### 阅读笔记接口

```bash
# 创建笔记
POST /api/v1/library/notes
Authorization: Bearer <token>
{ "paper_id": 1, "content": "阅读笔记..." }

# 查看笔记
GET /api/v1/library/notes/{paper_id}
Authorization: Bearer <token>

# 更新笔记
PUT /api/v1/library/notes/{note_id}
Authorization: Bearer <token>
{ "content": "更新后的笔记..." }

# 删除笔记
DELETE /api/v1/library/notes/{note_id}
Authorization: Bearer <token>
```

### 文献库统计接口

```bash
# 获取文献库统计
GET /api/v1/library/stats
Authorization: Bearer <token>
```

### 数据分析接口

```bash
# 数据分析
POST /api/v1/data/analyze
Authorization: Bearer <token>
{
  "data": [...],
  "analysis_type": "descriptive"
}
```

### 写作接口

```bash
# 生成大纲
POST /api/v1/writing/outline
Authorization: Bearer <token>
{
  "topic": "研究主题"
}
```

### 实验设计接口

```bash
# 设计实验
POST /api/v1/experiment/design
Authorization: Bearer <token>
{
  "goal": "研究目标",
  "variables": ["变量1", "变量2"],
  "design_type": "between"
}
```

### 数据导出接口

```bash
# 导出CSV
POST /api/v1/export/csv
Authorization: Bearer <token>

# 导出BibTeX
POST /api/v1/export/bibtex
Authorization: Bearer <token>

# 导出RIS
POST /api/v1/export/ris
Authorization: Bearer <token>
```

### 计费接口

```bash
# 获取当前套餐
GET /api/v1/billing/plan
Authorization: Bearer <token>

# 获取用量统计
GET /api/v1/billing/usage
Authorization: Bearer <token>
```

## 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `OPENAI_API_KEY` | OpenAI API密钥 | - |
| `OPENAI_BASE_URL` | API端点 | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | 模型名称 | `gpt-4` |
| `DATABASE_URL` | 数据库连接 | `sqlite+aiosqlite:///./research_agent.db` |
| `REDIS_URL` | Redis连接 | `redis://localhost:6379/0` |
| `CACHE_BACKEND` | 缓存后端（`memory` / `redis`） | `memory` |
| `RATE_LIMIT_BACKEND` | 限流后端（`memory` / `redis`） | `memory` |
| `MIGRATION_ON_STARTUP` | 启动时执行 Alembic 迁移 | `true` |
| `MILVUS_HOST` | Milvus地址 | `localhost` |
| `MILVUS_PORT` | Milvus端口 | `19530` |
| `SECRET_KEY` | JWT密钥 | `your-secret-key` |
| `DEBUG` | 调试模式 | `false` |

### 套餐限制

| 套餐 | API调用/分钟 | Token/月 |
|------|-------------|----------|
| Free | 10 | 10,000 |
| Basic | 30 | 100,000 |
| Pro | 100 | 1,000,000 |
| Enterprise | 1000 | 无限制 |

## 开发指南

### 运行测试

```bash
# 运行所有测试
make test

# 运行测试并生成覆盖率
make test-cov

# 运行特定测试
pytest tests/unit/agents/test_literature.py -v
```

### 数据库迁移（Alembic）

```bash
# 生成新迁移（基于模型变更自动检测）
alembic revision --autogenerate -m "描述变更"

# 升级到最新版本
alembic upgrade head

# 查看当前版本
alembic current

# 查看迁移历史
alembic history

# 回滚一个版本
alembic downgrade -1
```

> 启动时若 `MIGRATION_ON_STARTUP=true`（默认），应用会自动执行 `alembic upgrade head`。
> 迁移使用 `render_as_batch=True`，兼容 SQLite 的 ALTER TABLE 限制。

### 数据库后端切换（SQLite ↔ PostgreSQL）

开发环境用 SQLite（零依赖），生产环境推荐 PostgreSQL（并发写入、JSONB 索引、LISTEN/NOTIFY）。两种 compose 均已配好 PG 服务，只需改 `.env`：

```bash
# 开发零依赖（默认）
DATABASE_URL=sqlite+aiosqlite:///./research_agent.db

# 生产（Docker 已含 postgres:15-alpine 服务）
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/research_agent

# 切换后首次启动需执行迁移
alembic upgrade head
```

迁移文件使用 `render_as_batch=True` + `CURRENT_TIMESTAMP`，两种数据库均兼容，无需额外适配。`asyncpg` 已在 `requirements.txt` 中声明。

### 缓存与限流后端切换

通过环境变量切换后端，无需改代码：

```bash
# 单实例：内存后端（默认，零依赖）
CACHE_BACKEND=memory
RATE_LIMIT_BACKEND=memory

# 多实例：Redis 后端（分布式共享）
CACHE_BACKEND=redis
RATE_LIMIT_BACKEND=redis
REDIS_URL=redis://localhost:6379/0
```

Redis 不可用时自动降级到内存后端，服务不中断。

### 前端开发

```bash
cd frontend

# 开发模式（热更新，代理 /api 到后端）
npm run dev

# 类型检查 + 构建
npm run build

# 预览构建产物
npm run preview
```

前端使用 React 18 + TypeScript + Vite + Tailwind CSS，集成 React Bits 动画组件库。
构建产物输出到 `frontend/dist/`，由 FastAPI 直接服务。

### 代码规范

```bash
# 代码检查
make lint

# 代码格式化
make format
```

### 常用命令

```bash
make help           # 查看所有命令
make run            # 启动开发服务器
make docker-up      # 启动Docker服务
make docker-down    # 停止Docker服务
make docker-logs    # 查看日志
make clean          # 清理临时文件
```

## 部署

### 生产环境部署

```bash
# 1. 配置环境变量
export OPENAI_API_KEY=your-key
export SECRET_KEY=your-secret-key

# 2. 构建并启动
make docker-build
make docker-up

# 3. 初始化数据库
make db-init

# 4. 健康检查
curl http://localhost:8000/health
```

### 使用部署脚本

```bash
# 启动
./scripts/deploy.sh up

# 停止
./scripts/deploy.sh down

# 重启
./scripts/deploy.sh restart

# 查看状态
./scripts/deploy.sh status

# 更新
./scripts/deploy.sh update
```

### 监控

```bash
# 运行监控脚本
./scripts/monitor.sh
```

## 故障排除

### 常见问题

1. **LLM调用失败**
   - 检查 `OPENAI_API_KEY` 是否正确
   - 检查网络连接
   - 查看 `logs/error.log`

2. **数据库连接失败**
   - 检查 PostgreSQL 是否运行
   - 检查 `DATABASE_URL` 配置

3. **Milvus连接失败**
   - 检查 Milvus 是否运行
   - 检查 `MILVUS_HOST` 和 `MILVUS_PORT`

4. **文献收藏按钮不响应**
   - 确认已登录且Token有效
   - 检查浏览器控制台网络请求
   - 确认后端 `/api/v1/library/papers` 端点正常（支持数据库ID和外部paper_id双查找）

5. **搜索结果中收藏状态不正确**
   - 搜索完成后前端会自动加载文献库ID集合
   - 检查 `/api/v1/library/papers` 接口返回的 `paper_id` 字段
   - 确认搜索结果中的 `paper.id` 与文献库中 `paper_id` 一致

6. **Redis 连接失败**
   - 检查 Redis 是否运行：`redis-cli ping` 应返回 `PONG`
   - 检查 `REDIS_URL` 配置
   - 系统会自动降级到内存后端，服务不中断（查看日志中的降级警告）

7. **数据库迁移失败**
   - 查看启动日志中的 Alembic 输出
   - 手动执行 `alembic upgrade head` 查看详细错误
   - SQLite 环境：迁移使用 `render_as_batch` 模式，避免 ALTER TABLE 限制
   - 如需跳过启动迁移：设置 `MIGRATION_ON_STARTUP=false`

8. **前端构建失败**
   - 确认 Node.js 版本 ≥ 18
   - 删除 `frontend/node_modules` 后重新 `npm install`
   - 检查 TypeScript 类型错误：`npm run build` 会先执行 `tsc -b`

9. **前端页面空白**
   - 确认已执行 `npm run build` 生成 `frontend/dist/`
   - 检查后端 `FRONTEND_DIR` 指向 `frontend/dist/`
   - 开发模式使用 `npm run dev`（端口 5173），生产模式由 FastAPI 服务 `dist/`

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！

## nature-skills（学术出版辅助技能集）

`nature-skills/skills/` 下提供 11 个针对学术出版流程的独立技能模块，可独立调用或集成到 Agent 工作流：

| 技能 | 功能 |
|---|---|
| `nature-academic-search` | 学术文献检索（含 MCP Server） |
| `nature-citation` | 引用格式化与管理 |
| `nature-data` | 数据分析与可视化 |
| `nature-figure` | 科研图表生成 |
| `nature-paper-to-patent` | 论文转专利撰写 |
| `nature-paper2ppt` | 论文转 PPT |
| `nature-polishing` | 学术语言润色 |
| `nature-reader` | 论文深度精读 |
| `nature-response` | 审稿意见回复 |
| `nature-reviewer` | 模拟审稿 |
| `nature-writing` | 学术写作辅助 |

每个技能含独立的 `SKILL.md` 定义与参考文档，`_shared/` 提供共享资源。详见 [nature-skills/README.md](file:///d:/AI_agent/nature-skills/README.md)。

## 架构亮点

### 统一 LibraryService（痛点 1 完整状态同步）

文献库操作通过 [app/services/library_service.py](file:///d:/AI_agent/app/services/library_service.py) 统一处理，6 个子服务 + 门面聚合：

| 子服务 | 职责 |
|---|---|
| `PaperService` | 文献收藏 CRUD，维护 tag/category 计数 |
| `CategoryService` | 分类 CRUD，维护 `paper_count` |
| `TagService` | 标签 CRUD，维护 `usage_count` |
| `CitationService` | 引用关系 CRUD + 8 个网络分析（统一 `_build_network`） |
| `NoteService` | 阅读笔记 CRUD |
| `LibraryStatsService` | 统计聚合 |

**状态同步矩阵**：

| 操作 | 同步动作 |
|---|---|
| `add_paper` | tag `usage_count +1`；category `paper_count +1` |
| `update_paper` | tags 变更 diff 同步；category 变更双向同步 |
| `delete_paper` | tag/category 计数回收；级联删除 notes/citations |
| `delete_category` | 该分类下 papers 改为 `uncategorized` |
| `delete_tag` | 从所有 papers 的 tags 列表移除 |
| `add_citation` | 自动从 PaperCollection 回填 title |

路由层 [app/api/v1/library.py](file:///d:/AI_agent/app/api/v1/library.py) 从 1178 行精简到 613 行，业务逻辑全部下沉。

### 双后端缓存与限流

- [app/core/cache.py](file:///d:/AI_agent/app/core/cache.py)：`CacheBackend` ABC + `MemoryCache` + `RedisCache` + 工厂
- [app/core/rate_limit.py](file:///d:/AI_agent/app/core/rate_limit.py)：`RateLimiterBackend` ABC + Memory + Redis（ZSET + Lua 滑动窗口）
- 通过 `CACHE_BACKEND` / `RATE_LIMIT_BACKEND` 环境变量切换，Redis 不可用时自动降级

### Alembic 数据库迁移

- [migrations/env.py](file:///d:/AI_agent/migrations/env.py)：async env + `render_as_batch=True`（SQLite 兼容）
- [migrations/versions/6ab33371ef5b_initial_baseline.py](file:///d:/AI_agent/migrations/versions/6ab33371ef5b_initial_baseline.py)：初始 baseline（8 表 + 10 索引）
- 启动时自动执行 `alembic upgrade head`（可用 `MIGRATION_ON_STARTUP=false` 关闭）

### Agent 间结果传递

[app/agents/coordinator/agent.py](file:///d:/AI_agent/app/agents/coordinator/agent.py) 的 `_inject_upstream` 方法把上游 Agent 的输出注入下游 Agent 的输入，支持多 Agent 协作链路（如文献检索 → 引用网络分析 → 论文写作）。

### React Bits 动画前端

[frontend/src/](file:///d:/AI_agent/frontend/src/) 使用 React 18 + TypeScript + Vite + Tailwind，集成 5 个 React Bits 组件：

- **Aurora** — WebGL 极光背景（铜色色标，呼应"天文台"主题）
- **DecryptedText** — 主标题解密动画
- **BlurText** — 副标题逐词模糊揭示
- **Dock** — macOS 风格放大导航栏
- **StarBorder** — CTA 按钮星光流动边框

完整支持 `prefers-reduced-motion`，Aurora 在 reduced-motion 下不启动 WebGL。

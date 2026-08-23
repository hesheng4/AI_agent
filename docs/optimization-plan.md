# 研究Agent平台 — 可执行优化方案

> 状态：✅ 可执行方案（基于 `docs/competitive-analysis.md` 的 54 项优化清单，逐项给出实施路径）
> 目的：把调研结论转化为**可直接落地的实施计划**——每项标注 来源项目 / 本地现状 / 实施方案 / 涉及文件 / 验收标准 / 依赖 / 优先级。
> 更新：2026-08-14

---

## 一、方案总览

### 1.1 执行基线

- **已完成 ✅（P0-1）**：B2 引用验证外部实查（`app/services/citation_verification.py` + CrossRef/OpenAlex 三级策略 + 幻觉引用打标 + 24h 缓存 + 15 个单测）。pytest 24 passed，ruff 全绿。
- **本轮目标（P0 剩余 + P1 首批）**：
  - B3 审稿输出结构化「优缺点+改进建议」并直接串联审稿回复（ChatPaper 借鉴）
  - H1 审稿→修改→再审稿自动迭代闭环（AI-Scientist v1 借鉴，审稿分数为停止条件）
- **后续批次**：按第四节路线图推进 P1 → P2。

### 1.2 执行原则

1. **不重复造轮子**：凡第二节「本地能力核实」已具备的（WebSocket 流式、LLM 重试、多源检索、Milvus RAG、引用网络等）不做，仅做增强项。
2. **向后兼容**：所有 API 新增字段均可选，旧客户端不受影响。
3. **测试先行**：每个优化项落地必须配套单测（httpx.MockTransport 等，不发真实网络请求），pytest + ruff 双绿为验收底线。
4. **免费 API 优先**：外部数据源一律用无 key 免费接口（CrossRef / OpenAlex），Redis 限流承接速率限制。

---

## 二、逐参考资料分析（16 个项目 → 优化项映射）

> 每个项目：**核心参考价值** → **映射到本平台的优化项**（ID 见第三节）。

### 2.1 assafelovic/gpt-researcher（通用深度研究 Agent）
- **参考价值**：Plan-and-Solve 管线、上下文压缩、混合检索、**对抗式事实审查**、报告可定制、MCP 双向接入、自有文档研究。
- **映射**：A1（数据源扩展+向量重排序）、A5（上传文档 RAG）、B1（对抗式事实审查）、C1（报告定制）、E1（模型网关）、E4（MCP）。
- **优先级**：P1（A1/A5/B1/C1/E1）→ P2（E4）。

### 2.2 Future-House/paper-qa（引用级 RAG）
- **参考价值**：**句子级证据 grounding**、Agentic 多步证据收集、轻量向量存储、Settings 声明式配置、公开基准评估。
- **映射**：A2（证据级引用）、A3（Agentic RAG）、A6（token 粒度调节）、E3（声明式配置）、G2（Numpy store 兜底）、B4（基准质量门禁）。
- **优先级**：P1（A2）→ P2（A3/A6/B4/E3/G2）。

### 2.3 kaixindelele/ChatPaper（arXiv 流水线）
- **参考价值**：**审稿输出优缺点+改进建议**、**审稿→审稿回复闭环**、每日新论文批处理、翻译+润色一体化、本地归档、tenacity 重试。
- **映射**：**B3（本轮落地）**、A4（arXiv 批处理）、C3（本地归档）、C2（翻译润色，已具备）、E2（重试，已具备）。
- **优先级**：P0（B3）→ P2（A4/C3）。

### 2.4 SakanaAI/AI-Scientist 系列（自动科研闭环）
- **参考价值**：**审稿→修改→再审稿迭代闭环（分数停止条件）**、自动实验沙箱、自动选题+novelty 过滤、树搜索多方向探索、模板库、轨迹审计、Agent 评测套件。
- **映射**：**H1（本轮落地）**、H2（实验沙箱）、H3（自动选题）、H4（树搜索）、H5（模板库）、H6（轨迹审计）、H7（评测套件）。
- **优先级**：P0.5（H1）→ P2（H2–H7）。

### 2.5 MingfengHong/paperseek（迭代检索 Agent）
- **参考价值**：自然语言检索→**迭代查询改写**→候选扩展→排序→**可复核导出**。
- **映射**：A7（迭代查询闭环）、A8（候选涟漪扩展）、A9（可复核导出）。
- **优先级**：P1（A7）→ P1（A8）→ P2（A9）。

### 2.6 akiasprin/ripple-reader 与 HolobiomicsLab/Perspicacite-AI（发现+精读）
- **参考价值**：**来源级 SSE 流式事件**（逐条推送引用来源）、Agent 过程透明化、agentic 流程回归测试、涟漪式扩散发现（推测）。
- **映射**：A10（来源级流式事件）、E5（Agent 流程回归测试）、A8（涟漪扩展，与 citation 联动）。
- **优先级**：P1（A10）→ P2（E5）。

### 2.7 moonlarry/awesome-llm-paper-wiki（文件化文献库）
- **参考价值**：**Markdown 文件即知识库**（可移植/版本化/离线）、**综述自动化管线**（库→综述）、digest 沉淀、自然语言查库。
- **映射**：A11（Markdown 文献库导出）、A12（综述自动化管线）、A13（自然语言查库）、C4（digest 沉淀）。
- **优先级**：P1（A12）→ P2（A11/A13/C4）。

### 2.8 argahv/sisyphus-academica（质检管道）
- **参考价值**：**引用验证独立质检**（已落地为 B2）、**新颖性/贡献点检测生成**、**对抗性红队审稿**（攻击假设/弱证据/过度声称）。
- **映射**：B2（✅ 已落地）、B5（红队审稿模式）、B7（新颖性检测）。
- **优先级**：P1（B5）→ P2（B7）。

### 2.9 Intersect-Collaborations-LLC/research-workflow-assistant（MCP+审计）
- **参考价值**：**审计轨迹**（证据→动作→输出链）、**ICMJE/期刊规范约束**、系统综述流程化、Zotero 对接、六数据源 MCP 封装。
- **映射**：E6（审计轨迹）、C7（期刊合规检查）、A14（系统综述工作流）、A17（Zotero 对接）、E4（MCP）。
- **优先级**：P1（E6/C7）→ P2（A14/A17/E4）。

### 2.10 ShaishavMaisuria/research-paper-lifecycle-skills（生命周期技能）
- **参考价值**：**Rebuttal 全流程方法学**（逐条映射→强弱分类→证据引用→语气控制）、Camera-ready 定稿、汇报幻灯片、生命周期状态机。
- **映射**：B6（Rebuttal 方法学）、C5（Camera-ready）、C6（汇报版 PPT）、E8（技能编排）。
- **优先级**：P1（B6）→ P2（C5/C6/E8）。

### 2.11 AlphaLab-USTC/ResearchClaw（工作流展示）
- **参考价值**：**研究者画像**（研究方向/偏好注入全部 Agent）、看板式阅读清单、系统综述工作流、showcase 示例库。
- **映射**：E7（研究者画像）、A16（看板阅读清单）、A14（系统综述）。
- **优先级**：P1（E7）→ P2（A16/A14）。

### 2.12 wentorai/research-plugins（技能目录）
- **参考价值**：技能三级目录组织、**统计建模策略前置指南**、**AI 写作人性化改写**、Zotero/MCP 生态对接。
- **映射**：E8（技能目录页）、D3（建模策略前置）、C8（人性化改写）、A17（Zotero）。
- **优先级**：P1（C8）→ P2（D3/E8/A17）。

### 2.13 joshzyj/open-scholar-skill（社科研技能）
- **参考价值**：**统计方法广度**（贝叶斯 brms/LCA/SEM/序列/分位数）、**分析→Results 撰写一体化**、定时文献监控幂等、研究设计前置。
- **映射**：D1（统计方法扩展）、D2（分析→Results 一体化）、A15（文献周报）、D4（设计前置校验）。
- **优先级**：P1（D1/D2）→ P1（A15）→ P2（D4）。

### 2.14 JosephElvisMaman1/ResearchPilot-Skills（质检三件套）
- **参考价值**：**引用验证独立技能**（已落地为 B2）、证据检索、**免费元数据源**（OpenAlex/CrossRef 无 key）。
- **映射**：B2（✅ 已落地）、B1（证据链支撑）、A18（免费源接入）。
- **优先级**：P1（A18）→ P1（B1）。

### 2.15 AlphaLab-USTC 生态 AutoResearchClaw（衍生）
- **参考价值**：沙箱实验 + NaN/Inf 检测 + **LLM 自愈代码 + HITL**。
- **映射**：E9（数据执行安全）。
- **优先级**：P2。

### 2.16 cang-zhu/AcAgent
- **结论**：信息不足，无可借鉴点，**不纳入方案**。

---

## 三、可执行优化项清单

> 字段说明：**现状**（代码级核实）→ **方案** → **涉及文件** → **验收标准** → **依赖** → **优先级**。
> 已落地项标注 ✅，可跳过。

### A. 文献检索与阅读（literature / reader）

#### A1 扩展学术数据源 + 向量重排序混合检索 — P1
- **现状**：已有 T1/T2/T3 分级路由（semantic_scholar/arxiv/pubmed/crossref/scopus/science_direct），无 OpenAlex/Europe PMC，无向量重排序。
- **方案**：① literature `MCP_TOOLS` 增 OpenAlex（`api.openalex.org/works`）、Europe PMC（`ebi.ac.uk/europepmc/webservices/rest`）条目；② 检索结果用 `embedding_client` 对 query 与候选摘要做相似度重排（复用 `literature/tools.py` 的向量链路）。
- **涉及文件**：`app/agents/literature/agent.py`、`app/agents/literature/tools.py`、`app/config.py`
- **验收标准**：单测覆盖新源路由与重排函数；不破坏现有 T1 默认路由。
- **依赖**：—（独立）。

#### A2 句子级/证据级引用 grounding — P1
- **现状**：reader 输出章节/段落级中英对照，无逐句溯源。
- **方案**：reader `_build_output` 增加可选 `evidence_refs` 段——LLM 对每段结论标注支撑句子来源（段落号+句号），结构化返回。
- **涉及文件**：`app/agents/reader/agent.py`、`app/api/v1/reader.py`、`app/agents/reader/prompts.py`
- **验收标准**：输出含 `evidence_refs`（段落号→句子），单测断言字段结构；旧字段兼容。
- **依赖**：—（独立，成本中等）。

#### A3 Agentic 多步证据收集闭环 — P2
- **现状**：单次检索→总结。
- **方案**：literature 新增 `deep_read` 任务：检索→收集证据→引用→作答的多轮循环（信号量限并发）。
- **涉及文件**：`app/agents/literature/agent.py`、`app/services/citation_verification.py`（复用证据收集）
- **验收标准**：多轮检索有最大轮数上限与 token 预算护栏；单测 mock 检索服务。
- **依赖**：A1（多源）、B2（引用验证，已落地）。

#### A4 每日 arXiv 新论文批处理 — P2
- **现状**：无定时任务。
- **方案**：`scripts/arxiv_digest.py` + APScheduler/Celery 定时任务，按关键词拉取 arXiv API 新论文并生成 digest（幂等去重：论文 ID 集合 + Redis 缓存）。
- **涉及文件**：`scripts/arxiv_digest.py`（新增）、`app/main.py`（lifespan 挂载）、`app/config.py`
- **验收标准**：dry-run 脚本可离线 mock 验证；去重逻辑单测。
- **依赖**：—（独立）。

#### A5 上传 PDF 研究（本地语料 RAG）— P1
- **现状**：有 uploads/ 目录 + Milvus + data.upload，无通用"上传 PDF → 向量化 → 问答"链路。
- **方案**：新增 `app/services/pdf_rag.py`：PDF 文本提取（pypdf）→ 分段 → embedding → Milvus 入库 → 检索问答；`literature` 增加 `corpus_qa` 任务。
- **涉及文件**：`app/services/pdf_rag.py`（新增）、`app/agents/literature/agent.py`、`app/api/v1/literature.py`、`requirements.txt`
- **验收标准**：单测用内存 Milvus mock 验证入库/检索；PDF 解析失败优雅降级。
- **依赖**：—（独立，成本中）。

#### A6 token 成本预算：可调检索粒度 — P2
- **现状**：有 `_apply_token_budget`，无检索粒度调节。
- **方案**：literature 检索参数增加 `source_limit`/`passage_limit` 透传。
- **涉及文件**：`app/agents/base.py`、`app/agents/literature/agent.py`
- **验收标准**：参数生效并有默认值；单测覆盖。
- **依赖**：—（独立，小）。

#### A7 迭代查询/查询改写闭环 — P1
- **现状**：literature 单次检索 + AI 总结。
- **方案**：`_handle_search` 增加 `iterative_search` 模式：首轮结果 → LLM 改写查询 → 多轮收敛（最多 3 轮）→ 合并去重排序。
- **涉及文件**：`app/agents/literature/agent.py`、`app/agents/literature/prompts.py`
- **验收标准**：轮次上限、去重、合并逻辑单测；默认关闭不影响现有行为。
- **依赖**：—（独立）。

#### A8 候选论文扩展（涟漪式）— P1
- **现状**：citation 有共引分析，缺"种子论文长出文献子图"一体化流程。
- **方案**：`literature` 新增 `expand` 任务：种子论文 → 沿引用/共被引（Semantic Scholar citations API）→ 按相似度筛选扩展候选。
- **涉及文件**：`app/agents/literature/citation.py`（复用 get_citations/get_references）、`app/agents/literature/agent.py`
- **验收标准**：扩展深度/宽度参数有上限；单测 mock 引用 API。
- **依赖**：—（独立）。

#### A9 可复核导出（带命中依据）— P2
- **现状**：文献列表导出无命中依据。
- **方案**：导出格式增加 `matched_on`（命中字段/来源）字段，RIS/CSV 导出透传。
- **涉及文件**：`app/utils/export.py`、`app/agents/literature/agent.py`
- **验收标准**：导出样例含命中依据列；单测覆盖。
- **依赖**：A7（多轮结果才有依据）。

#### A10 来源级流式事件 — P1
- **现状**：有任务进度 WebSocket（E4 + useTaskStream），无逐来源事件。
- **方案**：E4 事件总线新增 `source_event` 事件类型；literature 总结过程中逐条 `emit("source", {paper_id,title})`；前端 useTaskStream 渲染来源列表。
- **涉及文件**：`app/core/events.py`、`app/agents/literature/agent.py`、`frontend/src/hooks/useTaskStream.ts`、`frontend/src/pages/Literature.tsx`
- **验收标准**：后端事件类型单测；前端收到 source 事件渲染。
- **依赖**：—（后端独立，前端需 rebuild）。

#### A11 Markdown 文件化文献库导出 — P2
- **现状**：library 为服务端数据库。
- **方案**：export 增加 `markdown_library` 格式：每篇文献一个 `.md`（元数据 front-matter + 摘要 + 笔记），zip 打包下载。
- **涉及文件**：`app/utils/export.py`、`app/api/v1/export.py`
- **验收标准**：生成文件结构正确；单测覆盖。
- **依赖**：—（独立）。

#### A12 综述自动化管线（文献库→结构化综述）— P1
- **现状**：library/citation/literature 各自独立，无"库→综述"收尾。
- **方案**：`literature` 新增 `review_synthesis` 任务：选定文献集合 → 主题聚类（citation_network 聚类复用）→ 按主题生成章节 → 附引用。
- **涉及文件**：`app/agents/literature/agent.py`、`app/services/citation_network.py`、`app/agents/writing/agent.py`（复用写作模板）
- **验收标准**：综述含章节+引用；单测验证输入输出契约。
- **依赖**：A8（扩展完备性）可选。

#### A13 自然语言查库（wiki-query）— P2
- **现状**：library 查询偏结构化过滤。
- **方案**：library API 增加 `query` 语义参数：embedding 检索文献库（复用 Milvus）→ 返回相关文献。
- **涉及文件**：`app/api/v1/library_domain/*`、`app/services/library_service.py`、`app/core/vector_store.py`
- **验收标准**：语义查询单测（mock 向量检索）。
- **依赖**：—（独立）。

#### A14 系统综述工作流（PRISMA 式）— P2
- **现状**：无。
- **方案**：`literature` 新增 `systematic_review` 任务状态机：检索→去重筛选（PRISMA 标准）→ 质量评估 → 证据表。
- **涉及文件**：`app/agents/literature/agent.py`、`app/agents/literature/prompts.py`、`app/services/review_pipeline.py`（新增）
- **验收标准**：状态机阶段流转与筛选记录单测。
- **依赖**：A7/A8。

#### A15 文献定时监控/周报（幂等去重）— P1
- **现状**：无定时任务，被动检索。
- **方案**：与 A4 同设施：`scripts/literature_monitor.py` 定时跑 A7 检索 + digest，Redis 存 `last_seen_paper_ids` 幂等去重。
- **涉及文件**：`scripts/literature_monitor.py`（新增）、`app/core/cache.py`、`app/config.py`
- **验收标准**：幂等去重单测（同一论文两次运行只报一次）。
- **依赖**：A4 设施。

#### A16 看板式阅读清单 — P2
- **现状**：无。
- **方案**：library 增加阅读状态字段（to-read/reading/read），前端 Library 页加看板视图。
- **涉及文件**：`app/models/library.py`、`app/api/v1/library_domain/*`、`frontend/src/pages/Library.tsx`
- **验收标准**：状态迁移 API 单测；前端看板渲染。
- **依赖**：—（前端工作量较大）。

#### A17 Zotero 对接 — P2
- **现状**：无。
- **方案**：`literature` 新增 `zotero_import/export` 任务：通过 Zotero Web API（用户 token）同步条目 ↔ library。
- **涉及文件**：`app/services/zotero.py`（新增）、`app/agents/literature/agent.py`、`app/config.py`
- **验收标准**：导入/导出映射单测（mock API）。
- **依赖**：—（独立）。

#### A18 免费元数据源接入（OpenAlex/CrossRef 后备）— P1
- **现状**：已有 crossref，缺 OpenAlex。
- **方案**：复用 `citation_verification.py` 的检索函数，作为 literature 检索后备源（`requires_key: False` 加入 MCP_TOOLS）。
- **涉及文件**：`app/services/citation_verification.py`、`app/agents/literature/agent.py`
- **验收标准**：OpenAlex 检索单测（MockTransport）。
- **依赖**：B2（已落地，直接复用）。

### B. 引用与可信度（citation / reviewer / writing）

#### B1 对抗式事实审查 Agent（外部查证后复核）— P1
- **现状**：reviewer 仅在"给定内容内"评估证据，无外部查证步骤。
- **方案**：reviewer `assess` 增加可选 `external_verify: bool`：审稿前对稿件中的关键引用/论断调用 `citation_verification` 外部实查，把核查结果注入事实基础 prompt，输出「外部核查」小节。
- **涉及文件**：`app/agents/reviewer/agent.py`、`app/agents/reviewer/prompts.py`、`app/api/v1/reviewer.py`
- **验收标准**：开启外部核查时输出含核查摘要；单测 mock 服务；默认关闭保持旧行为。
- **依赖**：B2（已落地）。

#### B2 引用验证外部实查 — ✅ 已落地（P0-1）
- **落地内容**：`app/services/citation_verification.py`（DOI 提取/标题归一化/CrossRef→OpenAlex 三级策略/信号量并发/24h 缓存/降级 uncertain）；`citation.verify_citations` 注入外部核查结果；API 新增 `per_reference/verified_count/suspicious_count`；15 个单测。
- **跳过**：直接作为 B1/A3/A18 的依赖复用。

#### B3 审稿输出结构化「优缺点+改进建议」并串联审稿回复 — ✅ 已落地（本轮）
- **落地内容**：reviewer.assess 增加 Step 3 结构化提取（`STRUCTURED_REVIEW_EXTRACTION_PROMPT` + `_parse_structured` 容错 JSON 解析），输出 `strengths` / `improvement_suggestions`（含 issue/location/suggestion/severity/category）；response.draft 支持直接接收 `review_result` 自动派生审稿意见与决策类型（`_derive_comments`）；API：`POST /reviewer/assess` 响应新增可选字段、`POST /response/draft` 请求新增 `review_result`；16 个单测（`test_reviewer_response_b3.py`）。
- **跳过**：作为 H1（审稿迭代闭环）的前置依赖已落地。

#### B4 公开基准质量门禁（RAG-QA Arena 类）— P2
- **现状**：无评测接入。
- **方案**：`tests/benchmark/` 建小样本评测集，对 literature/reader 检索问答质量打分，CI 门禁。
- **涉及文件**：`tests/benchmark/`（新增）、`pyproject.toml`
- **验收标准**：评测脚本可离线跑通并输出分数。
- **依赖**：A2（证据级输出后才有评测对象）。

#### B5 对抗性/红队审稿模式 — P1
- **现状**：reviewer 为打分型审稿，无红队模式。
- **方案**：reviewer 新增 `redteam` 任务：专攻假设漏洞/弱证据/过度声称，输出「拒稿风险清单」（每条：风险点→证据→严重度→缓解建议）。
- **涉及文件**：`app/agents/reviewer/agent.py`、`app/agents/reviewer/prompts.py`、`app/api/v1/reviewer.py`
- **验收标准**：redteam 输出含风险清单结构；单测覆盖。
- **依赖**：—（独立）。

#### B6 Rebuttal 全流程方法学 — P1
- **现状**：response 有 draft/audit/revise 与 10 步工作流骨架，缺"逐条意见→强弱分类→证据引用→语气控制"的显式方法学链路。
- **方案**：response `draft` 增强：意见分类细化（major/minor/clarification + 强弱评分）、每条回复要求挂证据引用、输出前跑 TONE_AUDIT 语气检查。
- **涉及文件**：`app/agents/response/agent.py`、`app/agents/response/prompts.py`
- **验收标准**：draft 输出含逐条映射与强弱分类；单测断言结构。
- **依赖**：B3（串联后才有完整闭环）。

#### B7 新颖性/贡献点检测与生成 — P2
- **现状**：无。
- **方案**：writing 新增 `novelty_check` 任务：提取稿件贡献点 → 对照相关工作（citation 网络）判断重复度 → 输出新颖性评估与卖点改写建议。
- **涉及文件**：`app/agents/writing/agent.py`、`app/agents/writing/prompts.py`、`app/services/citation_network.py`
- **验收标准**：输出贡献点清单+重复度评级；单测覆盖。
- **依赖**：A8（相关工作集合）。

### C. 写作与投稿闭环（writing / submission_package / paper2ppt）

#### C1 报告结构高度可定制（大纲/语气/字数/期刊预设）— P1
- **现状**：writing 有论文类型模板，缺语气/字数/领域级预设。
- **方案**：writing API 增加 `outline`/`tone`/`target_words`/`journal` 参数透传 prompt。
- **涉及文件**：`app/agents/writing/agent.py`、`app/agents/writing/prompts.py`、`app/api/v1/writing.py`
- **验收标准**：参数注入 prompt 并生效；单测断言。
- **依赖**：—（独立）。

#### C2 翻译+润色一体化 — ✅ 已具备（polishing.translate + reader 中英对照），跳过。

#### C3 输出本地可版本化归档 — P2
- **现状**：有导出，缺笔记库落盘链路。
- **方案**：export 增加"归档包"格式：writing 结果 + digest 笔记 + 引用文件打包 zip。
- **涉及文件**：`app/utils/export.py`
- **验收标准**：归档包结构单测。
- **依赖**：C4（digest 沉淀）。

#### C4 digest 式日常沉淀 — P2
- **现状**：无。
- **方案**：literature/reader 结果增加"存为笔记"动作：生成 Markdown 笔记（摘要+要点+标签）写入 library 笔记表。
- **涉及文件**：`app/services/library_service.py`、`app/agents/reader/agent.py`
- **验收标准**：笔记生成与入库单测。
- **依赖**：—（独立）。

#### C5 Camera-ready 定稿 — P2
- **现状**：submission_package 缺接收后阶段。
- **方案**：submission_package 新增 `camera_ready` 任务：版面/版权/参考文献校对清单。
- **涉及文件**：`app/agents/submission_package/agent.py`
- **验收标准**：校对清单输出单测。
- **依赖**：—（独立）。

#### C6 汇报版幻灯片生成 — P2
- **现状**：paper2ppt 偏论文转 PPT。
- **方案**：paper2ppt 增加 `presentation` 模式：按"听众=组会/答辩"组织叙事。
- **涉及文件**：`app/agents/paper2ppt/agent.py`
- **验收标准**：模式切换单测。
- **依赖**：—（独立）。

#### C7 ICMJE/期刊规范约束 — P1
- **现状**：无合规检查。
- **方案**：submission_package 打包前按期刊模板跑合规清单（参考文献格式/声明/伦理），输出检查报告。
- **涉及文件**：`app/agents/submission_package/agent.py`、`app/config.py`
- **验收标准**：合规清单单测。
- **依赖**：—（独立）。

#### C8 AI 写作人性化改写（AI 痕迹检测）— P1
- **现状**：polishing 偏语言润色，无 AI 痕迹检测。
- **方案**：polishing 新增 `deai` 任务：检测 AI 高频句式/用词（模板清单+LLM 复核）→ 改写为自然学术语体。
- **涉及文件**：`app/agents/polishing/agent.py`、`app/agents/polishing/prompts.py`、`app/api/v1/polishing.py`
- **验收标准**：检测清单单测 + 改写调用单测。
- **依赖**：—（独立）。

### D. 数据分析（data / stats）

#### D1 统计方法扩展（贝叶斯/潜变量等）— P1
- **现状**：data/tools.py 有回归/方差/非参数/生存/卡方，无贝叶斯/潜变量/序列分析。
- **方案**：data/tools.py 增加 `bayesian_regression`（numpyro/pymc 可选依赖，缺失时提示）、`latent_class`（LCA，sklearn 混合模型近似）；stats 审计 Agent 支持新方法结果解读。
- **涉及文件**：`app/agents/data/tools.py`、`app/agents/stats/`、`requirements.txt`
- **验收标准**：新方法有基础单测（纯 numpy 实现或 mock 依赖）。
- **依赖**：—（独立，成本中）。

#### D2 分析与结果撰写一体化 — P1
- **现状**：data 与 writing 独立。
- **方案**：data.analyze 结果增加 `results_section`：LLM 把统计输出转成 Results 章节草稿（表格+显著性表述），供 writing 直接接用。
- **涉及文件**：`app/agents/data/agent.py`、`app/agents/data/prompts.py`
- **验收标准**：results_section 生成单测（mock LLM）。
- **依赖**：—（独立）。

#### D3 统计建模策略前置指南 — P2
- **现状**：无。
- **方案**：stats 新增 `model_recommend` 任务：按数据形态（因变量类型/设计/样本量）推荐模型并给前提假设。
- **涉及文件**：`app/agents/stats/agent.py`
- **验收标准**：推荐规则单测。
- **依赖**：—（独立）。

#### D4 研究设计/因果推断前置校验 — P2
- **现状**：experiment 有设计推荐，缺因果推断校验。
- **方案**：experiment 增加 `design_audit`：对设计做因果识别策略校验（混杂/选择偏倚检查）。
- **涉及文件**：`app/agents/experiment/agent.py`
- **验收标准**：校验清单单测。
- **依赖**：—（独立）。

### E. 工程架构

#### E1 统一模型网关抽象（类 LiteLLM）— P1
- **现状**：llm.py 有 remote/ascend 双后端。
- **方案**：抽象 `ModelRouter`：注册多 provider（openai 兼容/ascend/ollama），按模型名路由；保留现有 API 签名。
- **涉及文件**：`app/utils/llm.py`、`app/config.py`
- **验收标准**：路由逻辑单测；现有调用不受影响。
- **依赖**：—（独立，重构需谨慎）。

#### E2 LLM 调用限流重试工程化 — ✅ 已具备（llm.py MAX_RETRIES+退避），跳过。

#### E3 Settings 声明式配置 — P2
- **现状**：有 config，缺按会话/任务参数覆盖。
- **方案**：agent 调用增加 `runtime_params` 透传覆盖。
- **涉及文件**：`app/agents/base.py`、`app/config.py`
- **验收标准**：覆盖优先级单测。
- **依赖**：—（独立）。

#### E4 MCP 双向接入 — P2
- **现状**：MCP_TOOLS 仅命名惯例，无真实 MCP 协议。
- **方案**：用 `mcp` python 包把 citation_verification/literature 暴露为 MCP server（`scripts/mcp_server.py`）。
- **涉及文件**：`scripts/mcp_server.py`（新增）、`requirements.txt`
- **验收标准**：MCP server 可启动并响应 list_tools/call_tool（本地 smoke test）。
- **依赖**：—（独立，成本中）。

#### E5 Agent 流程回归测试 — P2
- **现状**：单测按 Agent 分文件，缺多步编排回归。
- **方案**：`tests/regression/` 增加多 Agent 串联（reviewer→response→audit）集成测试。
- **涉及文件**：`tests/regression/test_workflow_chain.py`（新增）
- **验收标准**：链路测试全绿。
- **依赖**：B3（链路落地后）。

#### E6 审计轨迹/可追溯性 — P1
- **现状**：无"证据→动作→输出"链。
- **方案**：Agent 执行结果统一附加 `trace`（输入摘要→调用记录→输出变更），API 返回可选 `trace` 字段。
- **涉及文件**：`app/agents/base.py`、`app/api/v1/`（各响应模型）、`app/core/events.py`
- **验收标准**：trace 生成单测；旧字段兼容。
- **依赖**：—（独立，横切改动面大，排后）。

#### E7 研究者画像机制 — P1
- **现状**：无用户画像注入。
- **方案**：user 模型增加 `research_profile` 字段；BaseAgent 调用时注入画像 prompt 片段。
- **涉及文件**：`app/models/user.py`、`app/agents/base.py`、`app/api/v1/platform/auth.py`、`migrations/versions/`（新迁移）
- **验收标准**：画像存取 API 单测；注入逻辑单测。
- **依赖**：—（独立）。

#### E8 技能目录组织 + Agent 目录页 — P2
- **现状**：Agent 平铺列表。
- **方案**：manifest_router 聚合生成技能目录 JSON，前端新增目录页。
- **涉及文件**：`app/agents/manifest_router.py`、`frontend/src/pages/`（新增）
- **验收标准**：目录 JSON 生成单测。
- **依赖**：—（独立）。

#### E9 实验沙箱 + 自愈代码 — P2
- **现状**：无。
- **方案**：data 执行环境加可选沙箱（subprocess+资源限制）+ NaN/Inf 检测与 LLM 自愈重跑。
- **涉及文件**：`app/agents/data/tools.py`、`app/core/sandbox.py`（新增）
- **验收标准**：沙箱限制与自愈单测。
- **依赖**：—（独立，成本高）。

### F. 前端体验

#### F1 WebSocket 流式研究进度 — ✅ 已具备（E4 + useTaskStream），跳过。

### G. 昇腾 NPU 差异化

#### G1 本地模型后端对接（Ollama/自托管兼容层）— P1
- **现状**：有 ascend 后端，缺通用 OpenAI 兼容本地服务注册。
- **方案**：llm.py 增加 `local_openai` provider（任意 OpenAI 兼容 base_url），配置化注册。
- **涉及文件**：`app/utils/llm.py`、`app/config.py`
- **验收标准**：provider 切换单测。
- **依赖**：E1（模型网关统一后更顺）。

#### G2 轻量向量存储兜底（Numpy dense store）— P2
- **现状**：仅 Milvus。
- **方案**：vector_store 抽象增加内存/文件后端（numpy），Milvus 不可用时降级。
- **涉及文件**：`app/core/vector_store.py`
- **验收标准**：降级路径单测。
- **依赖**：—（独立）。

### H. 自动化科研闭环（AI-Scientist 系列）

#### H1 审稿→修改→再审稿自动迭代闭环 — ✅ 已落地（本轮）
- **落地内容**：reviewer 新增 `score` 任务（`REVIEW_SCORE_PROMPT` + `_parse_score` 容错解析，5 维度 0-10 分）；writing 新增 `revise` 任务（`REVISE_PROMPT`，输出修订稿 + change_log + skipped，解析失败退回原文）；新增 `app/services/review_loop.py`（停止条件双保险：分数阈值/最大轮数，评分不可用/无意见/修订无变化时提前收敛防死循环）；API：`POST /review-loop/run`；17 个单测（`test_review_loop.py`，含 FakeReviewer/FakeWriting 模拟全链路）。
- **跳过**：依赖 B3 的结构化审稿输出。

#### H2 自动实验代码执行沙箱 — P2（分水岭）
- **现状**：experiment 仅出方案。
- **方案**：experiment 增加 `run_sandbox`：生成可执行脚本 → 沙箱运行 → 结果回流。与 E9 复用沙箱。
- **涉及文件**：`app/agents/experiment/agent.py`、`app/core/sandbox.py`
- **验收标准**：沙箱运行真实小脚本通过。
- **依赖**：E9（沙箱设施）。

#### H3 自动选题/假设生成 + novelty 过滤 — P2
- **现状**：无。
- **方案**：coordinator 增加 `research_ideas` 任务：批量生成候选研究问题 → novelty 过滤（对照 B7）。
- **涉及文件**：`app/agents/coordinator/agent.py`
- **验收标准**：生成+过滤单测。
- **依赖**：B7（新颖性检测）。

#### H4 树搜索式多方向探索层 — P2
- **现状**：coordinator 为响应式路由。
- **方案**：coordinator 增加 `explore` 模式：生成多分支 → 评分 → 剪枝 → 深化（状态机）。
- **涉及文件**：`app/agents/coordinator/agent.py`、`app/agents/coordinator/planner.py`
- **验收标准**：分支评分/剪枝单测。
- **依赖**：H3。

#### H5 可复用研究模板库 — P2
- **现状**：无。
- **方案**：`app/templates/` 存研究基线+论文模板，writing/experiment 引用。
- **涉及文件**：`app/templates/`（新增）
- **验收标准**：模板加载单测。
- **依赖**：—（独立）。

#### H6 研究轨迹审计留痕 — P2
- **现状**：无。
- **方案**：与 E6 复用：任务执行轨迹落盘/入库可查。
- **涉及文件**：同 E6。
- **验收标准**：同 E6。
- **依赖**：E6。

#### H7 平台自身 Agent 评测套件 — P2
- **现状**：无。
- **方案**：`tests/benchmark/agent_evals/` 建各 Agent 小评测集与打分脚本。
- **涉及文件**：`tests/benchmark/`（新增）
- **验收标准**：评测脚本可跑。
- **依赖**：—（独立）。

---

## 四、实施批次路线图

> 批次按**依赖拓扑 + 性价比**排序：先做解锁后续项的基础能力，再做独立高价值项。
> 每批完成后：`pytest` + `ruff` 双绿 + 更新 `competitive-analysis.md` 落地状态。

### 批次 0 — 已落地 ✅
- **B2 引用验证外部实查**（P0-1）：服务/Agent/API/配置/15 单测完成，pytest 24 passed。
- 状态：作为 B1/A3/A18 的基础依赖复用。

### 批次 1 — ✅ 已完成（P0，审稿可信度闭环）
1. **B3** 审稿结构化「优缺点+改进建议」+ 串联审稿回复 — 已落地
2. **H1** 审稿→修改→再审稿迭代闭环（依赖 B3）— 已落地
- 交付确认：reviewer 结构化输出（strengths/improvement_suggestions）→ response 一键回复（review_result 派生意见）→ review_loop 自动迭代（分数阈值/最大轮数停止，5 种收敛路径防死循环）。
- 验证：`tests/unit` 全量 308 passed + ruff 全绿（2026-08-14）。

### 批次 2 — P1 独立高价值（按模块并行，每个 1-2 天）
- **文献**：A1（数据源扩展+重排）、A2（证据级 grounding）、A7（迭代查询）、A10（来源级流式事件）、A12（综述管线）、A15（文献周报）、A18（OpenAlex 后备）
- **可信度**：B1（对抗式事实审查，依赖 B2）、B5（红队审稿）、B6（Rebuttal 方法学，依赖 B3）
- **写作**：C1（报告定制）、C7（期刊合规）、C8（人性化改写）
- **统计**：D1（贝叶斯/潜变量）、D2（分析→Results 一体化）
- **架构**：E1（模型网关）、E7（研究者画像）、G1（Ollama 对接）
- **注意**：E6（审计轨迹）横切面大，放本批最后或顺延 P2。

### 批次 3 — P1 中成本 / 依赖项
- A5（上传 PDF RAG，成本中）、E6（审计轨迹，横切）
- 依赖链：B6 ← B3；A12 ← A8（可选）。

### 批次 4 — P2 长期演进（按需求热度排序）
- 检索：A3/A4/A6/A8/A9/A11/A13/A14/A16/A17
- 可信度：B4/B7；写作：C3/C4/C5/C6；数据：D3/D4
- 架构：E3/E4/E5/E8/E9；昇腾：G2
- 自动化科研：H2/H3/H4/H5/H6/H7

---

## 五、变更记录

| 日期 | 变更 |
|------|------|
| 2026-08-14 | 创建：基于 competitive-analysis.md 生成可执行方案；批次 0 标记 B2 已落地 |
| 2026-08-14 | 批次 1 落地：B3（审稿结构化输出 + response 串联）+ H1（审稿迭代闭环）；`tests/unit` 308 passed + ruff 全绿 |

# 研究Agent平台 — 同类开源项目调研与优化方案

> 状态：✅ 调研完成（11/11 组仓库，详见第四节完成度）
> 目的：通过对 GitHub 上同类科研 AI Agent 开源项目的深度调研，找出本平台（研究Agent平台）可借鉴的优化点，输出可落地的优化建议与优先级路线图。
> 调研时间：2026-08（web 检索）

---

## 一、调研范围与结论摘要

### 1.1 本地平台现状（对比基准）

- **后端**：Python FastAPI + Alembic；**前端**：React 18 + TypeScript + Vite + Tailwind
- **科研工作台（20+ Agent）**：coordinator 智能路由、literature 文献检索（Semantic Scholar/arXiv）、reader 论文精读、library 文献库（收藏/分类/标签/笔记）、citation 引用网络（图谱/共引/聚类/前沿/脉络）、data/stats 数据分析（回归/方差/非参数/生存/卡方/审计）、writing 写作、experiment 实验设计（功效分析）、reviewer 模拟审稿、response 审稿回复、figure 图表、cover、methods、polishing、paper2ppt、paper_to_patent、submission_package、data_availability、export、billing
- **昇腾工作台（本地 NPU 推理）**：ascend / adaptation / alignment / profiling / perf_tuning / toolchain / validator / debugging / history_to_skill
- **工程特性**：双后端缓存（内存/Redis）、双后端限流（Redis ZSET+Lua）、Milvus 向量检索、JWT 认证、统一 LibraryService 状态同步、并行 Agent + 结果传递、LLM 远程/昇腾双后端

### 1.2 已调研的同类项目一览

| 项目 | 定位 | 与本平台关系 |
|------|------|--------------|
| [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher) | 通用自主深度研究 Agent（多 Agent 编排 + 20+ 数据源 + 报告生成） | 最接近的"Agent 编排"参考，但面向通用网络调研 |
| [Future-House/paper-qa](https://github.com/Future-House/paper-qa) | 面向科学文献的**引用级**高精度 RAG 问答（PaperQA2，RAG-QA Arena SOTA） | 可被 literature/reader 直接集成，补引用级 grounding |
| [kaixindelele/ChatPaper](https://github.com/kaixindelele/ChatPaper) | arXiv 检索 + AI 总结/翻译/润色/审稿/审稿回复流水线（5.7k star） | 审稿回复闭环与批处理场景值得借鉴 |
| [SakanaAI/AI-Scientist](https://github.com/SakanaAI/AI-Scientist) / [v2](https://github.com/SakanaAI/AI-Scientist-v2) | 全自动科学发现：选题→实验→写作→审稿（ICLR 2025 6/7/6 通过同行评审） | 自动化闭环标杆：审稿迭代、实验沙箱、树搜索可借鉴 |
| [MingfengHong/paperseek](https://github.com/MingfengHong/paperseek) | 中文文献发现 Agent：自然语言→迭代检索→候选扩展→排序→可复核导出 | literature 检索策略 Agent 化参考 |
| [akiasprin/ripple-reader](https://github.com/akiasprin/ripple-reader) 等 | LLM 论文发现与深度阅读（信息不足，仅标题） | 涟漪式扩散发现（推测，需核实） |
| [HolobiomicsLab/Perspicacite-AI](https://github.com/HolobiomicsLab/Perspicacite-AI) | Agentic 文献助手：找到并理解文献不迷失；来源级 SSE 流式 | AI 总结可实时溯源参考 |
| [moonlarry/awesome-llm-paper-wiki](https://github.com/moonlarry/awesome-llm-paper-wiki) | LLM 驱动的本地 Markdown 文献库 + 综述自动化 | library 文件化导出 + 综述管线参考 |
| [argahv/sisyphus-academica](https://github.com/argahv/sisyphus-academica) 等 | 综述/新颖性生成/引用验证/对抗性审稿管线 | 引用质检与红队审稿参考 |
| [Intersect-Collaborations-LLC/research-workflow-assistant](https://github.com/Intersect-Collaborations-LLC/research-workflow-assistant) | IDE 内嵌 + 六数据源 MCP 聚合 + ICMJE 合规 + 审计轨迹 | 审计轨迹/系统综述/MCP 数据源层参考 |
| [ShaishavMaisuria/research-paper-lifecycle-skills](https://github.com/ShaishavMaisuria/research-paper-lifecycle-skills) | 42 技能覆盖论文全生命周期（综述/rebuttal/camera-ready/slides） | 生命周期编排 + Rebuttal 方法学参考 |
| [cang-zhu/AcAgent](https://github.com/cang-zhu/AcAgent) | 学术型智能体（信息不足，未检索到 README 细节） | 仅确认体量小、个人化，无有效可借鉴点 |
| [AlphaLab-USTC/ResearchClaw](https://github.com/AlphaLab-USTC/ResearchClaw) 等技能库 | 科研工作流展示 + 研究者画像 + 看板阅读清单 | 研究者画像/系统综述工作流参考 |
| [wentorai/research-plugins](https://github.com/wentorai/research-plugins) | 350+ 科研技能/MCP 配置合集（三级目录组织） | 技能目录组织/建模策略/人性化改写参考 |
| [joshzyj/open-scholar-skill](https://github.com/joshzyj/open-scholar-skill) | 社科研技能集：贝叶斯 brms/LCA/SEM/序列分析 + 分析-写作闭环 + 定时文献监控 | 统计方法广度 + 主动文献服务参考 |
| [JosephElvisMaman1/ResearchPilot-Skills](https://github.com/JosephElvisMaman1/ResearchPilot-Skills) | 9 技能：证据检索/引用验证/文献扩展，OpenAlex+CrossRef 免费 API | 幻觉引用检测/免费数据源参考 |

### 1.3 核心结论（摘要）

1. **本平台在"学术工作流覆盖广度"上领先**所有调研项目——没有任何同类项目同时具备文献库、引用网络、写作、实验设计、模拟审稿、投稿打包的完整学术闭环 + 本地 NPU 推理。
2. **最值得借鉴的能力缺口**（详见第五节）：
   - 引用级/证据级 grounding（paper-qa 的强项，本平台 reviewer/reader 尚未做到句子级溯源）
   - 对抗式事实审查（gpt-researcher / sisyphus-academica 的强项；本平台 reviewer 仅在"给定内容内"评估，无外部查证）
   - 审稿→修改→再审稿自动迭代闭环（AI-Scientist v1 的强项，本平台 reviewer/response 尚未串联成闭环）
   - 自动实验代码执行沙箱（AI-Scientist v1 的分水岭能力，本平台 experiment 仅出方案）
3. **本地已具备大量候选能力**（代码级核实）：多数据源分级检索、Milvus RAG、WebSocket 流式、LLM 重试/双后端、引用验证、证据链分析、多格式导出——优化清单已剔除这些"重复造轮子"项。

---

## 二、本地平台能力核实（代码级验证，2026-08）

> 为避免"重复造轮子"式的优化建议，对本地代码库做了现状核实。下列能力**已存在**，优化清单中不再作为建议项（或仅作增强项）。

| 能力 | 位置（代码证据） | 状态 |
|------|------------------|------|
| LLM 双后端（remote / ascend NPU）+ 用户级 API 覆盖 | `app/utils/llm.py` — `LLMClient`（LLM_MODE 切换，用户级 api_key/base_url/model 覆盖） | ✅ 已有 |
| LLM 调用重试/指数退避 | `app/utils/llm.py` — MAX_RETRIES=3, RETRY_BACKOFF=2.0；`nature_citation.py` retry_with_backoff | ✅ 已有 |
| WebSocket 任务进度流式推送（后端 + 前端） | `app/api/v1/ws.py`（E4 事件总线）；`frontend/src/hooks/useTaskStream.ts` | ✅ 已有 |
| LLM 流式输出（chunk 级） | `app/utils/llm.py` generate_stream；`app/agents/base.py` call_llm_stream | ✅ 已有 |
| 多学术数据源分级路由（T1/T2/T3） | `app/agents/literature/agent.py` — semantic_scholar/arxiv/pubmed/crossref/scopus/science_direct | ✅ 已有 |
| 向量检索（Milvus）+ 多模式 Embedding | `app/core/vector_store.py`；`app/utils/embedding.py`（remote/ascend/npu_local） | ✅ 已有 |
| 文献库记忆（向量插入/召回） | `app/agents/literature/tools.py`（insert/recall，embedding 化） | ✅ 已有 |
| 引用验证（LLM 判断：引用是否支撑论断/缺失/多余/格式） | `app/agents/citation/agent.py` verify_citations | ✅ 已有 |
| 证据链分析 / 裸论断检测 | `app/agents/writing/agent.py` analyze_evidence；writing/tools.py 证据评估 | ✅ 已有 |
| 模拟审稿（3 审稿人 + 交叉综述 + 事实基础提取） | `app/agents/reviewer/agent.py`（FACT_BASE_EXTRACTION_PROMPT） | ✅ 已有 |
| 引用网络（图谱/共引/聚类/前沿/脉络/时间线） | `app/services/citation_network.py`；literature/citation.py | ✅ 已有 |
| 多格式导出（RIS/ENW/Zotero RDF/CSV/BibTeX/Word/LaTeX） | `app/agents/citation/scripts/nature_citation.py`；`app/utils/export.py` | ✅ 已有 |
| CrossRef/DOI 解析 | nature_citation.py fetch_crossref/fetch_crossref_doi | ✅ 已有 |
| token 预算控制 | `app/agents/base.py` _apply_token_budget | ✅ 已有 |
| 翻译能力（reader 中英对照 / polishing translate） | reader/agent.py 6步工作流；polishing/agent.py translate | ✅ 已有 |
| 论文转 PPT / 专利（证据账本 + 审计） | paper2ppt/agent.py；paper_to_patent/agent.py（source_map→evidence_ledger→claims→audit） | ✅ 已有 |
| 上传文档研究基础（uploads + data upload） | data/agent.py upload；uploads/ 目录 | ⚠️ 部分（未见对上传 PDF 的通用 RAG 问答链路） |
| 句子级/证据级引用 grounding | 未见 reader/literature 输出逐句溯源（当前为章节/段落级） | ❌ 缺失 |
| 对抗式事实复核（对生成内容外部查证后复核） | reviewer 在"给定内容内"评估证据，未见外部查证步骤 | ❌ 缺失 |
| 真实 MCP 协议接入 | 仅 `literature.MCP_TOOLS` 为命名惯例，无 mcp python 包集成 | ❌ 缺失 |
| 公开基准质量门禁（RAG-QA Arena 等） | 未见评测接入 | ❌ 缺失 |
| 每日 arXiv 新论文批处理订阅 | 未见定时任务 | ❌ 缺失 |

---

## 三、已深度调研项目明细

### 2.1 assafelovic/gpt-researcher

- **URL**：https://github.com/assafelovic/gpt-researcher
- **定位**：开源自主在线深度研究 Agent，自动执行"生成研究计划 → 并行检索网页 → 提取/压缩上下文 → 汇总成带引用的长篇研究报告"，不绑定单一 LLM 或搜索引擎；提供单 Agent 深度研究管线 + LangGraph 多 Agent 编辑团队两种模式，配套 Next.js 前端、WebSocket 流式、Docker 与 MCP 服务。
- **技术栈**：Python/FastAPI；前端 Next.js/React；LangGraph 编排；LiteLLM 支持 100+ 模型；20+ 搜索引擎/数据源（Tavily/Serper/Google/Bing/arXiv/PubMed/Wikipedia 等）；搜索 API + 本地向量库混合检索；WebSocket 流式；MCP Server。
- **核心功能**：自动深度研究（大纲→并行检索→带内联引用报告）；双模式架构（单 Agent 管线 + 多 Agent 编辑团队）；LLM 无关（LiteLLM）；20+ 数据源；报告可定制（大纲/语气/语言/字数/领域）；多格式导出（PDF/Docx/MD/JSON/CSV）；MCP 双向集成；WebSocket 流式 + Docker。
- **值得借鉴的技术**：
  - Plan-and-Solve 管线：planner 拆解研究问题，子问题并行检索后 curator 汇总，避免"总结即回答"
  - 上下文压缩：embeddings 相似度过滤，只保留最相关段落，防上下文溢出
  - 混合检索：搜索 API 召回 + 本地向量库重排序
  - **对抗式审查**：reviewer/curator 对生成事实复核改写，抑制幻觉与错误引用
  - LangGraph 状态图编排多 Agent；WebSocket 流式进度；MCP 双向接入
- **优化机会点（对本平台）**：
  1. **LLM 无关提供商抽象层**：本平台已有远程/昇腾双后端，可进一步抽象为统一模型网关（类 LiteLLM），支持一键切换与多模型路由
  2. **多数据源 + 混合检索**：literature 目前以 Semantic Scholar/arXiv 为主，可扩展 20+ 学术数据源（OpenAlex/PubMed/Europe PMC/CrossRef）并加向量重排序
  3. **对抗式事实审查 Agent**：在 writing/reviewer 后增加"事实复核"环节，抑制幻觉与错误引用——科研写作可信度关键
  4. **WebSocket 流式研究进度**：长任务（综述/深度报告）实时反馈，可中断
  5. **报告结构高度可定制**（大纲/语气/字数/领域预设）：贴近不同学科与期刊规范
  6. **MCP 双向接入**：平台能力可被外部 Agent 复用，也可接入外部数据源，生态化关键
  7. **自有文档/上传文件研究**：基于用户上传 PDF/语料做研究，弥补纯检索盲区

### 2.2 Future-House/paper-qa

- **URL**：https://github.com/Future-House/paper-qa
- **定位**：高精度 RAG 工具——"对科学文献/文档进行带引用的问答"。PaperQA2 为 agentic RAG 管线，RAG-QA Arena 科学基准 SOTA（对应论文《Language agents achieve superhuman synthesis of scientific knowledge》，arXiv 2409.13740），约 8.8k star。
- **技术栈**：Python 库 + CLI；LiteLLM 抽象 LLM 后端（OpenAI/本地/Ollama）；默认 **Numpy dense vector store**（不依赖外部向量库）；pydantic Settings 集中配置。
- **核心功能**：引用级问答（citation-grounded）；可调 source/passage 数量控制 token；agentic 多步证据选择；支持本地/自托管 LLM；可配置 embedding；CLI + Python 库。
- **值得借鉴的技术**：
  - **Agentic RAG 循环**：搜索→收集证据→引用→作答的多步闭环
  - **引用级 grounding**：答案逐条关联来源证据（句子级），可信度大幅提升
  - 轻量向量存储（Numpy dense store）：降低部署复杂度
  - LiteLLM 多后端抽象 + 本地模型支持
  - 可调检索粒度做 token 成本预算；pydantic Settings 声明式配置
  - **评估驱动**：用 RAG-QA Arena/LiteQA 基准做量化验证
- **优化机会点（对本平台）**：
  1. **引用级/证据级 grounding**：本平台 reader/literature 多为文档块级引用，升级为句子级证据关联，回答可信度质变
  2. **Agentic 多步证据收集**：复杂科研问题（跨多篇论文）用"检索→收集→引用→作答"闭环替代单次 RAG
  3. **公开基准量化质量**：接入 RAG-QA Arena 类评测作为质量门禁
  4. **可调 source/passage 与 token 成本预算**：显式控制上下文与成本
  5. **Settings 声明式配置体系**：模型/参数集中切换，便于 A/B 实验

### 2.3 kaixindelele/ChatPaper

- **URL**：https://github.com/kaixindelele/ChatPaper
- **定位**：中文社区经典 arXiv 检索 + AI 总结工具（5.7k star），"全流程加速科研"：检索→总结→翻译→润色→审稿（优缺点+改进建议）→审稿回复 一站式链路。
- **技术栈**：Python；arxiv、openai、tenacity（重试/限流容错）、tiktoken（token 计数/长文分段）、argparse；衍生版 Gradio/HuggingFace。
- **核心功能**：arXiv 关键词检索；全文总结；专业翻译；润色；审稿（优缺点+改进建议）；**审稿回复**；全流程批处理；结果本地 markdown 归档。
- **值得借鉴的技术**：
  - tenacity 对 LLM API 自动重试与限流容错（大批量调用稳定）
  - token 计数 + 长文分段规避上下文限制
  - 多角色结构化 Prompt 模板（审稿人视角输出优缺点+改进建议）
  - **"审稿→审稿回复"闭环**
- **优化机会点（对本平台）**：
  1. **审稿回复闭环补强**：本平台已有 reviewer + response，可借鉴"审稿意见→回复草稿"的直接串联与结构化模板
  2. **审稿输出"优缺点+改进建议"结构化**：不只给分，给出可操作改进方向，服务投稿前自检
  3. **每日新论文批处理**：arXiv 原生检索 + 关键词过滤 + 批量速读场景
  4. **翻译+润色一体化**：专业翻译作为标准内置步骤
  5. **本地归档为 markdown/可版本化文件**：沉淀个人论文笔记库
  6. **LLM 调用限流重试工程化**（tenacity 模式）融入平台调用层

### 2.4 SakanaAI/AI-Scientist 与 AI-Scientist-v2

- **URL**：https://github.com/SakanaAI/AI-Scientist ；https://github.com/SakanaAI/AI-Scientist-v2
- **定位**：AI-Scientist v1 是首个端到端自动化的 AI 科研系统——LLM 从选题（idea）出发，自主完成实验执行 → 论文撰写（LaTeX）→ 自动审稿 → 迭代改进，全程零人工，产出可投稿论文（约 15 美元/篇）；论文投稿 ICLR 2025 工作坊获 6/7/6 通过同行评审，2026-03 登上 Nature。v2 用 **Agentic Tree Search（智能体树搜索）** 替代单线流程：同时探索多个研究分支、按价值评分剪枝、深挖有潜力的分支，产出 Workshop 级成果（ICLR 2025 工作坊通过，宣称击败 55% 人类投稿）。
- **技术栈**：Python；闭源商用 LLM API（GPT-4o/Claude 等，多模型可配）；LaTeX 模板系统 + nanoGPT 等可训练基线；受控沙箱代码执行（Docker 隔离）；v2 应用于 GNN/语言模型两个 benchmark 领域。
- **核心功能**：自动想法生成（novelty 过滤）；沙箱内真实实验执行（跑真实训练脚本）；自动论文撰写；自动审稿 Agent（多维度打分）；审稿→修改→再审稿迭代闭环；v2 多分支并行 + 剪枝择优。
- **值得借鉴的技术**：
  - **全流程 agent 化闭环**：idea → experiment → writing → review → iterate，而非单点工具
  - **模板驱动基座**：可复用基线（nanoGPT）+ LaTeX 模板，新研究一键起跑
  - **审稿 Agent 作为质量闸门**：把"写"与"评"分离，审稿分数驱动写作迭代
  - **真实实验而非脑补**：论文数值来自沙箱真实运行结果
  - **树搜索形式化科研路径选择**：分支生成→评分→剪枝→深化，可解释、可回放、可审计
  - **成本量化**：15 美元/篇，可复现可优化
- **优化机会点（对本平台）**：
  1. **审稿→修改自动迭代闭环**：把现有 reviewer + response 串成"审稿→修改→再审稿"循环，以审稿分数为停止条件——改动小、见效快，直接提升论文质量上限
  2. **自动实验代码执行沙箱**：让 experiment Agent 从"给方案"升级为"在沙箱里真跑数据"，数据回流 writing——与"自动科研"的分水岭
  3. **自动选题/假设生成（novelty 过滤）**：批量生成候选研究想法并按新颖性筛选，从"辅助执行"升级为"主动提出研究问题"
  4. **树搜索式多方向探索**：在 coordinator 之上加"研究假设生成 + 分支评估"层，作为长期规划项；昇腾 NPU 本地推理使实验执行成本可控
  5. **可复用研究模板库**：基线 + 论文模板沉淀为平台资产，降低冷启动成本
  6. **研究轨迹审计（tree log）**：探索留痕，提升可复现性与审稿/合规加分
  7. **代码沙箱 + 安全审查**：开放"自动实验"能力所需的必备安全基础设施
  8. **用真实评测做系统验收**：沉淀平台自己的 Agent 评测套件

### 2.6 MingfengHong/paperseek

- **URL**：https://github.com/MingfengHong/paperseek
- **定位**：LLM based Literature Search Agent——面向研究者的文献发现工具：自然语言发起检索 → **自动迭代查询** → **扩展候选论文** → 排序 → **导出可复核的文献列表**。以 Python 包 + Agent Skill（ModelScope/JinDaGe）+ Vercel 演示多形态分发；数据源 PubMed。
- **核心功能**：自然语言检索；自动迭代查询（首轮结果驱动查询改写）；候选论文扩展；相关性排序；可复核导出（带来源）；Skill 化可嵌入。
- **值得借鉴的技术**：检索策略 Agent 化（查询改写+多轮收敛）；可复核性设计（AI 检索结果默认不可信，导出带命中依据）；多形态分发（pip + Skill + Web）。
- **优化机会点（对本平台）**：
  1. **迭代查询/查询改写闭环**：literature 目前"一次检索+AI 总结"，缺多轮改写收敛——显著提升冷启动召回率
  2. **候选论文扩展（涟漪式）**：从命中论文沿引文/共被引/关键词扩展，与 citation 引用网络深度联动
  3. **可复核导出**：导出列表保留每篇来源/命中依据，可审计、可评估检索质量

### 2.7 akiasprin/ripple-reader 与 HolobiomicsLab/Perspicacite-AI

- **URL**：https://github.com/akiasprin/ripple-reader ；https://github.com/HolobiomicsLab/Perspicacite-AI
- **定位**：ripple-reader 为 "LLM-driven academic paper discovery & deep reading"（公开信息极少，仅标题，涟漪式扩散为命名推断）；Perspicacite-AI 为面向科学家/研究者/学生的 **Agentic 文献助手**（"在海量论文中找到并理解文献而不迷失"），生物组学实验室出品，有 docs 与回归测试。
- **技术栈（Perspicacite-AI）**：Python；**SSE 流式**（_stream_agentic 逐条发射 source 事件）；React 单组件设计稿；ASB fixture 回归测试。
- **核心功能（Perspicacite-AI）**：Agentic 文献发现与理解；**来源级 SSE 流式输出**（生成过程逐条推送当前引用文献的来源事件）；过程透明化；回归测试保障。
- **值得借鉴的技术**：
  - **来源级流式事件**：生成过程中逐条推送"当前引用了哪篇文献"，用户实时校验答案可信度
  - Agent 过程透明化（正在检索/读/引用什么逐步可视化）
  - agentic 流程回归测试（含 fixture），防止编排逻辑回归
- **优化机会点（对本平台）**：
  1. **来源级流式事件**：literature/reader 的 AI 总结目前整体返回，改为"生成过程逐条推送引用来源"可实时溯源
  2. **Agent 执行过程可视化**：20+ Agent 的执行过程追踪（检索/读/引用逐步展示）
  3. **Agent 流程回归测试**：为多步 Agent 流程建立回归测试套件
  4. **涟漪式扩散发现**（推测）：从种子论文沿引用/共被引扩散，与 citation Agent 结合形成"种子论文长出相关文献子图"

### 2.8 moonlarry/awesome-llm-paper-wiki

- **URL**：https://github.com/moonlarry/awesome-llm-paper-wiki
- **定位**：LLM Agent 驱动的**本地 Markdown 文献库管理与学术综述自动化系统**，以 Claude Code Agent Skill 形态分发（paper-wiki / digest / wiki-query）。核心思想："文件即知识库"（LLM Wiki 模式）——文献库就是 Markdown 文件集合，可 Git 版本管理、可被 Obsidian 等任意工具读取、数据不锁定在专有数据库。
- **核心功能**：本地 Markdown 文献库管理；学术综述自动化；digest 论文摘要沉淀；wiki-query 自然语言查库；架构文档化。
- **值得借鉴的技术**：Markdown 文件化文献库（可移植/可版本化/可离线）；综述自动化管线（库→综述）；Skill 化集成。
- **优化机会点（对本平台）**：
  1. **Markdown 文件化文献库 + 双向同步**：library 增加"一键导出/同步为本地 Markdown 文献库"，数据可移植、可版本管理、可离线
  2. **综述自动化管线**：从已收藏文献库直接生成结构化综述（按主题聚合→生成章节→附引用），打通 library/citation/literature 的"库→文"收尾能力
  3. **digest 式日常沉淀**：每次检索/精读自动生成可入库存档的 Markdown 笔记，把一次性问答变成可持续知识资产
  4. **自然语言查库（wiki-query）**：library 当前偏结构化过滤，缺语义化问答查库

### 2.9 argahv/sisyphus-academica

- **URL**：https://github.com/argahv/sisyphus-academica
- **定位**：开源研究管道（research pipeline）：**文献综述 → 新颖性生成 → 引用验证 → 对抗性审查**。把证据层面的质检（引用真伪、论断支撑）与对抗视角审查嵌入写作流程，而非"写完即出"。
- **核心功能**：文献综述；新颖性生成（创新点/卖点提炼）；引用验证（引文真伪与支撑度校验）；对抗性审查（红队找茬攻击稿件假设）；管道化职责分离。
- **值得借鉴的技术**：引用验证作为**独立质检环节**前置（直击 LLM 幻觉引用）；新颖性显式化（"贡献点"变成可生成可审查的对象）；对抗性审查（审稿=系统性攻击假设而非打分）。
- **优化机会点（对本平台）**：
  1. **引用真实性验证**：逐条核对引文真实存在（CrossRef/OpenAlex/Semantic Scholar 元数据）+ 判定是否真正支撑该句论断
  2. **新颖性/贡献点检测与生成**：投稿前自动生成卖点陈述并对照相关工作判断重复度，回应"novelty 不足"拒稿理由
  3. **对抗性自审（红队审稿）**：与 reviewer 结合，输出"假设漏洞/弱证据/过度声称"驱动的拒稿风险清单

### 2.10 Intersect-Collaborations-LLC/research-workflow-assistant

- **URL**：https://github.com/Intersect-Collaborations-LLC/research-workflow-assistant
- **定位**：面向 VS Code + GitHub Copilot 的开源 AI 科研助手，通过 **MCP 服务器统一接入 PubMed、OpenAlex、Semantic Scholar、Europe PMC、CrossRef 与 Zotero** 六大数据源；自定义 agents 引导系统综述、学术写作、数据分析与项目管理，全程 **ICMJE 合规**并保留**完整审计轨迹**。
- **技术栈**：VS Code 扩展 + Copilot；MCP 服务器连接层（六路数据源）；Python 生态（market.dev 归类）。
- **核心功能**：多路学术检索统一接入；Zotero 本地库对接；系统综述引导式工作流；学术写作/数据分析/项目管理 agent；ICMJE 合规输出约束；完整审计轨迹。
- **值得借鉴的技术**：六大数据源经 MCP 统一封装；**审计轨迹**（科研可信度工程，AI 改动可追溯可复核）；ICMJE 规范编码进 agent 行为；系统综述流程化（检索→筛选→提取→综合）。
- **优化机会点（对本平台）**：
  1. **审计轨迹/可追溯性**：为每个 agent 输出记录"输入证据→处理动作→输出变更"链并在界面展示来源
  2. **ICMJE/期刊规范约束**：把目标期刊格式规范做成可配置 agent 约束，submission_package 自动合规检查
  3. **系统综述专用流程**：多阶段筛选/提取状态机，服务元分析与综述类用户
  4. **Zotero 对接**：接入研究者既有文献管理工具

### 2.11 ShaishavMaisuria/research-paper-lifecycle-skills

- **URL**：https://github.com/ShaishavMaisuria/research-paper-lifecycle-skills
- **定位**：42 个 AI agent 技能包，覆盖论文全生命周期：文献综述、学术写作、引用验证、会议投稿、**rebuttal（审稿回复）**、发表（camera-ready）、演示（slides）。Agent Skills 标准结构（SKILL.md），面向 Claude Code 等。
- **核心功能**：literature-review；orchestrate-paper（总控编排）；draft-related-work；verify-claims（论断验证）；write-rebuttal；prepare-camera-ready；make-slides。
- **值得借鉴的技术**：生命周期全覆盖的**编排设计**（总控技能先协调再分步）；Rebuttal 独立成技能（逐条意见→回应→证据支撑）；camera-ready + slides 收尾闭环；SKILL.md 声明式技能包（多运行时复用）。
- **优化机会点（对本平台）**：
  1. **Rebuttal 全流程方法学**：response 升级为"审稿意见逐条映射→强弱分类→证据引用→语气控制"完整工作流
  2. **Camera-ready 定稿技能**：投稿接收后的版面/版权/参考文献校对环节，submission_package 扩展"接收后处理"阶段
  3. **汇报幻灯片生成**：论文→演示转换（本地 paper2ppt 偏论文转 PPT，可补"汇报版"模式）
  4. **生命周期阶段状态机**：按综述→写作→投稿→rebuttal→camera-ready→slides 组织任务与状态

### 2.12 AlphaLab-USTC/ResearchClaw

- **URL**：https://github.com/AlphaLab-USTC/ResearchClaw
- **定位**："上朝式科研：AI-powered research workflow showcase"——科研工作流技能展示库（reading-list 看板、literature-review、systematic-review、literature-search），含 docs/config.md 与 research-profile-example.md（研究者画像）。
- **值得借鉴的技术**：**研究者画像（research profile）**（"我是谁/研究什么/偏好什么"独立配置文件供所有技能共享）；看板式阅读管理；workflow showcase 模式。
- **优化机会点（对本平台）**：
  1. **研究者画像机制**：集中管理研究方向/偏好，注入 20+ Agent 提示词，替代每次重复描述
  2. **看板式阅读清单/仪表盘**：把"检索"升级为"阅读状态管理"闭环（结合 Redis/Milvus 持久化）
  3. **系统综述工作流**：PRISMA 式筛选、质量评估、证据表（面向发综述用户的高价值场景）
  - 注：衍生项目 AutoResearchClaw 的**沙箱实验 + NaN/Inf 检测 + LLM 自愈代码 + HITL** 思路值得关注（属衍生能力）

### 2.13 wentorai/research-plugins

- **URL**：https://github.com/wentorai/research-plugins
- **定位**：350+ 学术科研技能/MCP 配置/插件合集，面向 Research-Claw 及各类 AI Agent；npm 分发；目录结构 `skills/<领域>/<子类>/<技能>/SKILL.md`（research / analysis / writing / tools 四领域）。代表技能：research-paper-kb（研究论文知识库方法论）、modeling-strategy-guide（统计建模策略）、ai-writing-humanizer（AI 写作人性化改写）、zotero-api / zotero-mcp-guide。
- **值得借鉴的技术**：三级目录组织（技能可索引可组合）；**AI 写作人性化改写独立成技能**（写作后处理管线）；**统计方法论指南与执行分离**（先决策后执行）；工具对接技能化（Zotero）；npm 分发。
- **优化机会点（对本平台）**：
  1. **统计建模策略指南**：跑回归/方差前先由"方法论技能"给出模型选择建议（OLS vs logit vs 面板 vs 生存）
  2. **AI 写作人性化改写**：检测并改写 AI 痕迹（润色后处理），国内论文场景需求大
  3. **技能目录组织**：把 Agent 能力拆成可索引技能单元，前端做"技能/Agent 目录页"
  4. **Zotero 对接**：Zotero API/MCP 与本地 Milvus 文献库双向同步

### 2.14 joshzyj/open-scholar-skill

- **URL**：https://github.com/joshzyj/open-scholar-skill
- **定位**：面向**社会科学**研究的 Claude Code 插件/技能集，覆盖 idea 生成、研究设计、数据分析到结果撰写、文献监控完整链路。技能表：scholar-analyze（OLS、logit、**贝叶斯 brms**、LCA、**SEM**、序列分析、分位数回归）、scholar-eda、scholar-idea、scholar-design、scholar-causal、scholar-compute、scholar-knowledge、scholar-monitor（/loop 定时文献监控 + cadence_days 幂等过滤）、scholar-conceptual、scholar-citation 等。
- **值得借鉴的技术**：**统计方法覆盖最广**（贝叶斯 brms/潜变量 LCA/SEM/分位数回归）+ **分析结果撰写一体化**（analyze 直接产出可投稿结果段落）；定时文献监控幂等去重；选题前置技能；研究设计/因果推断前置。
- **优化机会点（对本平台）**：
  1. **贝叶斯统计（brms）支持**：扩展贝叶斯回归/分层模型——社科与生物医学论文的差异化能力
  2. **潜变量/高级方法（LCA、SEM、序列分析、分位数回归）**：按数据形态自动推荐方法
  3. **分析与结果撰写一体化**：统计后自动生成 Results 章节（表格+显著性表述），打通 data 与 writing
  4. **文献定时监控/周报（幂等去重）**：平台从"被动检索"变"主动服务"

### 2.15 JosephElvisMaman1/ResearchPilot-Skills

- **URL**：https://github.com/JosephElvisMaman1/ResearchPilot-Skills
- **定位**：9 个轻量学术研究技能，聚焦**证据检索、引用验证、文献扩展**三大能力；跨 Claude Code/Codex/Gemini CLI；内置 **OpenAlex 与 CrossRef 免费 API 层**（无 key 免费调用）。
- **值得借鉴的技术**：**引用验证做成独立技能**（针对 AI 幻觉引用痛点，用 CrossRef/OpenAlex 做 DOI 与元数据核验）；免费 API 优先（零成本零合规门槛）；跨 CLI 兼容（技能即资产可移植）。
- **优化机会点（对本平台）**：
  1. **引用验证/幻觉引用检测**：writing 生成参考文献后自动核验（DOI/标题/作者/卷期），错配条目打标或重写——解决 AI 论文助手最大信任问题
  2. **证据检索（evidence grounding）**：论断级检索支撑文献，每条结论挂证据链
  3. **免费元数据源接入**：OpenAlex/CrossRef 作为本地检索后备数据源（Redis 限流正好承接免费 API 速率限制）

### 2.16 cang-zhu/AcAgent

- **URL**：https://github.com/cang-zhu/AcAgent
- **结论**：仅见仓库描述"一款学术型智能体"，README 与功能细节未被搜索引擎索引，**信息不足**，无法提炼有效借鉴点。仅确认体量小、个人化，无与本地平台的实质可比性。

---

## 四、调研完成度

全部 11 组仓库调研完成：gpt-researcher、paper-qa、ChatPaper、AI-Scientist 系列、paperseek、ripple-reader、Perspicacite-AI、awesome-llm-paper-wiki、sisyphus-academica、research-workflow-assistant、research-paper-lifecycle-skills、ResearchClaw、research-plugins、open-scholar-skill、ResearchPilot-Skills、AcAgent（信息不足）。
- 信息充分：gpt-researcher / paper-qa / ChatPaper / AI-Scientist 系列 / paperseek / Perspicacite-AI / awesome-llm-paper-wiki / sisyphus-academica / research-workflow-assistant / research-paper-lifecycle-skills / open-scholar-skill
- 信息中等：ResearchClaw / research-plugins / ResearchPilot-Skills（技能清单未全量枚举）
- 信息不足：ripple-reader（仅标题）/ AcAgent（无 README 索引）

---

## 五、优化机会点清单（完整版）

> 按模块归类；每项标注来源项目与优先级建议（P0 高价值低成本 / P1 高价值中成本 / P2 长期演进）

### A. 文献检索与阅读（literature / reader）

| # | 优化点 | 来源 | 本地现状 | 优先级 |
|---|--------|------|----------|--------|
| A1 | 扩展学术数据源（OpenAlex/Europe PMC）+ 向量重排序混合检索 | gpt-researcher | ⚠️ 部分（已有 pubmed/crossref/scopus/science_direct 分级路由，缺 OpenAlex/Europe PMC 与向量重排序） | P1 |
| A2 | 句子级/证据级引用 grounding（答案逐条关联来源证据） | paper-qa | ❌ 缺失（当前章节/段落级） | P1 |
| A3 | Agentic 多步证据收集闭环替代单次 RAG | paper-qa | ❌ 缺失 | P2 |
| A4 | 每日 arXiv 新论文批处理 + 关键词过滤速读 | ChatPaper | ❌ 缺失（无定时任务） | P2 |
| A5 | 自有文档/上传 PDF 研究（本地语料检索） | gpt-researcher | ⚠️ 部分（有 uploads + Milvus + 文献库记忆，缺通用上传 PDF RAG 问答链路） | P1 |
| A6 | token 成本预算：可调检索粒度（source/passage 数） | paper-qa | ⚠️ 部分（有 _apply_token_budget，缺检索粒度调节） | P2 |
| A7 | 迭代查询/查询改写闭环（自然语言→多轮迭代检索收敛） | paperseek | ❌ 缺失（当前单次检索+AI总结） | P1 |
| A8 | 候选论文扩展（涟漪式：沿引文/共被引/关键词扩展） | paperseek / ripple-reader | ⚠️ 部分（citation 有共引分析，缺"种子论文长出文献子图"的一体化流程） | P1 |
| A9 | 可复核导出（导出带命中依据的文献列表） | paperseek | ❌ 缺失 | P2 |
| A10 | 来源级流式事件（AI 生成过程逐条推送引用来源） | Perspicacite-AI | ❌ 缺失（有任务进度流，无逐来源事件） | P1 |
| A11 | Markdown 文件化文献库 + 双向同步（数据可移植/版本化/离线） | awesome-llm-paper-wiki | ❌ 缺失（library 为服务端数据库） | P2 |
| A12 | 综述自动化管线（文献库→结构化综述，含引用） | awesome-llm-paper-wiki | ❌ 缺失 | P1 |
| A13 | 自然语言查库（wiki-query 语义化问答） | awesome-llm-paper-wiki | ❌ 缺失（library 偏结构化过滤） | P2 |
| A14 | 系统综述工作流（PRISMA 式筛选/质量评估/证据表） | RWA / ResearchClaw | ❌ 缺失 | P2 |
| A15 | 文献定时监控/周报（幂等去重，主动推送新文献） | open-scholar-skill（/loop 模式） | ❌ 缺失（无定时任务） | P1 |
| A16 | 看板式阅读清单/文献状态管理（检索→阅读→笔记闭环） | ResearchClaw | ❌ 缺失 | P2 |
| A17 | Zotero 对接（API/MCP ↔ Milvus 文献库双向同步） | RWA / research-plugins | ❌ 缺失 | P2 |
| A18 | 免费元数据源（OpenAlex/CrossRef）作为检索后备（Redis 限流承接免费 API 速率） | ResearchPilot-Skills | ⚠️ 部分（已有 crossref，缺 OpenAlex） | P1 |

### B. 引用与可信度（citation / reviewer / writing）

| # | 优化点 | 来源 | 本地现状 | 优先级 |
|---|--------|------|----------|--------|
| B1 | 对抗式事实审查 Agent（复核生成事实与引用，抑制幻觉） | gpt-researcher / sisyphus-academica | ❌ 缺失（reviewer 仅在给定内容内评估，无外部查证步骤） | P1 |
| B2 | 引用验证（逐条核对引用是否存在、是否支持论断） | sisyphus-academica / ResearchPilot | ⚠️ 部分（citation.verify_citations 为 LLM 判断，未对接外部库实查） | P1 |
| B3 | 审稿输出结构化"优缺点+改进建议"，并直接串联审稿回复 | ChatPaper | ✅ 已落地（2026-08-14：assess 输出 strengths/improvement_suggestions + response.draft 接收 review_result 自动派生意见） | P0 ✅ |
| B4 | 公开基准量化质量门禁（RAG-QA Arena 类） | paper-qa | ❌ 缺失 | P2 |
| B5 | 对抗性/红队审稿模式（专攻假设漏洞/弱证据/过度声称，输出拒稿风险清单） | sisyphus-academica | ❌ 缺失 | P1 |
| B6 | Rebuttal 全流程方法学（审稿意见逐条映射→强弱分类→证据引用→语气控制） | lifecycle-skills | ⚠️ 部分（有 response agent，缺方法学工作流） | P1 |
| B7 | 新颖性/贡献点检测与生成（对照相关工作判断重复度） | sisyphus-academica | ❌ 缺失 | P2 |

### C. 写作与投稿闭环（writing / submission_package / paper2ppt）

| # | 优化点 | 来源 | 本地现状 | 优先级 |
|---|--------|------|----------|--------|
| C1 | 报告结构高度可定制（大纲/语气/字数/期刊领域预设） | gpt-researcher | ⚠️ 部分（writing 有论文类型模板，缺语气/字数/领域级预设） | P1 |
| C2 | 翻译+润色一体化内置步骤 | ChatPaper | ✅ 已具备（polishing.translate + reader 中英对照） | — |
| C3 | 输出本地可版本化归档（markdown/JSON） | ChatPaper | ⚠️ 部分（有导出，缺笔记库落盘链路） | P2 |
| C4 | digest 式日常沉淀（每次检索/精读自动生成可入库存档的 Markdown 笔记） | awesome-llm-paper-wiki | ❌ 缺失 | P2 |
| C5 | Camera-ready 定稿（接收后处理：版面/版权/参考文献校对） | lifecycle-skills | ❌ 缺失（submission_package 缺接收后阶段） | P2 |
| C6 | 汇报版幻灯片生成（论文→汇报演示模式） | lifecycle-skills | ❌ 缺失（paper2ppt 偏论文转 PPT） | P2 |
| C7 | ICMJE/期刊规范约束（submission_package 自动合规检查） | RWA | ❌ 缺失 | P1 |
| C8 | AI 写作人性化改写（AI 痕迹检测 + 改写后处理） | research-plugins | ❌ 缺失（polishing 偏语言润色） | P1 |

### D. 数据分析（data / stats）

| # | 优化点 | 来源 | 本地现状 | 优先级 |
|---|--------|------|----------|--------|
| D1 | 扩展统计方法覆盖（OLS/贝叶斯 brms/LCA/SEM/序列分析/分位数回归等） | open-scholar-skill | ⚠️ 部分（已有回归/方差/非参数/生存/卡方，缺贝叶斯/潜变量/序列分析） | P1 |
| D2 | 分析与结果撰写一体化（统计输出自动生成 Results 章节，打通 data/writing） | open-scholar-skill | ❌ 缺失（data 与 writing 独立） | P1 |
| D3 | 统计建模策略前置指南（跑检验前先做模型选择决策） | research-plugins | ❌ 缺失 | P2 |
| D4 | 研究设计/因果推断前置校验（数据分析前验证设计与识别策略） | open-scholar-skill | ⚠️ 部分（experiment 有设计推荐，缺因果推断校验） | P2 |

### E. 工程架构

| # | 优化点 | 来源 | 本地现状 | 优先级 |
|---|--------|------|----------|--------|
| E1 | 统一模型网关抽象（类 LiteLLM，远程/昇腾/多服务商一键切换路由） | gpt-researcher / paper-qa | ⚠️ 部分（已有 remote/ascend 双后端，缺多服务商注册与统一网关） | P1 |
| E2 | LLM 调用限流重试工程化（tenacity 模式） | ChatPaper | ✅ 已具备（llm.py MAX_RETRIES + 退避） | — |
| E3 | Settings 声明式配置体系（模型/参数集中可切换，A/B 实验） | paper-qa | ⚠️ 部分（有 config，缺按会话/任务的参数覆盖） | P2 |
| E4 | MCP 双向接入（平台能力对外暴露为工具 + 接入外部数据源） | gpt-researcher | ❌ 缺失（MCP_TOOLS 仅为命名惯例，无真实 MCP 协议） | P2 |
| E5 | Agent 流程回归测试（多步 Agent 编排防回归，含 fixture） | Perspicacite-AI | ❌ 缺失 | P2 |
| E6 | 审计轨迹/可追溯性（每个 agent 记录"证据→动作→输出"链，前端展示来源） | RWA | ❌ 缺失 | P1 |
| E7 | 研究者画像机制（集中管理研究方向/偏好，注入 20+ Agent 提示词） | ResearchClaw | ❌ 缺失 | P1 |
| E8 | 技能目录三级组织 + 前端"技能/Agent 目录页"（能力可索引可组合） | research-plugins | ❌ 缺失（Agent 平铺列表） | P2 |
| E9 | 沙箱实验 + NaN/Inf 检测 + LLM 自愈代码 + HITL（数据分析代码执行安全） | AutoResearchClaw（衍生） | ❌ 缺失 | P2 |

### F. 前端体验

| # | 优化点 | 来源 | 本地现状 | 优先级 |
|---|--------|------|----------|--------|
| F1 | WebSocket 流式研究进度（长任务实时反馈、可中断） | gpt-researcher | ✅ 已具备（E4 + useTaskStream） | — |

### G. 昇腾 NPU 差异化

| # | 优化点 | 来源 | 本地现状 | 优先级 |
|---|--------|------|----------|--------|
| G1 | 本地模型后端对接（Ollama/自托管 LLM 兼容层，放大小模型部署优势） | paper-qa | ⚠️ 部分（有 ascend 后端，缺通用 OpenAI 兼容本地服务注册） | P1 |
| G2 | 轻量向量存储可选（Numpy dense store 兜底，降低本地部署依赖） | paper-qa | ❌ 缺失 | P2 |

### H. 自动化科研闭环（AI-Scientist 系列）

| # | 优化点 | 来源 | 本地现状 | 优先级 |
|---|--------|------|----------|--------|
| H1 | 审稿→修改→再审稿自动迭代闭环（reviewer+response 串联，审稿分数为停止条件） | AI-Scientist v1 | ✅ 已落地（2026-08-14：review_loop 服务 + reviewer.score + writing.revise + POST /review-loop/run） | P0.5-P1 ✅ |
| H2 | 自动实验代码执行沙箱（experiment 从"给方案"升级为"沙箱跑真实数据"，数据回流 writing） | AI-Scientist v1 | ❌ 缺失（experiment 仅出方案） | P2（分水岭能力） |
| H3 | 自动选题/假设生成 + novelty 过滤（主动提出研究问题） | AI-Scientist v1 | ❌ 缺失 | P2 |
| H4 | 树搜索式多方向探索层（coordinator 之上加分支生成/评分/剪枝） | AI-Scientist v2 | ❌ 缺失（coordinator 为响应式路由） | P2（昇腾本地推理使成本可控） |
| H5 | 可复用研究模板库（基线 + LaTeX 论文模板沉淀为平台资产） | AI-Scientist v1 | ❌ 缺失 | P2 |
| H6 | 研究轨迹审计留痕（tree log：哪些分支试过、为何放弃） | AI-Scientist v2 | ❌ 缺失 | P2 |
| H7 | 平台自身 Agent 评测套件（以真实评测做系统验收） | AI-Scientist v2 | ❌ 缺失 | P2 |

---

## 六、优先级路线图

> 标注"已具备"的能力不再列入（详见第二节核实表）。

### P0（快速见效，1-2 周）
- ✅ B3 审稿输出结构化"优缺点+改进建议" + 审稿回复直接串联（2026-08-14 已落地）
- ✅ B2 引用验证升级为"外部实查"：CrossRef/OpenAlex DOI 与元数据核验 + 幻觉引用打标（2026-08-14 已落地，P0-1）
- ✅ H1（P0.5）审稿→修改→再审稿自动迭代闭环（review_loop 服务 + reviewer.score + writing.revise，2026-08-14 已落地）

### P1（核心竞争力，1-2 个月）
- 文献检索：A1 数据源扩展+向量重排序；A2 证据级引用；A5 上传文档 RAG；A7 迭代查询闭环；A10 来源级流式事件；A15 文献定时监控/周报；A18 OpenAlex 免费后备源
- 可信度：B1 对抗式事实审查；B5 红队审稿；B6 Rebuttal 方法学
- 综述闭环：A12 文献库→结构化综述管线；A14 系统综述工作流
- 写作：C1 报告定制（语气/字数/期刊预设）；C7 期刊规范合规检查；C8 AI 写作人性化改写
- 统计：D1 贝叶斯/潜变量方法扩展；D2 分析→Results 撰写一体化
- 架构：E1 模型网关抽象；E6 审计轨迹；E7 研究者画像；G1 本地模型对接（Ollama/自托管）

### P2（长期演进）
- 检索：A3 Agentic RAG、A4 arXiv 批处理、A6 检索粒度调节、A8 涟漪式扩展、A9 可复核导出、A11 Markdown 文献库、A13 自然语言查库、A16 看板阅读清单、A17 Zotero 对接
- 可信度：B4 公开基准质量门禁、B7 新颖性检测
- 写作：C3/C4 归档与 digest 沉淀、C5 Camera-ready、C6 汇报版 PPT
- 数据：D3 建模策略前置、D4 因果推断校验
- 架构：E3 声明式配置、E4 MCP 双向接入、E5 Agent 流程回归测试、E8 技能目录、E9 实验沙箱自愈
- 昇腾：G2 轻量向量存储兜底
- 自动化科研：H2 实验代码沙箱、H3 自动选题、H4 树搜索探索、H5 模板库、H6 轨迹审计、H7 Agent 评测套件

---

## 七、参考资料

- gpt-researcher：https://github.com/assafelovic/gpt-researcher
- paper-qa：https://github.com/Future-House/paper-qa
- ChatPaper：https://github.com/kaixindelele/ChatPaper
- AI-Scientist：https://github.com/SakanaAI/AI-Scientist ；v2：https://github.com/SakanaAI/AI-Scientist-v2
- paperseek：https://github.com/MingfengHong/paperseek
- ripple-reader：https://github.com/akiasprin/ripple-reader
- Perspicacite-AI：https://github.com/HolobiomicsLab/Perspicacite-AI
- awesome-llm-paper-wiki：https://github.com/moonlarry/awesome-llm-paper-wiki
- sisyphus-academica：https://github.com/argahv/sisyphus-academica
- research-workflow-assistant：https://github.com/Intersect-Collaborations-LLC/research-workflow-assistant
- research-paper-lifecycle-skills：https://github.com/ShaishavMaisuria/research-paper-lifecycle-skills
- ResearchClaw：https://github.com/AlphaLab-USTC/ResearchClaw
- research-plugins：https://github.com/wentorai/research-plugins
- open-scholar-skill：https://github.com/joshzyj/open-scholar-skill
- ResearchPilot-Skills：https://github.com/JosephElvisMaman1/ResearchPilot-Skills
- AcAgent：https://github.com/cang-zhu/AcAgent
- AutoResearchClaw（ResearchClaw 衍生）：https://github.com/aiming-lab/AutoResearchClaw
- paper-qa 论文：*Language agents achieve superhuman synthesis of scientific knowledge*（arXiv 2409.13740）
- AI-Scientist 论文：arXiv 2408.06292；v2：arXiv 2504.08066（ICLR 2025）

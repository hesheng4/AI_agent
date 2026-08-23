// 后端 API 类型定义 — 与 app/api/v1 各路由契约对齐

// ===== 认证 =====
export interface User {
  id: string;
  email: string;
  username: string;
  role: string;
  avatar?: string | null;
  bio?: string | null;
  institution?: string | null;
  api_key_configured: boolean;
  api_base_url?: string | null;
  api_model?: string | null;
  created_at?: string | null;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  username: string;
  password: string;
}

// ===== 文献检索 =====
export interface Paper {
  id?: string;
  paper_id?: string;
  title: string;
  authors?: string[];
  abstract?: string;
  year?: number;
  journal?: string;
  url?: string;
  source?: string;
  citation_count?: number;
  tags?: string[];
  category?: string;
  notes?: string;
  rating?: number;
  is_favorite?: number;
  created_at?: string;
}

export interface SearchRequest {
  query: string;
  filters?: Record<string, unknown>;
}

export interface SearchResponse {
  status: string;
  papers: Paper[];
  suggestions: string;
  total_results: number;
}

export interface ReadRequest {
  content: string;
}

export interface ReadResponse {
  status: string;
  analysis: string;
  key_points: string[];
}

// ===== 文献库 =====
export interface LibraryStats {
  total_papers: number;
  total_categories: number;
  total_tags: number;
  favorite_count: number;
  recent_papers: Array<{ id: string; title: string; year?: number }>;
  top_categories: Array<{ name: string; count: number }>;
  top_tags: Array<{ name: string; count: number }>;
}

export interface Category {
  id: string;
  name: string;
  description?: string | null;
  color: string;
  parent_id?: string | null;
  paper_count: number;
}

export interface Tag {
  id: string;
  name: string;
  color: string;
  usage_count: number;
}

export interface Citation {
  id: string;
  citing_paper_id: string;
  cited_paper_id: string;
  citing_title?: string | null;
  cited_title?: string | null;
  weight: number;
  source: string;
  created_at?: string | null;
}

export interface NetworkGraph {
  nodes: Array<Record<string, unknown>>;
  edges: Array<Record<string, unknown>>;
  metrics?: Record<string, unknown>;
}

// ===== 数据分析 =====
export interface AnalyzeRequest {
  data: Array<Record<string, unknown>>;
  analysis_type?: 'descriptive' | 'correlation' | 'outlier' | 'group';
  group_col?: string;
  value_col?: string;
}

export interface AnalyzeResponse {
  status: string;
  results: Record<string, unknown>;
  explanation: string;
  data_shape: number[];
  analysis_type: string;
}

// ===== 论文写作 =====
export interface OutlineRequest {
  topic: string;
  paper_type?: 'research' | 'methods' | 'hypothesis' | 'algorithmic' | 'review' | 'auto';
  journal?: 'standard' | 'nat-comms';
}

export interface OutlineResponse {
  status: string;
  template: Record<string, unknown>;
  optimized_outline: string;
  paper_type: string;
  core_chain: string;
  drafting_order: string[];
}

export interface PolishRequest {
  content: string;
  paper_type?: string;
}

export interface PolishResponse {
  status: string;
  original: string;
  polished: string;
  terminology_ledger?: Record<string, unknown> | null;
}

export interface CheckRequest {
  content: string;
}

export interface CheckResponse {
  status: string;
  issues: Array<{ type: string; message: string; position?: string }>;
  total_issues: number;
}

// ===== 实验设计 =====
export interface DesignRequest {
  research_goal: string;
  variables?: string[];
  design_type?: 'between' | 'within' | 'mixed' | 'factorial' | 'repeated';
}

export interface DesignResponse {
  status: string;
  plan: Record<string, unknown>;
  optimized_plan: string;
}

export interface PowerAnalysisRequest {
  effect_size: number;
  alpha?: number;
  power?: number;
}

export interface PowerAnalysisResponse {
  status: string;
  result: Record<string, unknown>;
}

// ===== 计费 =====
export interface UsageResponse {
  api_calls_used: number;
  tokens_used: number;
  plan: string;
}

// ===== 协调器 =====
export interface CapabilityMap {
  skills: Array<{ name: string; description: string; category: string }>;
}

export interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  steps: string[];
}

export interface RouteResponse {
  result: Record<string, unknown>;
}

// ===== 精读 =====
export interface ReadFullRequest {
  content: string;
  source_format?: 'auto' | 'pdf-text' | 'scanned-pdf' | 'html' | 'doi-arxiv' | 'pasted-text';
  journal?: 'nature' | 'nat-comms' | 'generic';
  language?: 'zh-to-en' | 'en';
}

export interface ReadFullResponse {
  paper_md: string;
  source_map: string;
  terminology_ledger: string;
  translation_notes: string;
  stats: Record<string, unknown>;
}

// ===== 审稿 =====
export interface AssessRequest {
  content: string;
  paper_type?: string;
  input_scope?: string;
}

export interface AssessResponse {
  status: string;
  fact_base: string;
  review_result: string;
  paper_type: string;
  input_scope: string;
  /** 结构化优点清单（B3） */
  strengths?: Array<Record<string, unknown>>;
  /** 结构化改进建议清单（B3，含 issue/location/suggestion/severity/category） */
  improvement_suggestions?: Array<Record<string, unknown>>;
}

export interface QuickCheckRequest {
  content: string;
  paper_type?: string;
}

export interface QuickCheckResponse {
  status: string;
  quick_check: string;
  paper_type: string;
}

// ===== 审稿回复 =====
export interface DraftResponseRequest {
  /** 审稿意见列表（与 review_result 二选一，后端默认空列表） */
  reviewer_comments?: string[];
  /** reviewer 结构化审稿结果（B3 串联），与 reviewer_comments 二选一，自动派生审稿意见 */
  review_result?: AssessResponse | null;
  decision_type?: 'minor' | 'major' | 'revise-and-resubmit';
  manuscript_content?: string;
  user_notes?: string;
}

export interface DraftResponseResult {
  status: string;
  classification: string;
  response_letter: string;
  decision_type: string;
  total_comments: number;
}

export interface AuditResponseRequest {
  response_content: string;
  reviewer_comments?: string[];
}

export interface AuditResponseResult {
  status: string;
  audit_result: string;
  total_comments: number;
}

export interface ReviseResponseRequest {
  response_content: string;
  feedback: string;
  reviewer_comments?: string[];
}

export interface ReviseResponseResult {
  status: string;
  revised_response: string;
  feedback_applied: string;
}

// ===== 审稿迭代闭环（H1）=====
export interface ReviewLoopRequest {
  /** 稿件内容 */
  content: string;
  paper_type?: string;
  /** 最大迭代轮数（1-10，默认 3） */
  max_rounds?: number;
  /** 达标分数阈值（0-10，默认 7.0） */
  target_score?: number;
}

export interface ReviewLoopRound {
  round: number;
  /** 本轮综合评分（0-10），无法评分时为 null */
  score: number | null;
  /** 各维度评分（novelty/quality/validity/clarity/impact 等） */
  axes: Record<string, number>;
  /** 本轮审稿意见条数 */
  suggestion_count: number;
  /** 本轮修订说明 */
  change_summary: string;
}

export interface ReviewLoopResponse {
  status: string;
  /** 最终稿件（迭代修订后） */
  final_content: string;
  total_rounds: number;
  converged: boolean;
  /** score_achieved | score_unavailable | no_suggestions | revise_no_change | max_rounds */
  stop_reason: string;
  target_score: number;
  max_rounds: number;
  rounds: ReviewLoopRound[];
}

// ===== 引用管理 =====
export interface AddCitationsRequest {
  content: string;
  journal_scope?: 'nature' | 'science' | 'cell' | 'general';
}

export interface AddCitationsResult {
  status: string;
  segments: string;
  claims: string;
  citations: string;
  annotated_text: string;
  journal_scope: string;
}

export interface VerifyCitationsRequest {
  content: string;
  references?: string[];
}

export interface VerifyCitationsResult {
  status: string;
  verification: string;
  total_references: number;
}

export interface FormatReferencesRequest {
  references: string[];
  style?: 'apa' | 'mla' | 'chicago' | 'ieee' | 'vancouver' | 'harvard' | 'gbt7714';
}

export interface FormatReferencesResult {
  status: string;
  formatted_references: string;
  style: string;
  total_references: number;
}

// ===== 导出 =====
export interface ExportRequest {
  data: Array<Record<string, unknown>>;
  filename?: string;
}

export interface PapersExportRequest {
  papers: Array<Record<string, unknown>>;
  filename?: string;
}

// ===== 图表合同 =====
export interface FigureContractRequest {
  conclusion: string;
  evidence_chain?: string[];
  archetype?: 'comparison' | 'distribution' | 'correlation' | 'time_series' | 'composition' | 'spatial' | 'network';
  journal?: 'nature' | 'nat-comms' | 'generic';
  backend?: 'python' | 'r';
}

export interface FigureContractResult {
  contract: Record<string, unknown>;
  style_guide: string;
  code_template: string;
}

export interface FigureQARequest {
  contract: Record<string, unknown>;
}

// ===== 论文转PPT =====
export interface Paper2PPTRequest {
  content: string;
  paper_type?: 'auto' | 'discovery' | 'methods' | 'resource' | 'clinical' | 'materials' | 'review';
}

export interface Paper2PPTResult {
  status: string;
  pptx_path: string;
  slide_count: number;
  slides: Array<{ title: string; content: string }>;
}

// ===== 论文转专利 =====
export interface PatentDraftRequest {
  content: string;
  task_mode?: 'full_draft' | 'claims_only' | 'audit';
  invention_type?: 'algorithm' | 'apparatus' | 'process' | 'mixed';
}

export interface PatentDraftResult {
  status: string;
  claims: string;
  specification: string;
  abstract: string;
}

// ===== Cover Letter =====
export interface CoverRequest {
  task?: 'draft' | 'audit' | 'shorten';
  content?: string;
  letter_type?: string;
  journal?: string;
}

// ===== Methods =====
export interface MethodsRequest {
  task?: 'audit' | 'draft' | 'check_ethics' | 'remove_vague';
  content?: string;
  study_type?: string;
  journal?: string;
}

// ===== Submission Package =====
export interface SubPkgRequest {
  task?: 'checklist' | 'match_journal' | 'consistency_check';
  abstract?: string;
  journal?: string;
  artefacts?: Record<string, unknown>;
}

// ===== Polishing =====
export interface PolishingRequest {
  task?: 'polish' | 'diagnose' | 'terminology' | 'latex_layout' | 'translate';
  content?: string;
  journal?: string;
}

// ===== Stats =====
export interface StatsRequest {
  task?: 'audit' | 'draft' | 'check_test' | 'check_multiple_comparison';
  content?: string;
  report_location?: string;
  journal?: string;
}

// ===== Data Availability =====
export interface GenerateStatementRequest {
  data_description: string;
  repository_type?: string;
  restrictions?: string;
  journal?: string;
}

export interface GenerateStatementResult {
  status: string;
  statement: string;
  journal: string;
  has_restrictions: boolean;
}

export interface AuditStatementRequest {
  statement: string;
}

export interface AuditStatementResult {
  status: string;
  audit_result: string;
  fair_compliance: string;
}

export interface SelectRepositoryRequest {
  data_type: string;
  data_size?: string;
  access_control?: 'open' | 'restricted';
}

export interface SelectRepositoryResult {
  status: string;
  recommendation: string;
  data_type: string;
  access_control: string;
}

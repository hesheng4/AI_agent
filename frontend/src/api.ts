// API 客户端 — 封装 fetch，自动携带 JWT，统一错误处理
import type {
  User, TokenResponse, LoginRequest, RegisterRequest,
  SearchRequest, SearchResponse, ReadRequest, ReadResponse,
  LibraryStats, Category, Tag, Paper, Citation, NetworkGraph,
  AnalyzeRequest, AnalyzeResponse,
  OutlineRequest, OutlineResponse, PolishRequest, PolishResponse,
  CheckRequest, CheckResponse,
  DesignRequest, DesignResponse, PowerAnalysisRequest, PowerAnalysisResponse,
  UsageResponse,
  RouteResponse,
  OrchestrateResponse,
  RunSummary,
  RunRecord,
  ResumeResponse,
  ReadFullRequest, ReadFullResponse,
  AssessRequest, AssessResponse, QuickCheckRequest, QuickCheckResponse,
  DraftResponseRequest, DraftResponseResult, AuditResponseRequest, AuditResponseResult,
  ReviseResponseRequest, ReviseResponseResult,
  ReviewLoopRequest, ReviewLoopResponse,
  AddCitationsRequest, AddCitationsResult, VerifyCitationsRequest, VerifyCitationsResult,
  FormatReferencesRequest, FormatReferencesResult,
  ExportRequest, PapersExportRequest,
  FigureContractRequest, FigureContractResult, FigureQARequest,
  Paper2PPTRequest, Paper2PPTResult,
  PatentDraftRequest, PatentDraftResult,
  CoverRequest, MethodsRequest, SubPkgRequest, PolishingRequest, StatsRequest,
  GenerateStatementRequest, GenerateStatementResult, AuditStatementRequest, AuditStatementResult,
  SelectRepositoryRequest, SelectRepositoryResult,
} from './types';

const API_BASE = '/api/v1';

// ===== Token 管理 — 内存优先 + sessionStorage 持久化 =====
const TOKEN_KEY = 'moguan_token';
const REFRESH_TOKEN_KEY = 'moguan_refresh_token';
let _tokenMemory: string | null = null;
let _refreshMemory: string | null = null;

export function getToken(): string | null {
  // 内存优先（防 XSS 读取）
  if (_tokenMemory) return _tokenMemory;
  // 降级到 sessionStorage（比 localStorage 安全，关标签页清除）
  try {
    const stored = sessionStorage.getItem(TOKEN_KEY);
    if (stored) {
      _tokenMemory = stored;
      return stored;
    }
  } catch {}
  return null;
}

export function setToken(token: string): void {
  _tokenMemory = token;
  try {
    sessionStorage.setItem(TOKEN_KEY, token);
  } catch {}
}

export function clearToken(): void {
  _tokenMemory = null;
  _refreshMemory = null;
  try {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(REFRESH_TOKEN_KEY);
  } catch {}
}

// Refresh token 管理（R16 S1 配套 — 长效令牌换取新 access token）
export function getRefreshToken(): string | null {
  if (_refreshMemory) return _refreshMemory;
  try {
    const stored = sessionStorage.getItem(REFRESH_TOKEN_KEY);
    if (stored) {
      _refreshMemory = stored;
      return stored;
    }
  } catch {}
  return null;
}

export function setRefreshToken(token: string): void {
  _refreshMemory = token;
  try {
    sessionStorage.setItem(REFRESH_TOKEN_KEY, token);
  } catch {}
}

// Token 过期检测（JWT payload 解码）
export function isTokenExpired(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    // 缺 exp 视为已过期（防伪造/异常 token 被当作永不过期）
    return payload.exp ? Date.now() >= payload.exp * 1000 : true;
  } catch {
    return true;
  }
}

// ===== 统一请求封装 =====
class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

// Token 过期 → 尝试 refresh，失败才清除
// single-flight：并发 401 时只发一次 /auth/refresh。
// 后端 refresh 每次轮换 refresh_token，若并发各自刷新，
// 后返回者会把先返回者刚发的 token 作废 → 用户被意外登出。
let _refreshInFlight: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  if (_refreshInFlight) return _refreshInFlight;
  _refreshInFlight = _doRefresh();
  try {
    return await _refreshInFlight;
  } finally {
    _refreshInFlight = null;
  }
}

async function _doRefresh(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) return null;
    const data: TokenResponse = await res.json();
    setToken(data.access_token);
    setRefreshToken(data.refresh_token);
    return data.access_token;
  } catch {
    return null;
  }
}

async function request<T>(
  path: string,
  options: RequestInit & { signal?: AbortSignal } = {},
): Promise<T> {
  const token = getToken();

  // Token 过期 → 先尝试 refresh，失败才清除并抛
  let activeToken = token;
  if (token && isTokenExpired(token)) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      activeToken = refreshed;
    } else {
      clearToken();
      throw new ApiError(401, '会话已过期，请重新登录');
    }
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string>) || {}),
  };
  if (activeToken) {
    headers['Authorization'] = `Bearer ${activeToken}`;
  }

  // FormData 不设置 Content-Type（浏览器自动设置 boundary）
  if (options.body instanceof FormData) {
    delete headers['Content-Type'];
  }

  const { signal, ...fetchOptions } = options;
  const res = await fetch(`${API_BASE}${path}`, { ...fetchOptions, headers, signal });

  // 401 → 尝试 refresh 后重试一次；仍失败才清除并抛
  if (res.status === 401) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      const retryHeaders = { ...headers, Authorization: `Bearer ${refreshed}` };
      const retryRes = await fetch(`${API_BASE}${path}`, { ...fetchOptions, headers: retryHeaders, signal });
      if (retryRes.status !== 401) {
        // 复用下方统一处理（重试成功或非 401 错误）
        return handleResponse<T>(retryRes);
      }
    }
    clearToken();
    throw new ApiError(401, '未授权，请重新登录');
  }

  return handleResponse<T>(res);
}

// 响应处理（从 request 抽出，供 401 重试复用）
async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `请求失败 (${res.status})`;
    try {
      const err = await res.json();
      if (Array.isArray(err.detail)) {
        // Pydantic 验证错误: [{loc, msg, type}, ...] → 拼接 msg
        detail = err.detail.map((e: { msg?: string }) => e.msg || String(e)).join('; ');
      } else {
        detail = err.detail || err.message || detail;
      }
    } catch {
      // 非 JSON 错误响应
    }
    throw new ApiError(res.status, detail);
  }

  // 二进制响应（导出文件）
  if (res.headers.get('content-type')?.includes('application/octet-stream')
      || res.headers.get('content-disposition')?.includes('attachment')) {
    return res.blob() as unknown as T;
  }

  return res.json() as Promise<T>;
}

// ===== 认证 API =====
export const authApi = {
  login: (data: LoginRequest) =>
    request<TokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  register: (data: RegisterRequest) =>
    request<User>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  forgotPassword: (email: string) =>
    request<{ message: string; token?: string; expires_in?: number }>('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),
  resetPassword: (token: string, new_password: string) =>
    request<{ message: string }>('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, new_password }),
    }),
  me: () => request<User>('/auth/me'),
  // 更新个人资料与自定义 API 配置
  // 注意：api_key 仅在此处发送到后端，不存于 User 类型中（安全考虑）
  updateProfile: (data: Partial<Pick<User, 'username' | 'bio' | 'institution' | 'avatar' | 'api_key_configured' | 'api_base_url' | 'api_model'>> & { api_key?: string }) =>
    request<User>('/auth/me', {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  // 修改密码（需旧密码校验 + 新密码复杂度）
  changePassword: (data: { old_password: string; new_password: string }) =>
    request<{ message: string }>('/auth/password', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  // 测试自定义 API 配置连通性（后端走 SSRF 防护校验）
  testApiConfig: (data: { api_key?: string; api_base_url?: string; api_model?: string }) =>
    request<{ success: boolean; message: string; model?: string; response_preview?: string }>(
      '/auth/test-api-config',
      { method: 'POST', body: JSON.stringify(data) },
    ),
};

// ===== 文献检索 API =====
export const literatureApi = {
  search: (data: SearchRequest) =>
    request<SearchResponse>('/literature/search', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  read: (data: ReadRequest) =>
    request<ReadResponse>('/literature/read', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  summarize: (data: { content: string; max_length?: number }) =>
    request<{ status: string; summary: string }>('/literature/summarize', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  citations: (paperId: string) =>
    request<{ status: string; citations: unknown[] }>(`/literature/citations/${encodeURIComponent(paperId)}`),
  references: (paperId: string) =>
    request<{ status: string; references: unknown[] }>(`/literature/references/${encodeURIComponent(paperId)}`),
  citationNetwork: (paperId: string, depth = 2) =>
    request<NetworkGraph>(`/literature/citation-network/${encodeURIComponent(paperId)}?depth=${depth}`),
  citationTrend: (paperId: string) =>
    request<{ status: string; trend: unknown }>(`/literature/citation-trend/${encodeURIComponent(paperId)}`),
  citationGraph: (data: { paper_id: string; depth?: number }) =>
    request<NetworkGraph>('/literature/citation-graph', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  coCitation: (data: { paper_id: string }) =>
    request<{ status: string; co_citations: unknown[] }>('/literature/co-citation', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  bibliographicCoupling: (data: { paper_id: string }) =>
    request<{ status: string }>('/literature/bibliographic-coupling', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  knowledgeDiffusion: (data: { paper_id: string }) =>
    request<{ status: string }>('/literature/knowledge-diffusion', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  researchFrontier: (data: { topic: string }) =>
    request<{ status: string }>('/literature/research-frontier', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  influentialPapers: (data: { top_k?: number }) =>
    request<{ status: string; influential_papers: unknown[] }>('/literature/influential-papers', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ===== 文献库 API =====
export const libraryApi = {
  // 文献
  listPapers: (params?: { category?: string; tag?: string; favorite?: number; search?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null) q.set(k, String(v));
      });
    }
    return request<Paper[]>(`/library/papers${q.toString() ? `?${q}` : ''}`);
  },
  getPaper: (paperId: string) => request<Paper>(`/library/papers/${paperId}`),
  addPaper: (data: Partial<Paper> & { paper_id: string; title: string }) =>
    request<Paper>('/library/papers', { method: 'POST', body: JSON.stringify(data) }),
  updatePaper: (paperId: string, data: Partial<Paper>) =>
    request<Paper>(`/library/papers/${paperId}`, { method: 'PUT', body: JSON.stringify(data) }),
  deletePaper: (paperId: string) =>
    request<{ status: string }>(`/library/papers/${paperId}`, { method: 'DELETE' }),

  // 分类
  listCategories: () => request<Category[]>('/library/categories'),
  createCategory: (data: { name: string; description?: string; color?: string }) =>
    request<Category>('/library/categories', { method: 'POST', body: JSON.stringify(data) }),
  deleteCategory: (id: string) =>
    request<{ status: string }>(`/library/categories/${id}`, { method: 'DELETE' }),

  // 标签
  listTags: () => request<Tag[]>('/library/tags'),
  createTag: (data: { name: string; color?: string }) =>
    request<Tag>('/library/tags', { method: 'POST', body: JSON.stringify(data) }),
  deleteTag: (id: string) =>
    request<{ status: string }>(`/library/tags/${id}`, { method: 'DELETE' }),

  // 统计
  stats: () => request<LibraryStats>('/library/stats'),

  // 引用关系
  listCitations: (params?: { paper_id?: string; direction?: string }) => {
    const q = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v) q.set(k, String(v));
      });
    }
    return request<Citation[]>(`/library/citations${q.toString() ? `?${q}` : ''}`);
  },
  addCitation: (data: { citing_paper_id: string; cited_paper_id: string; citing_title?: string; cited_title?: string }) =>
    request<Citation>('/library/citations', { method: 'POST', body: JSON.stringify(data) }),
  deleteCitation: (id: string) =>
    request<{ status: string }>(`/library/citations/${id}`, { method: 'DELETE' }),

  // 引用网络分析
  getGraph: (paperId: string, depth = 2) =>
    request<NetworkGraph>('/library/citations/network/graph', {
      method: 'POST',
      body: JSON.stringify({ paper_id: paperId, depth }),
    }),
  coCitation: (min_co_citations = 1, top_k = 50) =>
    request<unknown>('/library/citations/network/co-citation', {
      method: 'POST',
      body: JSON.stringify({ min_co_citations, top_k }),
    }),
  influentialPapers: (top_k = 10) =>
    request<{ influential_papers: unknown[] }>('/library/citations/network/influential', {
      method: 'POST',
      body: JSON.stringify({ top_k }),
    }),
};

// ===== 数据分析 API =====
export const dataApi = {
  analyze: (data: AnalyzeRequest) =>
    request<AnalyzeResponse>('/data/analyze', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  visualize: (data: { data: unknown[]; chart_type?: string; x_col?: string; y_col?: string }) =>
    request<{ status: string; chart_url: string; chart_data: unknown }>('/data/visualize', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  upload: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return request<{ status: string; data: unknown[]; filename: string }>('/data/upload', {
      method: 'POST',
      body: formData,
      headers: {},
    });
  },
};

// ===== 写作 API =====
export const writingApi = {
  outline: (data: OutlineRequest) =>
    request<OutlineResponse>('/writing/outline', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  generate: (data: {
    outline: Record<string, unknown>;
    section?: string;
    paper_type?: string;
    terminology_ledger?: Record<string, unknown>;
  }) =>
    request<{ status: string; section?: string; content: string; paper_type?: string }>(
      '/writing/generate',
      { method: 'POST', body: JSON.stringify(data) },
    ),
  polish: (data: PolishRequest) =>
    request<PolishResponse>('/writing/polish', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  check: (data: CheckRequest) =>
    request<CheckResponse>('/writing/check', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  wordCount: (data: { content: string }) =>
    request<{ status: string; word_count: number; char_count: number }>('/writing/word-count', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  structure: (data: { content: string }) =>
    request<{ status: string; structure: unknown }>('/writing/structure', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  terminology: (data: { content: string; domain?: string }) =>
    request<{ status: string; terminology: unknown[] }>('/writing/terminology', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  evidence: (data: { content: string }) =>
    request<{ status: string; evidence: unknown[] }>('/writing/evidence', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  detectType: (data: { content: string }) =>
    request<{ status: string; paper_type: string; confidence: number }>('/writing/detect-type', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  latexExport: (data: { content: string; template?: string }) =>
    request<Blob>('/writing/export-latex', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ===== 实验设计 API =====
export const experimentApi = {
  design: (data: DesignRequest) =>
    request<DesignResponse>('/experiment/design', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  powerAnalysis: (data: PowerAnalysisRequest) =>
    request<PowerAnalysisResponse>('/experiment/power-analysis', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  optimize: (data: { design: unknown; constraints?: unknown }) =>
    request<{ status: string; optimized: unknown }>('/experiment/optimize', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  predict: (data: { design: unknown; parameters?: unknown }) =>
    request<{ status: string; prediction: unknown }>('/experiment/predict', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  statisticalTest: (data: { data: unknown[]; test_type?: string; groups?: string[] }) =>
    request<{ status: string; result: unknown }>('/experiment/statistical-test', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ===== 计费 API =====
export const billingApi = {
  usage: () => request<UsageResponse>('/billing/usage'),
};

// ===== 昇腾 NPU 适配 =====
export const ascendApi = {
  info: () => request<Record<string, unknown>>('/ascend/info'),
  vllmHealth: () => request<{ healthy: boolean; url: string; error?: string }>('/ascend/vllm-health'),
  warmup: () => request<Record<string, unknown>>('/ascend/warmup', { method: 'POST' }),
  switchMode: (llm_mode: 'remote' | 'ascend') =>
    request<Record<string, unknown>>('/ascend/mode', { method: 'PUT', body: JSON.stringify({ llm_mode }) }),
};

// ===== 精度对齐 =====
export const alignmentApi = {
  status: () => request<{ running: boolean; last_result: unknown; error: string | null }>('/alignment/status'),
  run: (data: Record<string, unknown>) =>
    request<{ message: string; baseline_source: string }>('/alignment/run', { method: 'POST', body: JSON.stringify(data) }),
  report: () => request<Record<string, unknown>>('/alignment/report'),
  thresholds: () => request<Record<string, unknown>>('/alignment/thresholds'),
  constraints: () => request<Record<string, unknown>>('/alignment/constraints'),
};

// ===== 性能采集 =====
export const profilingApi = {
  status: () => request<Record<string, unknown>>('/profiling/status'),
  levels: () => request<Record<string, unknown>>('/profiling/levels'),
  generate: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>('/profiling/generate', { method: 'POST', body: JSON.stringify(data) }),
  run: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>('/profiling/run', { method: 'POST', body: JSON.stringify(data) }),
  taskStatus: () => request<Record<string, unknown>>('/profiling/task-status'),
  stop: () => request<Record<string, unknown>>('/profiling/stop', { method: 'POST' }),
  results: (output_dir = './profiling_output') =>
    request<{ count: number; output_dir: string; results: unknown[] }>(`/profiling/results?output_dir=${encodeURIComponent(output_dir)}`),
  checklist: () => request<Record<string, unknown>>('/profiling/checklist'),
  envCheck: () => request<Record<string, unknown>>('/profiling/env-check'),
  generateDeepspeed: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>('/profiling/generate-deepspeed', { method: 'POST', body: JSON.stringify(data) }),
};

// ===== 性能调优 =====
export const perfTuningApi = {
  status: () => request<Record<string, unknown>>('/perf-tuning/status'),
  recommendedConfigs: () => request<Record<string, unknown>>('/perf-tuning/recommended-configs'),
  apply: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>('/perf-tuning/apply', { method: 'POST', body: JSON.stringify(data) }),
  launchCommand: (data: Record<string, unknown>) =>
    request<{ command: string; config: Record<string, unknown> }>('/perf-tuning/launch-command', { method: 'POST', body: JSON.stringify(data) }),
  detectTcmalloc: () => request<Record<string, unknown>>('/perf-tuning/detect-tcmalloc'),
  detectNuma: () => request<Record<string, unknown>>('/perf-tuning/detect-numa'),
  quickReference: () => request<Record<string, unknown>>('/perf-tuning/quick-reference'),
  verifyEnv: () => request<Record<string, unknown>>('/perf-tuning/verify-env'),
  analyzeScript: (script: string) =>
    request<Record<string, unknown>>('/perf-tuning/analyze-script', { method: 'POST', body: JSON.stringify({ script }) }),
  diagnoseBottleneck: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>('/perf-tuning/diagnose-bottleneck', { method: 'POST', body: JSON.stringify(data) }),
  suggestCodeOptimizations: (model_code = '') =>
    request<Record<string, unknown>>('/perf-tuning/suggest-code-optimizations', { method: 'POST', body: JSON.stringify({ model_code }) }),
};

// ===== 工具链 =====
export const toolchainApi = {
  status: () => request<Record<string, unknown>>('/toolchain/status'),
  hardwareCheck: () => request<Record<string, unknown>>('/toolchain/hardware-check'),
  envSetup: (device_ids = '0,1,2,3') =>
    request<Record<string, unknown>>(`/toolchain/env-setup?device_ids=${encodeURIComponent(device_ids)}`),
  verifyEnvironment: () => request<Record<string, unknown>>('/toolchain/verify-environment'),
  vllmInstallGuide: () => request<Record<string, unknown>>('/toolchain/vllm-install-guide'),
  vllmLaunch: (data: Record<string, unknown>) =>
    request<{ command: string; config: Record<string, unknown>; notes: string[] }>('/toolchain/vllm-launch', { method: 'POST', body: JSON.stringify(data) }),
  vllmDiagnose: (error_output: string) =>
    request<{ diagnoses: unknown[]; error_output_preview: string }>('/toolchain/vllm-diagnose', { method: 'POST', body: JSON.stringify({ error_output }) }),
  quantize: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>('/toolchain/quantize', { method: 'POST', body: JSON.stringify(data) }),
  aisbench: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>('/toolchain/aisbench', { method: 'POST', body: JSON.stringify(data) }),
  quickReference: () => request<Record<string, unknown>>('/toolchain/quick-reference'),
};

// ===== 模型验证 =====
export const validatorApi = {
  status: () => request<Record<string, unknown>>('/validator/status'),
  envCheck: () => request<Record<string, unknown>>('/validator/env-check'),
  deployCommand: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>('/validator/deploy-command', { method: 'POST', body: JSON.stringify(data) }),
  accuracy: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>('/validator/accuracy', { method: 'POST', body: JSON.stringify(data) }),
  benchmarkServe: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>('/validator/benchmark/serve', { method: 'POST', body: JSON.stringify(data) }),
  benchmarkLatency: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>('/validator/benchmark/latency', { method: 'POST', body: JSON.stringify(data) }),
  benchmarkThroughput: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>('/validator/benchmark/throughput', { method: 'POST', body: JSON.stringify(data) }),
  run: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>('/validator/run', { method: 'POST', body: JSON.stringify(data) }),
  models: () => request<{ models: unknown[]; presets: Record<string, unknown> }>('/validator/models'),
  quickReference: () => request<Record<string, unknown>>('/validator/quick-reference'),
};

// ===== 调试辅助 =====
export const debuggingApi = {
  status: () => request<Record<string, unknown>>('/debugging/status'),
  sessions: () => request<{ sessions: unknown[]; total: number }>('/debugging/sessions'),
  createSession: (title = '') =>
    request<Record<string, unknown>>('/debugging/sessions', { method: 'POST', body: JSON.stringify({ title }) }),
  getSession: (id: string) => request<Record<string, unknown>>(`/debugging/sessions/${id}`),
  quickDiagnose: (error_text: string) =>
    request<Record<string, unknown>>('/debugging/quick-diagnose', { method: 'POST', body: JSON.stringify({ error_text }) }),
  report: (id: string) => request<Record<string, unknown>>(`/debugging/report/${id}`),
  redFlags: (id: string) => request<Record<string, unknown>>(`/debugging/red-flags/${id}`),
  quickReference: () => request<Record<string, unknown>>('/debugging/quick-reference'),
};

// ===== 历史转技能 =====
export const historyToSkillApi = {
  status: () => request<Record<string, unknown>>('/history-to-skill/status'),
  variants: (model_name: string) =>
    request<Record<string, unknown>>(`/history-to-skill/variants/${encodeURIComponent(model_name)}`),
  roots: (sources?: string) =>
    request<Record<string, unknown>>(`/history-to-skill/roots${sources ? `?sources=${encodeURIComponent(sources)}` : ''}`),
  search: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>('/history-to-skill/search', { method: 'POST', body: JSON.stringify(data) }),
  generate: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>('/history-to-skill/generate', { method: 'POST', body: JSON.stringify(data) }),
  run: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>('/history-to-skill/run', { method: 'POST', body: JSON.stringify(data) }),
  validate: (skill_dir: string) =>
    request<Record<string, unknown>>('/history-to-skill/validate', { method: 'POST', body: JSON.stringify({ skill_dir }) }),
  quickReference: () => request<Record<string, unknown>>('/history-to-skill/quick-reference'),
};

// ===== 模型适配 =====
export const adaptationApi = {
  status: () => request<Record<string, unknown>>('/adaptation/status'),
  createSession: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>('/adaptation/sessions', { method: 'POST', body: JSON.stringify(data) }),
  listSessions: () => request<Record<string, unknown>>('/adaptation/sessions'),
  getSession: (id: string) => request<Record<string, unknown>>(`/adaptation/sessions/${id}`),
  step2: (id: string, data: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/adaptation/sessions/${id}/step2`, { method: 'POST', body: JSON.stringify(data) }),
  step3: (id: string, data: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/adaptation/sessions/${id}/step3`, { method: 'POST', body: JSON.stringify(data) }),
  step4: (id: string, data: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/adaptation/sessions/${id}/step4`, { method: 'POST', body: JSON.stringify(data) }),
  step5: (id: string) =>
    request<Record<string, unknown>>(`/adaptation/sessions/${id}/step5`, { method: 'POST' }),
  step6: (id: string, data: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/adaptation/sessions/${id}/step6`, { method: 'POST', body: JSON.stringify(data) }),
  step7Dummy: (id: string, data: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/adaptation/sessions/${id}/step7-dummy`, { method: 'POST', body: JSON.stringify(data) }),
  step7Real: (id: string, data: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/adaptation/sessions/${id}/step7-real`, { method: 'POST', body: JSON.stringify(data) }),
  step8: (id: string, data: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/adaptation/sessions/${id}/step8`, { method: 'POST', body: JSON.stringify(data) }),
  step9: (id: string) =>
    request<Record<string, unknown>>(`/adaptation/sessions/${id}/step9`, { method: 'POST' }),
  step10: (id: string) =>
    request<Record<string, unknown>>(`/adaptation/sessions/${id}/step10`, { method: 'POST' }),
  quickReference: () => request<Record<string, unknown>>('/adaptation/quick-reference'),
};

// ===== 协调器 API =====
export const coordinatorApi = {
  capabilityMap: () => request<RouteResponse>('/coordinator/capability-map'),
  workflowTemplates: () => request<RouteResponse>('/coordinator/workflow-templates'),
  route: (task: string, content = '') =>
    request<RouteResponse>('/coordinator/route', {
      method: 'POST',
      body: JSON.stringify({ task, content }),
    }),
  /** 多 Agent 编排（完整 process()）。task_id 传入则事件发布到该 id，
   *  供调用方先建立 /ws/tasks/{task_id} 连接再发起请求。
   *  saveArtifact=true 时编排结果持久化为产出物（结果存档页可回看）。 */
  orchestrate: (task: string, content = '', taskId?: string, saveArtifact = false) =>
    request<OrchestrateResponse>('/coordinator/orchestrate', {
      method: 'POST',
      body: JSON.stringify({
        task,
        content,
        ...(taskId ? { task_id: taskId } : {}),
        ...(saveArtifact ? { save_artifact: true } : {}),
      }),
    }),
};

// ===== 运行记录 API（E6 工作流恢复）=====
export const runsApi = {
  list: () => request<{ runs: RunSummary[] }>('/coordinator/runs'),
  detail: (runId: string) => request<RunRecord>(`/coordinator/runs/${runId}`),
  /** 从失败步恢复：跳过已完成步，重执行 failed/pending 及其传递下游 */
  resume: (runId: string) =>
    request<ResumeResponse>(`/coordinator/runs/${runId}/resume`, { method: 'POST' }),
};

// ===== 精读 API =====
export const readerApi = {
  readFull: (data: ReadFullRequest) =>
    request<ReadFullResponse>('/reader/read-full', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ===== 审稿 API =====
export const reviewerApi = {
  assess: (data: AssessRequest) =>
    request<AssessResponse>('/reviewer/assess', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  quickCheck: (data: QuickCheckRequest) =>
    request<QuickCheckResponse>('/reviewer/quick-check', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ===== 审稿回复 API =====
export const responseApi = {
  draft: (data: DraftResponseRequest) =>
    request<DraftResponseResult>('/response/draft', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  audit: (data: AuditResponseRequest) =>
    request<AuditResponseResult>('/response/audit', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  revise: (data: ReviseResponseRequest) =>
    request<ReviseResponseResult>('/response/revise', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ===== 审稿迭代闭环 API（H1）=====
export const reviewLoopApi = {
  run: (data: ReviewLoopRequest) =>
    request<ReviewLoopResponse>('/review-loop/run', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ===== 引用管理 API =====
export const citationApi = {
  add: (data: AddCitationsRequest) =>
    request<AddCitationsResult>('/citation/add', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  verify: (data: VerifyCitationsRequest) =>
    request<VerifyCitationsResult>('/citation/verify', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  formatReferences: (data: FormatReferencesRequest) =>
    request<FormatReferencesResult>('/citation/format', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ===== 导出 API =====
export const exportApi = {
  csv: (data: ExportRequest) =>
    request<Blob>('/export/csv', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  json: (data: ExportRequest) =>
    request<Blob>('/export/json', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  bibtex: (data: PapersExportRequest) =>
    request<Blob>('/export/bibtex', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  ris: (data: PapersExportRequest) =>
    request<Blob>('/export/ris', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  markdown: (data: ExportRequest) =>
    request<Blob>('/export/markdown', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ===== 图表合同 API =====
export const figureApi = {
  createContract: (data: FigureContractRequest) =>
    request<FigureContractResult>('/figure/contract', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  applyStyle: (journal = 'generic') =>
    request<{ style: string; config: unknown }>('/figure/apply-style', {
      method: 'POST',
      body: JSON.stringify({ journal }),
    }),
  qaCheck: (data: FigureQARequest) =>
    request<{ status: string; issues: string[] }>('/figure/qa', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ===== 论文转PPT API =====
export const paper2pptApi = {
  generate: (data: Paper2PPTRequest) =>
    request<Paper2PPTResult>('/paper2ppt/generate', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ===== 论文转专利 API =====
export const paperToPatentApi = {
  draft: (data: PatentDraftRequest) =>
    request<PatentDraftResult>('/paper-to-patent/draft', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ===== Cover Letter API =====
export const coverApi = {
  process: (data: CoverRequest) =>
    request<{ result: Record<string, unknown> }>('/cover/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ===== Methods API =====
export const methodsApi = {
  process: (data: MethodsRequest) =>
    request<{ result: Record<string, unknown> }>('/methods/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ===== Submission Package API =====
export const submissionPackageApi = {
  process: (data: SubPkgRequest) =>
    request<{ result: Record<string, unknown> }>('/submission-package/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ===== Polishing API =====
export const polishingApi = {
  process: (data: PolishingRequest) =>
    request<{ result: Record<string, unknown> }>('/polishing/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ===== Stats API =====
export const statsApi = {
  process: (data: StatsRequest) =>
    request<{ result: Record<string, unknown> }>('/stats/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ===== Data Availability API =====
export const dataAvailabilityApi = {
  generateStatement: (data: GenerateStatementRequest) =>
    request<GenerateStatementResult>('/data-availability/generate-statement', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  auditStatement: (data: AuditStatementRequest) =>
    request<AuditStatementResult>('/data-availability/audit-statement', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  selectRepository: (data: SelectRepositoryRequest) =>
    request<SelectRepositoryResult>('/data-availability/select-repository', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ===== Agent 生成器 API =====
export const agentGeneratorApi = {
  generate: (data: { description: string; name_hint?: string }) =>
    request<Record<string, unknown>>('/agents/generate', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  confirm: (data: { session_id: string }) =>
    request<Record<string, unknown>>('/agents/confirm', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ===== 工作流编排 API (E5) =====
export const workflowsApi = {
  list: () => request<{ workflows: Record<string, unknown>[] }>('/workflows/'),
  get: (id: string) => request<Record<string, unknown>>(`/workflows/${id}`),
  create: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>('/workflows/', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/workflows/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string) =>
    request<{ status: string }>(`/workflows/${id}`, { method: 'DELETE' }),
  run: (id: string) =>
    request<Record<string, unknown>>(`/workflows/${id}/run`, { method: 'POST' }),
};

export { ApiError };

// ===== 产出物 API（结果持久化）=====
export interface Artifact {
  id: string;
  agent: string;
  title: string;
  payload: Record<string, unknown>;
  created_at: string | null;
}

export const artifactsApi = {
  create: (data: { agent: string; title: string; payload: Record<string, unknown> }) =>
    request<Artifact>('/artifacts/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  list: (params?: { agent?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.agent) qs.set('agent', params.agent);
    if (params?.limit) qs.set('limit', String(params.limit));
    if (params?.offset) qs.set('offset', String(params.offset));
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    return request<Artifact[]>(`/artifacts/${suffix}`);
  },
  get: (id: string) => request<Artifact>(`/artifacts/${id}`),
  delete: (id: string) => request<{ status: string }>(`/artifacts/${id}`, { method: 'DELETE' }),
};

// ===== 分享与 fork API =====
export interface ShareItem {
  id: string;
  resource_type: string;
  resource_id: string;
  expires_at: string | null;
  revoked: boolean;
  created_at: string | null;
}

export interface ShareCreateResult extends ShareItem {
  token: string;
}

export interface SharedLibraryPreview {
  resource_type: string;
  owner: string;
  paper_count: number;
  papers: Array<{ title: string; year: number | null; journal: string | null; tags: string[]; category: string | null }>;
  categories: string[];
  tags: string[];
  citation_count: number;
}

export interface ForkResult {
  papers_added: number;
  papers_skipped: number;
  categories_created: number;
  tags_created: number;
  notes_copied: number;
  citations_copied: number;
  citations_skipped: number;
}

export const sharesApi = {
  create: (data: { resource_type: string; resource_id?: string; ttl_days?: number | null }) =>
    request<ShareCreateResult>('/shares/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  list: () => request<ShareItem[]>('/shares/'),
  revoke: (id: string) => request<{ status: string }>(`/shares/${id}`, { method: 'DELETE' }),
  preview: (token: string) => request<SharedLibraryPreview>(`/shares/by-token/${token}`),
  fork: (token: string) => request<ForkResult>(`/shares/by-token/${token}/fork`, { method: 'POST' }),
};

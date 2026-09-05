// 协调器页 — 能力地图 · 工作流模板 · 智能路由 · 多 Agent 编排 · 运行记录
import { useState, useEffect, useRef, type FormEvent } from 'react';
import { motion } from 'motion/react';
import { useNavigate } from 'react-router-dom';
import { PageHeader, Button, Card, Input, Loading, EmptyState, ErrorBanner } from '../components/ui';
import { coordinatorApi, runsApi } from '../api';
import { useTaskStream } from '../hooks/useTaskStream';
import type { OrchestrateResponse, RunSummary, RunRecord } from '../types';

type TabKey = 'route' | 'capabilities' | 'workflows' | 'orchestrate' | 'runs';

const ROUTE_SUGGESTIONS = [
  { label: '文献检索', task: '搜索关于大语言模型的最新论文', icon: 'fa-search' },
  { label: '论文写作', task: '帮我写一篇关于深度学习的论文大纲', icon: 'fa-pen-fancy' },
  { label: '审稿评估', task: '模拟 Nature 审稿人评估我的稿件', icon: 'fa-user-check' },
  { label: '引用添加', task: '为我的论文段落添加 Nature 系列引用', icon: 'fa-quote-right' },
  { label: '实验设计', task: '设计一个关于药物疗效的随机对照实验', icon: 'fa-flask' },
  { label: '模型适配', task: '将 LLaMA 适配到昇腾 NPU', icon: 'fa-microchip' },
];

// 路由目标映射
const ROUTE_TARGETS: Record<string, string> = {
  literature: '/app/literature',
  library: '/app/library',
  writing: '/app/writing',
  reviewer: '/app/reviewer',
  citation: '/app/citation',
  experiment: '/app/experiment',
  data: '/app/data',
  reader: '/app/reader',
  response: '/app/response',
  export: '/app/library',
};

export default function Coordinator() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<TabKey>('route');

  // 路由 tab
  const [taskInput, setTaskInput] = useState('');
  const [routeResult, setRouteResult] = useState<Record<string, unknown> | null>(null);
  const [routeLoading, setRouteLoading] = useState(false);
  const [routeError, setRouteError] = useState('');

  // 能力地图 tab
  const [capabilities, setCapabilities] = useState<Array<{ name: string; description: string; category: string }>>([]);
  const [capsLoading, setCapsLoading] = useState(false);
  const [capsError, setCapsError] = useState('');

  // 工作流 tab
  const [workflows, setWorkflows] = useState<Array<{ id: string; name: string; description: string; steps: string[] }>>([]);
  const [wfLoading, setWfLoading] = useState(false);
  const [wfError, setWfError] = useState('');

  // 运行记录 tab（E6 恢复）
  const [runsList, setRunsList] = useState<RunSummary[]>([]);
  const [runsLoading, setRunsLoading] = useState(false);
  const [runsError, setRunsError] = useState('');
  const [runDetail, setRunDetail] = useState<RunRecord | null>(null);
  const [resumingRunId, setResumingRunId] = useState<string | null>(null);
  const [resumeNotice, setResumeNotice] = useState('');

  // 编排 tab — 先连 WS（/ws/tasks/{taskId}）再发编排请求，避免错过 start/planned 事件
  const [orchInput, setOrchInput] = useState('');
  const [orchTaskId, setOrchTaskId] = useState<string | null>(null);
  const [orchResult, setOrchResult] = useState<OrchestrateResponse | null>(null);
  const [orchLoading, setOrchLoading] = useState(false);
  const [orchError, setOrchError] = useState('');
  const [orchWsReady, setOrchWsReady] = useState(false);
  const orchPending = useRef<{ task: string; gen: number } | null>(null);
  const orchGen = useRef(0);

  const orchStream = useTaskStream(orchTaskId, !!orchTaskId, () => {
    setOrchWsReady(true);
    const p = orchPending.current;
    if (p && p.gen === orchGen.current && orchTaskId) {
      orchPending.current = null;
      void runOrchestrate(p.task, orchTaskId);
    }
  });

  async function runOrchestrate(task: string, taskId: string) {
    try {
      const res = await coordinatorApi.orchestrate(task, '', taskId);
      setOrchResult(res);
    } catch (err) {
      setOrchError(err instanceof Error ? err.message : '编排失败');
    } finally {
      setOrchLoading(false);
    }
  }

  function handleOrchestrate(e: FormEvent) {
    e.preventDefault();
    const task = orchInput.trim();
    if (!task) return;
    setOrchError('');
    setOrchResult(null);
    setOrchLoading(true);
    setOrchWsReady(false);
    orchGen.current += 1;
    const gen = orchGen.current;
    const taskId = crypto.randomUUID();
    orchPending.current = { task, gen };
    setOrchTaskId(taskId);
    // 兜底：WS 800ms 内未建立（如 token 缺失）则直接发请求，避免卡死
    setTimeout(() => {
      const p = orchPending.current;
      if (p && p.gen === gen) {
        orchPending.current = null;
        void runOrchestrate(p.task, taskId);
      }
    }, 800);
  }

  useEffect(() => {
    if (tab === 'capabilities' && capabilities.length === 0) loadCapabilities();
    if (tab === 'workflows' && workflows.length === 0) loadWorkflows();
    if (tab === 'runs') loadRuns();
  }, [tab]);

  async function handleRoute(e: FormEvent) {
    e.preventDefault();
    if (!taskInput.trim()) return;
    setRouteLoading(true);
    setRouteError('');
    setRouteResult(null);
    try {
      const res = await coordinatorApi.route(taskInput.trim());
      setRouteResult(res.result);
    } catch (err) {
      setRouteError(err instanceof Error ? err.message : '路由失败');
    } finally {
      setRouteLoading(false);
    }
  }

  async function loadCapabilities() {
    setCapsLoading(true);
    setCapsError('');
    try {
      const res = await coordinatorApi.capabilityMap();
      const skills = (res.result?.skills as Array<{ name: string; description: string; category: string }>) || [];
      setCapabilities(skills);
    } catch (err) {
      setCapsError(err instanceof Error ? err.message : '加载能力地图失败');
    } finally {
      setCapsLoading(false);
    }
  }

  async function loadWorkflows() {
    setWfLoading(true);
    setWfError('');
    try {
      const res = await coordinatorApi.workflowTemplates();
      const templates = (res.result?.templates as Array<{ id: string; name: string; description: string; steps: string[] }>) || [];
      setWorkflows(templates);
    } catch (err) {
      setWfError(err instanceof Error ? err.message : '加载工作流模板失败');
    } finally {
      setWfLoading(false);
    }
  }

  function handleSuggestionClick(task: string) {
    setTaskInput(task);
  }

  // ── 运行记录（E6 恢复）──
  async function loadRuns() {
    setRunsLoading(true);
    setRunsError('');
    try {
      const res = await runsApi.list();
      setRunsList(res.runs);
    } catch (err) {
      setRunsError(err instanceof Error ? err.message : '加载运行记录失败');
    } finally {
      setRunsLoading(false);
    }
  }

  async function toggleRunDetail(runId: string) {
    if (runDetail?.run_id === runId) {
      setRunDetail(null);
      return;
    }
    try {
      const record = await runsApi.detail(runId);
      setRunDetail(record);
    } catch (err) {
      setRunsError(err instanceof Error ? err.message : '加载运行详情失败');
    }
  }

  async function handleResume(runId: string) {
    setResumingRunId(runId);
    setResumeNotice('');
    setRunsError('');
    try {
      const res = await runsApi.resume(runId);
      const status = (res.result?.status as string) ?? '';
      setResumeNotice(
        status === 'success'
          ? `run ${runId} 已从失败步恢复，全部步骤执行成功。`
          : `run ${runId} 恢复执行结束，状态：${status}（可展开详情查看失败步）。`
      );
      setRunDetail(null);
      await loadRuns();
    } catch (err) {
      setRunsError(err instanceof Error ? err.message : '恢复失败');
    } finally {
      setResumingRunId(null);
    }
  }

  // 智能路由结果解析
  function renderRouteResult() {
    if (!routeResult) return null;
    const target = (routeResult.target_agent as string) || (routeResult.agent as string) || '';
    const confidence = routeResult.confidence as number | undefined;
    const explanation = (routeResult.explanation as string) || (routeResult.reasoning as string) || '';
    const routePath = ROUTE_TARGETS[target];

    return (
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <Card className="border-copper/20">
          <div className="flex items-start gap-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-copper/10">
              <i className="fas fa-route text-copper-light" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <h3 className="font-serif text-sm text-ink-bg">识别目标</h3>
                {target && (
                  <span className="rounded bg-copper/10 px-2 py-0.5 text-[10px] font-medium text-copper-light">
                    {target}
                  </span>
                )}
                {confidence !== undefined && (
                  <span className="text-[10px] text-ink-bg/60">
                    置信度 {(confidence * 100).toFixed(0)}%
                  </span>
                )}
              </div>
              {explanation && (
                <p className="mt-2 text-sm text-ink-bg/60">{explanation}</p>
              )}
              {routePath && (
                <Button
                  variant="secondary"
                  size="sm"
                  className="mt-3"
                  onClick={() => navigate(routePath)}
                >
                  <i className="fas fa-arrow-right mr-1.5" />
                  前往 {target}
                </Button>
              )}
            </div>
          </div>
          <details className="mt-3">
            <summary className="cursor-pointer text-xs text-ink-bg/60 hover:text-ink-bg/60">
              查看原始响应
            </summary>
            <pre className="mt-2 max-h-60 overflow-auto rounded-lg bg-ink-dark/60 p-3 text-xs text-ink-bg/70">
              {JSON.stringify(routeResult, null, 2)}
            </pre>
          </details>
        </Card>
      </motion.div>
    );
  }

  return (
    <div>
      <PageHeader
        title="智能协调器"
        subtitle="能力地图 · 工作流模板 · 意图路由 · 多 Agent 编排"
        icon="fa-route"
      />

      <div className="mb-6 flex gap-6 border-b border-copper/10">
        {([
          { key: 'route' as TabKey, label: '智能路由', icon: 'fa-route' },
          { key: 'capabilities' as TabKey, label: '能力地图', icon: 'fa-map' },
          { key: 'workflows' as TabKey, label: '工作流模板', icon: 'fa-diagram-project' },
          { key: 'orchestrate' as TabKey, label: '多 Agent 编排', icon: 'fa-sitemap' },
          { key: 'runs' as TabKey, label: '运行记录', icon: 'fa-clock-rotate-left' },
        ]).map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex cursor-pointer items-center gap-2 px-1 pb-3 text-sm transition-colors ${
              tab === t.key
                ? 'border-b-2 border-copper text-copper-light'
                : 'border-b-2 border-transparent text-ink-bg/50 hover:text-ink-bg'
            }`}
          >
            <i className={`fas ${t.icon} text-xs`} />
            {t.label}
          </button>
        ))}
      </div>

      {/* 智能路由 Tab */}
      {tab === 'route' && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="mb-6">
            <form onSubmit={handleRoute} className="flex flex-col gap-3 sm:flex-row">
              <div className="flex-1">
                <Input
                  icon="fa-wand-magic-sparkles"
                  placeholder="描述你的需求，系统自动路由到对应模块..."
                  value={taskInput}
                  onChange={e => setTaskInput(e.target.value)}
                  className="h-12 text-base"
                />
              </div>
              <Button type="submit" loading={routeLoading} className="h-12 shrink-0 sm:px-8">
                <i className="fas fa-route mr-1.5" />
                路由
              </Button>
            </form>
          </Card>

          {/* 快捷建议 */}
          {!routeResult && !routeLoading && (
            <div className="mb-6">
              <p className="mb-3 text-xs text-ink-bg/60">快捷路由：</p>
              <div className="flex flex-wrap gap-2">
                {ROUTE_SUGGESTIONS.map(s => (
                  <button
                    key={s.label}
                    onClick={() => handleSuggestionClick(s.task)}
                    className="flex cursor-pointer items-center gap-1.5 rounded-full border border-copper/15 bg-copper/[0.03] px-3 py-1.5 text-xs text-ink-bg/50 transition-colors hover:border-copper/30 hover:bg-copper/10 hover:text-copper-light"
                  >
                    <i className={`fas ${s.icon}`} />
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {routeError && <div className="mb-4"><ErrorBanner message={routeError} /></div>}
          {routeLoading && <Loading text="分析意图，路由中..." />}
          {renderRouteResult()}
        </motion.div>
      )}

      {/* 多 Agent 编排 Tab */}
      {tab === 'orchestrate' && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="mb-6">
            <form onSubmit={handleOrchestrate} className="flex flex-col gap-3 sm:flex-row">
              <div className="flex-1">
                <Input
                  icon="fa-sitemap"
                  placeholder="描述端到端需求，系统自动规划并并行执行（如：检索文献、精读、写论文）..."
                  value={orchInput}
                  onChange={e => setOrchInput(e.target.value)}
                  className="h-12 text-base"
                />
              </div>
              <Button type="submit" loading={orchLoading} className="h-12 shrink-0 sm:px-8">
                <i className="fas fa-sitemap mr-1.5" />
                编排
              </Button>
            </form>
          </Card>

          {orchError && <div className="mb-4"><ErrorBanner message={orchError} /></div>}

          {orchTaskId && (
            <Card className="mb-6">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="font-serif text-sm text-ink-bg">执行进度</h3>
                <span className={`text-[11px] ${orchWsReady ? 'text-emerald-500' : 'text-amber-500'}`}>
                  {orchWsReady ? '实时通道已连接' : '正在连接实时通道...'}
                </span>
              </div>

              {orchStream.plannedAgents.length > 0 ? (
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  {orchStream.plannedAgents.map((name, i) => {
                    const done = orchStream.agents.includes(name);
                    const current = orchStream.currentAgent === name;
                    return (
                      <span key={name} className="flex items-center gap-1">
                        {i > 0 && <i className="fas fa-chevron-right text-[8px] text-ink-bg/20" />}
                        <span
                          className={`rounded px-2 py-1 text-[11px] ${
                            done
                              ? 'bg-emerald-500/10 text-emerald-500'
                              : current
                                ? 'animate-pulse bg-copper/15 text-copper-light'
                                : 'bg-copper/10 text-ink-bg/40'
                          }`}
                        >
                          {done && <i className="fas fa-check mr-1" />}
                          {name}
                        </span>
                      </span>
                    );
                  })}
                </div>
              ) : (
                <p className="mb-3 text-xs text-ink-bg/50">
                  {orchLoading ? '正在规划任务，等待执行计划...' : '等待编排启动...'}
                </p>
              )}

              {orchStream.events.length > 0 && (
                <details open>
                  <summary className="cursor-pointer text-xs text-ink-bg/60">
                    事件流（{orchStream.events.length}）
                  </summary>
                  <pre className="mt-2 max-h-48 overflow-auto rounded-lg bg-ink-dark/60 p-3 text-[11px] leading-5 text-ink-bg/70">
                    {orchStream.events.slice(-30).map((ev, i) => (
                      <div key={i}>
                        {ev.type}
                        {ev.agent ? ` [${ev.agent}]` : ''}
                        {ev.status ? ` status=${ev.status}` : ''}
                      </div>
                    ))}
                  </pre>
                </details>
              )}
            </Card>
          )}

          {orchResult && (
            <Card>
              {(() => {
                const status = (orchResult.result.status as string) ?? '';
                const agentsUsed = (orchResult.result.agents_used as string[] | undefined) ?? [];
                const ok = status === 'success';
                return (
                  <>
                    <div className="mb-3 flex flex-wrap items-center gap-2">
                      <i className={`fas ${ok ? 'fa-circle-check text-emerald-500' : 'fa-circle-exclamation text-amber-500'}`} />
                      <h3 className="font-serif text-sm text-ink-bg">
                        {ok ? '编排完成' : '编排完成（部分失败）'}
                      </h3>
                      <span className="text-[10px] text-ink-bg/40">task_id: {orchResult.task_id}</span>
                    </div>
                    {agentsUsed.length > 0 && (
                      <p className="mb-3 text-xs text-ink-bg/60">参与 Agent：{agentsUsed.join(' → ')}</p>
                    )}
                    <details>
                      <summary className="cursor-pointer text-xs text-ink-bg/60">查看完整结果</summary>
                      <pre className="mt-2 max-h-96 overflow-auto rounded-lg bg-ink-dark/60 p-3 text-xs text-ink-bg/70">
                        {JSON.stringify(orchResult.result, null, 2)}
                      </pre>
                    </details>
                  </>
                );
              })()}
            </Card>
          )}
        </motion.div>
      )}

      {/* 能力地图 Tab */}
      {tab === 'capabilities' && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          {capsError && <div className="mb-4"><ErrorBanner message={capsError} /></div>}
          {capsLoading ? (
            <Loading text="加载能力地图" />
          ) : capabilities.length > 0 ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {capabilities.map(skill => (
                <Card key={skill.name} className="p-4 transition-colors hover:border-copper/30">
                  <div className="flex items-start gap-3">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-copper/10">
                      <i className="fas fa-puzzle-piece text-xs text-copper-light" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-serif text-sm text-ink-bg">{skill.name}</h3>
                      <p className="mt-1 line-clamp-2 text-xs text-ink-bg/50">{skill.description}</p>
                      {skill.category && (
                        <span className="mt-2 inline-block rounded bg-copper/10 px-1.5 py-0.5 text-[10px] text-copper-light">
                          {skill.category}
                        </span>
                      )}
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          ) : (
            <EmptyState
              icon="fa-map"
              title="能力地图"
              hint="点击下方按钮加载系统所有能力模块"
              action={
                <Button onClick={loadCapabilities} variant="secondary" size="sm" className="mt-4">
                  <i className="fas fa-sync mr-1.5" />
                  加载能力地图
                </Button>
              }
            />
          )}
        </motion.div>
      )}

      {/* 工作流模板 Tab */}
      {tab === 'workflows' && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          {wfError && <div className="mb-4"><ErrorBanner message={wfError} /></div>}
          {wfLoading ? (
            <Loading text="加载工作流模板" />
          ) : workflows.length > 0 ? (
            <div className="space-y-3">
              {workflows.map(wf => (
                <Card key={wf.id} className="p-5">
                  <div className="flex items-start gap-4">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-copper/10">
                      <i className="fas fa-diagram-project text-copper-light" />
                    </div>
                    <div className="flex-1">
                      <h3 className="font-serif text-sm text-ink-bg">{wf.name}</h3>
                      <p className="mt-1 text-xs text-ink-bg/50">{wf.description}</p>
                      {wf.steps && wf.steps.length > 0 && (
                        <div className="mt-3 flex flex-wrap items-center gap-2">
                          {wf.steps.map((step, i) => (
                            <span key={i} className="flex items-center gap-1 text-[11px] text-ink-bg/50">
                              {i > 0 && <i className="fas fa-chevron-right text-[8px] text-ink-bg/20" />}
                              <span className="rounded bg-copper/10 px-1.5 py-0.5">{step}</span>
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          ) : (
            <EmptyState
              icon="fa-diagram-project"
              title="工作流模板"
              hint="点击下方按钮加载预设工作流模板"
              action={
                <Button onClick={loadWorkflows} variant="secondary" size="sm" className="mt-4">
                  <i className="fas fa-sync mr-1.5" />
                  加载工作流
                </Button>
              }
            />
          )}
        </motion.div>
      )}
      {/* 运行记录 Tab（E6 恢复） */}
      {tab === 'runs' && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          {resumeNotice && (
            <div className="mb-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-500">
              <i className="fas fa-circle-check mr-2" />
              {resumeNotice}
            </div>
          )}
          {runsError && <div className="mb-4"><ErrorBanner message={runsError} /></div>}
          {runsLoading ? (
            <Loading text="加载运行记录" />
          ) : runsList.length > 0 ? (
            <div className="space-y-3">
              {runsList.map(run => {
                const ok = run.status === 'succeeded';
                const failed = run.status === 'failed';
                const src = run.source;
                const srcLabel =
                  src?.kind === 'template'
                    ? `模板 ${src.template_id ?? ''}`
                    : src?.kind === 'workflow'
                      ? `工作流 ${src.name || src.workflow_id || ''}`
                      : (src?.kind ?? '');
                const expanded = runDetail?.run_id === run.run_id;
                return (
                  <Card key={run.run_id} className="p-5">
                    <div className="flex flex-wrap items-center gap-3">
                      <i
                        className={`fas ${
                          ok
                            ? 'fa-circle-check text-emerald-500'
                            : failed
                              ? 'fa-circle-exclamation text-amber-500'
                              : 'fa-spinner text-copper-light'
                        }`}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-mono text-xs text-ink-bg">run {run.run_id}</span>
                          <span className="rounded bg-copper/10 px-1.5 py-0.5 text-[10px] text-copper-light">
                            {srcLabel}
                          </span>
                          <span
                            className={`rounded px-1.5 py-0.5 text-[10px] ${
                              ok
                                ? 'bg-emerald-500/10 text-emerald-500'
                                : failed
                                  ? 'bg-amber-500/10 text-amber-500'
                                  : 'bg-copper/10 text-ink-bg/50'
                            }`}
                          >
                            {failed ? '失败（可恢复）' : ok ? '成功' : run.status}
                          </span>
                        </div>
                        <div className="mt-2 flex flex-wrap items-center gap-1.5">
                          {run.steps.map(s => (
                            <span
                              key={s.agent}
                              className={`rounded px-1.5 py-0.5 text-[10px] ${
                                s.status === 'success'
                                  ? 'bg-emerald-500/10 text-emerald-500'
                                  : s.status === 'failed'
                                    ? 'bg-red-500/10 text-red-400'
                                    : 'bg-copper/10 text-ink-bg/40'
                              }`}
                            >
                              {s.agent}
                            </span>
                          ))}
                        </div>
                        {failed && run.error && (
                          <p className="mt-2 line-clamp-2 text-xs text-ink-bg/60">{run.error}</p>
                        )}
                      </div>
                      <div className="flex shrink-0 gap-2">
                        {failed && (
                          <Button
                            size="sm"
                            loading={resumingRunId === run.run_id}
                            onClick={() => handleResume(run.run_id)}
                          >
                            <i className="fas fa-rotate-right mr-1.5" />
                            从失败步恢复
                          </Button>
                        )}
                        <Button variant="secondary" size="sm" onClick={() => toggleRunDetail(run.run_id)}>
                          <i className={`fas ${expanded ? 'fa-chevron-up' : 'fa-chevron-down'} mr-1.5`} />
                          详情
                        </Button>
                      </div>
                    </div>
                    {expanded && runDetail && (
                      <div className="mt-4 space-y-2 border-t border-copper/10 pt-4">
                        {runDetail.steps.map(s => (
                          <div key={s.agent} className="rounded-lg bg-ink-dark/40 p-3">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="text-xs font-medium text-ink-bg">{s.agent}</span>
                              <span
                                className={`rounded px-1.5 py-0.5 text-[10px] ${
                                  s.status === 'success'
                                    ? 'bg-emerald-500/10 text-emerald-500'
                                    : s.status === 'failed'
                                      ? 'bg-red-500/10 text-red-400'
                                      : 'bg-copper/10 text-ink-bg/40'
                                }`}
                              >
                                {s.status === 'failed' ? `失败 ×${s.attempts ?? 1}` : s.status}
                              </span>
                              {s.status === 'failed' && s.failure_class === 'transient' && (
                                <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] text-amber-500">
                                  疑似瞬时故障，恢复大概率成功
                                </span>
                              )}
                              {s.status === 'failed' && s.failure_class === 'permanent' && (
                                <span className="rounded bg-red-500/10 px-1.5 py-0.5 text-[10px] text-red-400">
                                  疑似确定性故障，请先修正再恢复
                                </span>
                              )}
                            </div>
                            {s.error && (
                              <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap text-[11px] text-red-400/80">
                                {s.error}
                              </pre>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </Card>
                );
              })}
            </div>
          ) : (
            <EmptyState
              icon="fa-clock-rotate-left"
              title="运行记录"
              hint="模板编排与自定义工作流的每次运行都会在此留下检查点；失败后可从失败步恢复，不重复已完成的 LLM 工作"
              action={
                <Button onClick={loadRuns} variant="secondary" size="sm" className="mt-4">
                  <i className="fas fa-sync mr-1.5" />
                  刷新
                </Button>
              }
            />
          )}
        </motion.div>
      )}
    </div>
  );
}

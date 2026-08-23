// 协调器页 — 能力地图 · 工作流模板 · 智能路由
import { useState, useEffect, type FormEvent } from 'react';
import { motion } from 'motion/react';
import { useNavigate } from 'react-router-dom';
import { PageHeader, Button, Card, Input, Loading, EmptyState, ErrorBanner } from '../components/ui';
import { coordinatorApi } from '../api';

type TabKey = 'route' | 'capabilities' | 'workflows';

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

  useEffect(() => {
    if (tab === 'capabilities' && capabilities.length === 0) loadCapabilities();
    if (tab === 'workflows' && workflows.length === 0) loadWorkflows();
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
        subtitle="能力地图 · 工作流模板 · 意图路由"
        icon="fa-route"
      />

      <div className="mb-6 flex gap-6 border-b border-copper/10">
        {([
          { key: 'route' as TabKey, label: '智能路由', icon: 'fa-route' },
          { key: 'capabilities' as TabKey, label: '能力地图', icon: 'fa-map' },
          { key: 'workflows' as TabKey, label: '工作流模板', icon: 'fa-diagram-project' },
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
    </div>
  );
}

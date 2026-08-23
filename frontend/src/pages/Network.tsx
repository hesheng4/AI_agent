// 引用网络分析页 — 图谱 · 共引 · 影响力
import { useMemo, useState } from 'react';
import { motion } from 'motion/react';
import { PageHeader, Button, Card, Loading, EmptyState, ErrorBanner, Input } from '../components/ui';
import { libraryApi } from '../api';
import type { NetworkGraph } from '../types';

type TabKey = 'graph' | 'influential' | 'coCitation';

const TABS: Array<{ key: TabKey; label: string; icon: string }> = [
  { key: 'graph', label: '引用图谱', icon: 'fa-project-diagram' },
  { key: 'influential', label: '高影响力论文', icon: 'fa-award' },
  { key: 'coCitation', label: '共被引分析', icon: 'fa-link' },
];

// ── F3: 力导向引用图谱可视化（纯 SVG，无外部依赖）──
interface GraphNode {
  id: string;
  title: string;
  degree: number;
}
interface GraphEdge {
  source: string;
  target: string;
}

function ForceDirectedGraph({ nodes, edges }: { nodes: GraphNode[]; edges: GraphEdge[] }) {
  const W = 780;
  const H = 460;

  // 力导向布局：斥力 + 弹簧 + 向心力，迭代 120 轮
  const layout = useMemo(() => {
    const pos = new Map<string, { x: number; y: number }>();
    nodes.forEach((n, i) => {
      const angle = (i / Math.max(1, nodes.length)) * Math.PI * 2;
      pos.set(n.id, { x: W / 2 + Math.cos(angle) * (W / 3), y: H / 2 + Math.sin(angle) * (H / 3) });
    });
    const K = 1800; // 弹簧常数
    const REPULSION = 4200; // 斥力系数
    for (let iter = 0; iter < 120; iter++) {
      const forces = new Map<string, { fx: number; fy: number }>();
      nodes.forEach(n => forces.set(n.id, { fx: 0, fy: 0 }));
      // 斥力（所有节点对）
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = pos.get(nodes[i].id)!;
          const b = pos.get(nodes[j].id)!;
          let dx = b.x - a.x;
          let dy = b.y - a.y;
          let dist = Math.sqrt(dx * dx + dy * dy) || 1;
          dx /= dist; dy /= dist;
          const rep = REPULSION / (dist * dist);
          forces.get(nodes[i].id)!.fx -= dx * rep;
          forces.get(nodes[i].id)!.fy -= dy * rep;
          forces.get(nodes[j].id)!.fx += dx * rep;
          forces.get(nodes[j].id)!.fy += dy * rep;
        }
      }
      // 弹簧（边）
      edges.forEach(e => {
        const a = pos.get(e.source);
        const b = pos.get(e.target);
        if (!a || !b) return;
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        dx /= dist; dy /= dist;
        const f = (dist - 90) * K * 0.01;
        forces.get(e.source)!.fx += dx * f;
        forces.get(e.source)!.fy += dy * f;
        forces.get(e.target)!.fx -= dx * f;
        forces.get(e.target)!.fy -= dy * f;
      });
      // 应用力 + 向心约束
      nodes.forEach(n => {
        const p = pos.get(n.id)!;
        const f = forces.get(n.id)!;
        p.x += f.fx * 0.05 + (W / 2 - p.x) * 0.01;
        p.y += f.fy * 0.05 + (H / 2 - p.y) * 0.01;
        p.x = Math.max(30, Math.min(W - 30, p.x));
        p.y = Math.max(30, Math.min(H - 30, p.y));
      });
    }
    return pos;
  }, [nodes, edges]);

  // hover 高亮：高亮邻居与相关边
  const [hovered, setHovered] = useState<string | null>(null);
  const edgeMap = useMemo(() => {
    const m = new Map<string, Set<string>>();
    edges.forEach(e => {
      if (!m.has(e.source)) m.set(e.source, new Set());
      if (!m.has(e.target)) m.set(e.target, new Set());
      m.get(e.source)!.add(e.target);
      m.get(e.target)!.add(e.source);
    });
    return m;
  }, [edges]);
  const isNeighbor = hovered
    ? (id: string) => id === hovered || (edgeMap.get(hovered)?.has(id) ?? false)
    : () => true;
  const edgeActive = hovered
    ? (e: GraphEdge) => e.source === hovered || e.target === hovered
    : () => true;

  const maxDegree = Math.max(1, ...nodes.map(n => n.degree));

  return (
    <div className="overflow-hidden rounded-xl border border-copper/10 bg-ink-dark/30">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="引用关系力导向图">
        {/* 边 */}
        {edges.map((e, i) => {
          const a = layout.get(e.source);
          const b = layout.get(e.target);
          if (!a || !b) return null;
          const active = edgeActive(e);
          return (
            <line
              key={`e-${i}`}
              x1={a.x} y1={a.y} x2={b.x} y2={b.y}
              stroke={active ? '#C8A86B' : '#3A2E24'}
              strokeWidth={active ? 1.5 : 0.8}
              opacity={active ? 0.85 : 0.35}
            />
          );
        })}
        {/* 节点 */}
        {nodes.map(n => {
          const p = layout.get(n.id);
          if (!p) return null;
          const active = isNeighbor(n.id);
          const r = 8 + (n.degree / maxDegree) * 14;
          return (
            <g
              key={n.id}
              transform={`translate(${p.x},${p.y})`}
              onMouseEnter={() => setHovered(n.id)}
              onMouseLeave={() => setHovered(null)}
              className="cursor-pointer"
            >
              <circle
                r={r}
                fill={active ? '#C8A86B' : '#57402A'}
                stroke={hovered === n.id ? '#F0D9A8' : '#8A6A3F'}
                strokeWidth={1.2}
                opacity={active ? 1 : 0.55}
              />
              <text
                y={r + 12}
                textAnchor="middle"
                fontSize="9"
                fill={active ? '#E8D5B0' : '#8A6A3F'}
                opacity={active ? 1 : 0.6}
              >
                {n.title.length > 22 ? n.title.slice(0, 22) + '…' : n.title}
              </text>
            </g>
          );
        })}
      </svg>
      {hovered && (
        <div className="pointer-events-none absolute bottom-3 left-3 rounded-lg border border-copper/20 bg-ink-dark/80 px-3 py-1.5 text-xs text-ink-bg/80 backdrop-blur">
          <span className="text-copper-light">{hovered}</span> · 引用度 {edgeMap.get(hovered)?.size ?? 0}
        </div>
      )}
    </div>
  );
}


export default function Network() {
  const [tab, setTab] = useState<TabKey>('graph');

  // 图谱 tab 状态
  const [graphPaperId, setGraphPaperId] = useState('');
  const [graphDepth, setGraphDepth] = useState(2);
  const [graphData, setGraphData] = useState<NetworkGraph | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphError, setGraphError] = useState('');

  // 影响力 tab 状态
  const [influTopK, setInfluTopK] = useState(10);
  const [influPapers, setInfluPapers] = useState<unknown[]>([]);
  const [influLoading, setInfluLoading] = useState(false);
  const [influError, setInfluError] = useState('');
  const [influQueried, setInfluQueried] = useState(false);

  // 共引 tab 状态
  const [coMin, setCoMin] = useState(1);
  const [coTopK, setCoTopK] = useState(50);
  const [coData, setCoData] = useState<unknown>(null);
  const [coLoading, setCoLoading] = useState(false);
  const [coError, setCoError] = useState('');
  const [coQueried, setCoQueried] = useState(false);

  async function handleQueryGraph() {
    if (!graphPaperId.trim()) {
      setGraphError('请输入 paper_id');
      return;
    }
    setGraphLoading(true);
    setGraphError('');
    setGraphData(null);
    try {
      const data = await libraryApi.getGraph(graphPaperId.trim(), graphDepth);
      setGraphData(data);
    } catch (err) {
      setGraphError(err instanceof Error ? err.message : '加载图谱失败');
    } finally {
      setGraphLoading(false);
    }
  }

  async function handleQueryInfluential() {
    setInfluLoading(true);
    setInfluError('');
    setInfluPapers([]);
    try {
      const res = await libraryApi.influentialPapers(influTopK);
      const list = Array.isArray(res?.influential_papers) ? res.influential_papers : [];
      setInfluPapers(list);
      setInfluQueried(true);
    } catch (err) {
      setInfluError(err instanceof Error ? err.message : '加载影响力论文失败');
    } finally {
      setInfluLoading(false);
    }
  }

  async function handleQueryCoCitation() {
    setCoLoading(true);
    setCoError('');
    setCoData(null);
    try {
      const data = await libraryApi.coCitation(coMin, coTopK);
      setCoData(data);
      setCoQueried(true);
    } catch (err) {
      setCoError(err instanceof Error ? err.message : '加载共引分析失败');
    } finally {
      setCoLoading(false);
    }
  }

  // 安全读取数值
  function safeNumber(v: unknown): number | null {
    if (typeof v === 'number' && Number.isFinite(v)) return v;
    if (typeof v === 'string' && v.trim() !== '' && !isNaN(Number(v))) return Number(v);
    return null;
  }

  return (
    <div>
      <PageHeader
        title="引用网络"
        subtitle="图谱 · 共引 · 影响力"
        icon="fa-project-diagram"
      />

      {/* Tab 切换 */}
      <div className="mb-6 flex gap-6 border-b border-copper/10">
        {TABS.map(t => (
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

      {/* 图谱 Tab */}
      {tab === 'graph' && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="mb-4">
            <div className="flex flex-wrap items-end gap-3">
              <div className="min-w-[240px] flex-1">
                <Input
                  label="Paper ID"
                  icon="fa-fingerprint"
                  placeholder="输入论文 ID..."
                  value={graphPaperId}
                  onChange={e => setGraphPaperId(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleQueryGraph()}
                />
              </div>
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">深度</span>
                <select
                  value={graphDepth}
                  onChange={e => setGraphDepth(Number(e.target.value))}
                  className="cursor-pointer rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none focus:ring-1 focus:ring-copper/30"
                >
                  {[1, 2, 3, 4, 5].map(d => (
                    <option key={d} value={d} className="bg-ink-dark text-ink-bg">
                      {d} 层
                    </option>
                  ))}
                </select>
              </label>
              <Button onClick={handleQueryGraph} loading={graphLoading}>
                <i className="fas fa-search mr-1.5" />
                查询图谱
              </Button>
            </div>
          </Card>

          {graphError && <div className="mb-4"><ErrorBanner message={graphError} /></div>}

          {graphLoading ? (
            <Loading text="构建引用图谱" />
          ) : graphData ? (
            <div className="space-y-4">
              {/* 统计卡片 */}
              <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
                <Card className="p-4">
                  <div className="flex items-center gap-3">
                    <i className="fas fa-circle-nodes text-copper-light" />
                    <div>
                      <div className="font-serif text-2xl text-ink-bg">{graphData.nodes?.length ?? 0}</div>
                      <div className="text-[10px] text-ink-bg/60">节点数</div>
                    </div>
                  </div>
                </Card>
                <Card className="p-4">
                  <div className="flex items-center gap-3">
                    <i className="fas fa-share-nodes text-jade" />
                    <div>
                      <div className="font-serif text-2xl text-ink-bg">{graphData.edges?.length ?? 0}</div>
                      <div className="text-[10px] text-ink-bg/60">边数</div>
                    </div>
                  </div>
                </Card>
                <Card className="p-4">
                  <div className="flex items-center gap-3">
                    <i className="fas fa-chart-line text-indigo" />
                    <div>
                      <div className="font-serif text-2xl text-ink-bg">
                        {Object.keys(graphData.metrics || {}).length}
                      </div>
                      <div className="text-[10px] text-ink-bg/60">指标项数</div>
                    </div>
                  </div>
                </Card>
              </div>

              {/* 力导向图可视化（F3） */}
              {graphData.nodes?.length ? (
                <Card>
                  <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg">
                    <i className="fas fa-project-diagram text-copper-light" />
                    引用关系图
                  </h3>
                  {(() => {
                    // 先归一化边，再统计每节点度数（节点大小随引用度缩放）
                    const edges = (graphData.edges ?? [])
                      .map(e => {
                        const obj = (e || {}) as Record<string, unknown>;
                        return {
                          source: String(obj.source ?? obj.from ?? ''),
                          target: String(obj.target ?? obj.to ?? ''),
                        };
                      })
                      .filter(e => e.source && e.target);
                    const degreeMap = new Map<string, number>();
                    edges.forEach(e => {
                      degreeMap.set(e.source, (degreeMap.get(e.source) ?? 0) + 1);
                      degreeMap.set(e.target, (degreeMap.get(e.target) ?? 0) + 1);
                    });
                    return (
                      <ForceDirectedGraph
                        nodes={graphData.nodes.map(n => {
                          const obj = (n || {}) as Record<string, unknown>;
                          const id = String(obj.id ?? obj.paper_id ?? '');
                          return {
                            id,
                            title: String(obj.title ?? id),
                            degree: degreeMap.get(id) ?? 0,
                          };
                        })}
                        edges={edges}
                      />
                    );
                  })()}
                </Card>
              ) : null}

              {/* 网络指标 */}
              {graphData.metrics && Object.keys(graphData.metrics).length > 0 && (
                <Card>
                  <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg">
                    <i className="fas fa-gauge text-copper-light" />
                    网络指标
                  </h3>
                  <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
                    {Object.entries(graphData.metrics).map(([k, v]) => (
                      <div key={k} className="rounded-lg border border-copper/10 bg-ink-dark/40 px-3 py-2">
                        <div className="text-[10px] text-ink-bg/60">{k}</div>
                        <div className="mt-0.5 truncate font-serif text-sm text-ink-bg" title={String(v)}>
                          {String(v)}
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              {/* 原始数据预览 */}
              <Card>
                <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg">
                  <i className="fas fa-code text-copper-light" />
                  原始数据
                </h3>
                <pre className="max-h-96 overflow-auto rounded-lg bg-ink-dark/60 p-3 text-xs text-ink-bg/70">
{JSON.stringify(graphData, null, 2)}
                </pre>
              </Card>
            </div>
          ) : (
            <EmptyState
              icon="fa-project-diagram"
              title="输入 Paper ID 构建引用图谱"
              hint="支持 1-5 层深度展开，展示节点、边与网络指标"
            />
          )}
        </motion.div>
      )}

      {/* 高影响力论文 Tab */}
      {tab === 'influential' && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="mb-4">
            <div className="flex flex-wrap items-end gap-3">
              <div className="w-40">
                <Input
                  label="Top K"
                  icon="fa-trophy"
                  type="number"
                  min={1}
                  max={100}
                  value={influTopK}
                  onChange={e => setInfluTopK(Math.max(1, Number(e.target.value) || 10))}
                  onKeyDown={e => e.key === 'Enter' && handleQueryInfluential()}
                />
              </div>
              <Button onClick={handleQueryInfluential} loading={influLoading}>
                <i className="fas fa-bolt mr-1.5" />
                查询影响力
              </Button>
              <span className="pb-2 text-xs text-ink-bg/60">
                基于引用网络中心性，返回前 {influTopK} 篇高影响力论文
              </span>
            </div>
          </Card>

          {influError && <div className="mb-4"><ErrorBanner message={influError} /></div>}

          {influLoading ? (
            <Loading text="计算影响力排名" />
          ) : influPapers.length > 0 ? (
            <div className="space-y-2">
              {influPapers.map((item, idx) => {
                const obj = (item || {}) as Record<string, unknown>;
                const title = (obj.title as string) || (obj.paper_id as string) || '未知标题';
                const score = safeNumber(obj.score) ?? safeNumber(obj.influence_score) ?? safeNumber(obj.pagerank);
                const paperId = (obj.paper_id as string) || '';
                const year = safeNumber(obj.year);
                return (
                  <Card key={paperId || idx} className="p-4 transition-colors hover:border-copper/30">
                    <div className="flex items-start gap-3">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-copper/10 font-serif text-sm text-copper-light">
                        {idx + 1}
                      </div>
                      <div className="flex-1">
                        <h3 className="font-serif text-sm text-ink-bg">{title}</h3>
                        <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-ink-bg/60">
                          {paperId && <span className="font-mono">{paperId}</span>}
                          {year !== null && <span>{year}</span>}
                          {typeof obj.authors === 'string' && obj.authors && (
                            <span className="truncate">{obj.authors as string}</span>
                          )}
                          {Array.isArray(obj.authors) && (obj.authors as unknown[]).length > 0 && (
                            <span className="truncate">
                              {(obj.authors as unknown[]).slice(0, 3).join(', ')}
                            </span>
                          )}
                        </div>
                      </div>
                      {score !== null && (
                        <div className="shrink-0 text-right">
                          <div className="font-serif text-lg text-copper-light">{score.toFixed(4)}</div>
                          <div className="text-[10px] text-ink-bg/60">影响力分数</div>
                        </div>
                      )}
                    </div>
                  </Card>
                );
              })}
            </div>
          ) : influQueried ? (
            <EmptyState icon="fa-award" title="未找到高影响力论文" hint="尝试增大 Top K 或确认文献库已建立引用关系" />
          ) : (
            <EmptyState icon="fa-award" title="点击查询获取高影响力论文" hint="基于 PageRank 等中心性指标排序" />
          )}
        </motion.div>
      )}

      {/* 共被引分析 Tab */}
      {tab === 'coCitation' && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="mb-4">
            <div className="flex flex-wrap items-end gap-3">
              <div className="w-44">
                <Input
                  label="最小共引次数"
                  icon="fa-filter"
                  type="number"
                  min={1}
                  value={coMin}
                  onChange={e => setCoMin(Math.max(1, Number(e.target.value) || 1))}
                  onKeyDown={e => e.key === 'Enter' && handleQueryCoCitation()}
                />
              </div>
              <div className="w-40">
                <Input
                  label="Top K"
                  icon="fa-trophy"
                  type="number"
                  min={1}
                  max={500}
                  value={coTopK}
                  onChange={e => setCoTopK(Math.max(1, Number(e.target.value) || 50))}
                  onKeyDown={e => e.key === 'Enter' && handleQueryCoCitation()}
                />
              </div>
              <Button onClick={handleQueryCoCitation} loading={coLoading}>
                <i className="fas fa-link mr-1.5" />
                查询共引
              </Button>
            </div>
          </Card>

          {coError && <div className="mb-4"><ErrorBanner message={coError} /></div>}

          {coLoading ? (
            <Loading text="计算共引关系" />
          ) : coData !== null ? (
            <Card>
              <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg">
                <i className="fas fa-code text-copper-light" />
                共引分析结果
              </h3>
              <pre className="max-h-[600px] overflow-auto rounded-lg bg-ink-dark/60 p-3 text-xs text-ink-bg/70">
{JSON.stringify(coData, null, 2)}
              </pre>
            </Card>
          ) : coQueried ? (
            <EmptyState icon="fa-link" title="未找到共引关系" hint="尝试降低最小共引次数阈值" />
          ) : (
            <EmptyState
              icon="fa-link"
              title="设置参数后查询共引关系"
              hint="挖掘被同一文献引用的论文对，发现研究主题聚类"
            />
          )}
        </motion.div>
      )}
    </div>
  );
}

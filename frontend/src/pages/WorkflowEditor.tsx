// E5: 工作流编排 — 可视化 DAG 编辑器
import { useState, useEffect, useCallback } from 'react';
import { PageHeader, Button, Card } from '../components/ui';
import { workflowsApi } from '../api';

interface WFNode { id: string; agent: string; task: string; label: string; }
interface WFEdge { source: string; target: string; }
interface Workflow { id: string; name: string; description: string; nodes: WFNode[]; edges: WFEdge[]; }

const AGENT_OPTIONS = [
  'literature','citation','reader','writing','polishing','stats','methods',
  'figure','data','reviewer','response','cover','submission_package',
  'paper2ppt','paper_to_patent','experiment',
];

export default function WorkflowEditor() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [current, setCurrent] = useState<Workflow | null>(null);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState('');

  const loadAll = useCallback(async () => {
    try {
      const res = await workflowsApi.list();
      setWorkflows((res.workflows as unknown as Workflow[]) || []);
    } catch { /* ignore */ }
  }, []);
  useEffect(() => { loadAll(); }, [loadAll]);

  async function handleCreate() {
    try {
      const wf = await workflowsApi.create({ name: '新工作流', nodes: [], edges: [] }) as unknown as Workflow;
      setCurrent(wf);
      loadAll();
    } catch (err) { setError(err instanceof Error ? err.message : '创建失败'); }
  }

  async function handleSave() {
    if (!current) return;
    try {
      await workflowsApi.update(current.id, { nodes: current.nodes, edges: current.edges });
      loadAll();
    } catch (err) { setError(err instanceof Error ? err.message : '保存失败'); }
  }

  async function handleDelete(id: string) {
    try {
      await workflowsApi.delete(id);
      if (current?.id === id) setCurrent(null);
      loadAll();
    } catch { /* ignore */ }
  }

  async function handleRun() {
    if (!current) return;
    setRunning(true); setResult(null); setError('');
    try {
      const res = await workflowsApi.run(current.id);
      setResult(res);
    } catch (err) { setError(err instanceof Error ? err.message : '执行失败'); }
    finally { setRunning(false); }
  }

  function addNode() {
    if (!current) return;
    const id = `n${Date.now()}`;
    setCurrent({ ...current, nodes: [...current.nodes, { id, agent: 'literature', task: '', label: '' }] });
  }

  function removeNode(id: string) {
    if (!current) return;
    setCurrent({
      ...current,
      nodes: current.nodes.filter(n => n.id !== id),
      edges: current.edges.filter(e => e.source !== id && e.target !== id),
    });
  }

  function updateNode(id: string, field: keyof WFNode, value: string) {
    if (!current) return;
    setCurrent({ ...current, nodes: current.nodes.map(n => n.id === id ? { ...n, [field]: value } : n) });
  }

  function addEdge() {
    if (!current || current.nodes.length < 2) return;
    const source = current.nodes[0].id;
    const target = current.nodes[1].id;
    if (current.edges.some(e => e.source === source && e.target === target)) return;
    setCurrent({ ...current, edges: [...current.edges, { source, target }] });
  }

  function removeEdge(source: string, target: string) {
    if (!current) return;
    setCurrent({ ...current, edges: current.edges.filter(e => !(e.source === source && e.target === target)) });
  }

  return (
    <div>
      <PageHeader title="工作流编排" subtitle="自定义 Agent DAG · 拖拽编排 · 一键执行" icon="fa-diagram-project" />
      <div className="grid gap-6 lg:grid-cols-3">
        {/* 左：工作流列表 */}
        <Card>
          <div className="mb-3 flex items-center justify-between">
            <span className="text-sm font-medium text-copper">工作流列表</span>
            <Button onClick={handleCreate}><i className="fas fa-plus mr-1" />新建</Button>
          </div>
          <div className="space-y-2">
            {workflows.map(wf => (
              <div key={wf.id} onClick={() => setCurrent(wf)}
                className={`flex cursor-pointer items-center justify-between rounded-lg border px-3 py-2 transition-all ${current?.id === wf.id ? 'border-copper/50 bg-black' : 'border-copper/10 hover:border-copper/30'}`}>
                <span className="truncate text-sm">{wf.name}</span>
                <button onClick={e => { e.stopPropagation(); handleDelete(wf.id); }} className="text-xs text-red-400/60 hover:text-red-400"><i className="fas fa-trash" /></button>
              </div>
            ))}
            {workflows.length === 0 && <div className="py-4 text-center text-xs text-ink-bg/30">暂无工作流</div>}
          </div>
        </Card>

        {/* 中：DAG 编辑器 */}
        <Card>
          {current ? (
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-copper">{current.name}</span>
                <span className="text-xs text-ink-bg/40">{current.nodes.length} 节点 · {current.edges.length} 边</span>
              </div>
              {/* 节点列表 */}
              <div className="space-y-2">
                {current.nodes.map(node => (
                  <div key={node.id} className="flex items-center gap-2 rounded-lg border border-copper/15 bg-black/30 px-3 py-2">
                    <i className="fas fa-circle text-[8px] text-copper/60" />
                    <select value={node.agent} onChange={e => updateNode(node.id, 'agent', e.target.value)}
                      className="cursor-pointer rounded border border-copper/20 bg-ink-dark/40 px-2 py-1 text-xs text-ink-bg">
                      {AGENT_OPTIONS.map(a => <option key={a} value={a}>{a}</option>)}
                    </select>
                    <input value={node.task} onChange={e => updateNode(node.id, 'task', e.target.value)} placeholder="task"
                      className="w-20 rounded border border-copper/20 bg-ink-dark/40 px-2 py-1 text-xs text-ink-bg" />
                    <input value={node.label} onChange={e => updateNode(node.id, 'label', e.target.value)} placeholder="标签"
                      className="w-24 rounded border border-copper/20 bg-ink-dark/40 px-2 py-1 text-xs text-ink-bg" />
                    <button onClick={() => removeNode(node.id)} className="text-xs text-red-400/60 hover:text-red-400"><i className="fas fa-times" /></button>
                  </div>
                ))}
              </div>
              <div className="flex gap-2">
                <Button onClick={addNode}><i className="fas fa-plus mr-1" />添加节点</Button>
                <Button onClick={addEdge}><i className="fas fa-arrow-right mr-1" />添加依赖</Button>
                <Button onClick={handleSave}><i className="fas fa-save mr-1" />保存</Button>
              </div>
              {/* 边列表 */}
              {current.edges.length > 0 && (
                <div className="space-y-1">
                  <span className="text-xs text-ink-bg/40">依赖关系:</span>
                  {current.edges.map((edge, i) => {
                    const src = current.nodes.find(n => n.id === edge.source);
                    const tgt = current.nodes.find(n => n.id === edge.target);
                    return (
                      <div key={i} className="flex items-center gap-2 text-xs text-ink-bg/60">
                        <span>{src?.agent || edge.source}</span>
                        <i className="fas fa-arrow-right text-copper/40" />
                        <span>{tgt?.agent || edge.target}</span>
                        <button onClick={() => removeEdge(edge.source, edge.target)} className="text-red-400/60 hover:text-red-400"><i className="fas fa-times" /></button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ) : (
            <div className="flex h-40 items-center justify-center text-sm text-ink-bg/30">选择或新建一个工作流</div>
          )}
        </Card>

        {/* 右：执行 */}
        <Card>
          {current ? (
            <div className="space-y-4">
              <Button onClick={handleRun} disabled={running || current.nodes.length === 0}>
                {running ? <><i className="fas fa-spinner fa-spin mr-2" />执行中…</> : <><i className="fas fa-play mr-2" />执行工作流</>}
              </Button>
              {error && <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-400">{error}</div>}
              {result && (
                <div className="space-y-2">
                  <span className="text-xs font-medium text-copper">执行结果</span>
                  <pre className="max-h-60 overflow-auto rounded-lg border border-copper/15 bg-black/50 p-3 font-mono text-xs text-ink-bg/80">
                    {JSON.stringify(result, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ) : (
            <div className="flex h-40 items-center justify-center text-sm text-ink-bg/30">选择工作流后可执行</div>
          )}
        </Card>
      </div>
    </div>
  );
}

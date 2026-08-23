// E10: Agent 生成器 — 自然语言描述 → 代码骨架预览 → 确认写入
import { useState, type FormEvent } from 'react';
import { PageHeader, Button, Card, Textarea } from '../components/ui';
import { agentGeneratorApi } from '../api';

type TabKey = 'agent_py' | 'manifest_yaml' | 'api_route_py' | 'frontend_page_tsx';

const TAB_LABELS: Record<TabKey, string> = {
  agent_py: 'Agent (Python)',
  manifest_yaml: 'Manifest (YAML)',
  api_route_py: 'API 路由 (Python)',
  frontend_page_tsx: '前端页面 (TSX)',
};

export default function AgentGenerator() {
  const [description, setDescription] = useState('');
  const [nameHint, setNameHint] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>('agent_py');
  const [confirming, setConfirming] = useState(false);

  async function handleGenerate(e: FormEvent) {
    e.preventDefault();
    if (!description.trim()) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const res = await agentGeneratorApi.generate({ description: description.trim(), name_hint: nameHint.trim() || undefined });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : '生成失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirm() {
    if (!result?.session_id) return;
    setConfirming(true);
    setError('');
    try {
      const res = await agentGeneratorApi.confirm({ session_id: result.session_id as string });
      setResult(prev => prev ? { ...prev, _confirmed: res } : prev);
    } catch (err) {
      setError(err instanceof Error ? err.message : '确认失败');
    } finally {
      setConfirming(false);
    }
  }

  const confirmed = result?._confirmed as Record<string, unknown> | undefined;
  const codeContent = result ? (result[activeTab] as string || '') : '';

  return (
    <div>
      <PageHeader title="Agent 生成器" subtitle="自然语言描述 → 自动生成代码骨架" icon="fa-wand-magic-sparkles" />

      <div className="grid gap-6 lg:grid-cols-2">
        {/* 左：输入 */}
        <Card>
          <form onSubmit={handleGenerate} className="space-y-4">
            <label className="block">
              <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">描述 Agent 功能</span>
              <Textarea value={description} onChange={e => setDescription(e.target.value)} rows={5}
                placeholder="例：一个能从论文中提取实验参数（样本量、统计方法、效应量）并生成对比表格的 Agent"
                className="font-mono text-sm" />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">目录名（可选）</span>
              <input type="text" value={nameHint} onChange={e => setNameHint(e.target.value)}
                placeholder="extract-table" className="w-full rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none" />
            </label>
            <Button type="submit" disabled={loading || !description.trim()}>
              {loading ? <><i className="fas fa-spinner fa-spin mr-2" />生成中…</> : <><i className="fas fa-wand-magic-sparkles mr-2" />生成 Agent</>}
            </Button>
          </form>

          {error && <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">{error}</div>}

          {confirmed && (
            <div className="mt-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-400">
              <i className="fas fa-check-circle mr-2" />Agent <strong>{confirmed.agent_name as string}</strong> 已创建！文件：
              <ul className="mt-1 list-disc pl-5 text-xs">
                {(confirmed.files as string[]).map(f => <li key={f}>{f}</li>)}
              </ul>
            </div>
          )}
        </Card>

        {/* 右：预览 */}
        <Card>
          {result && !confirmed ? (
            <>
              <div className="mb-3 flex items-center gap-2">
                <span className="text-sm font-medium text-copper">生成结果:</span>
                <span className="font-mono text-xs text-ink-bg/60">{result.agent_name as string} / {result.class_name as string}</span>
              </div>
              {/* Tab 切换 */}
              <div className="mb-3 flex gap-1">
                {(Object.keys(TAB_LABELS) as TabKey[]).map(key => (
                  <button key={key} onClick={() => setActiveTab(key)}
                    className={`rounded-md px-3 py-1 text-xs transition-all ${activeTab === key ? 'bg-black text-copper' : 'text-ink-bg/50 hover:bg-black/40'}`}>
                    {TAB_LABELS[key]}
                  </button>
                ))}
              </div>
              {/* 代码预览 */}
              <pre className="max-h-80 overflow-auto rounded-lg border border-copper/15 bg-black/50 p-4 font-mono text-xs text-ink-bg/80">
                {codeContent}
              </pre>
              {/* api.ts 片段 */}
              {result.frontend_api_ts && (
                <div className="mt-3">
                  <span className="text-xs text-ink-bg/50">api.ts 新增片段:</span>
                  <pre className="mt-1 max-h-32 overflow-auto rounded-lg border border-copper/15 bg-black/50 p-3 font-mono text-xs text-ink-bg/80">
                    {result.frontend_api_ts as string}
                  </pre>
                </div>
              )}
              <div className="mt-4 flex justify-end">
                <Button onClick={handleConfirm} disabled={confirming}>
                  {confirming ? <><i className="fas fa-spinner fa-spin mr-2" />写入中…</> : <><i className="fas fa-check mr-2" />确认写入</>}
                </Button>
              </div>
            </>
          ) : !result ? (
            <div className="flex h-40 items-center justify-center text-sm text-ink-bg/30">
              输入描述后点击生成，代码骨架将在此预览
            </div>
          ) : null}
        </Card>
      </div>
    </div>
  );
}

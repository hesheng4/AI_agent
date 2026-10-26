// 产出物页 — Agent 结果持久化：列表 / 筛选 / 查看 / 删除
import { useCallback, useEffect, useState } from 'react';
import { PageHeader, Button, Card, Input, ErrorBanner } from '../components/ui';
import { artifactsApi, type Artifact } from '../api';

export default function ArtifactsPage() {
  const [items, setItems] = useState<Artifact[]>([]);
  const [agentFilter, setAgentFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<Artifact | null>(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await artifactsApi.list(agentFilter ? { agent: agentFilter } : undefined);
      setItems(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载产出物失败');
    } finally {
      setLoading(false);
    }
  }, [agentFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleDelete(id: string) {
    if (!window.confirm('确定删除该产出物？此操作不可恢复。')) return;
    try {
      await artifactsApi.delete(id);
      setItems(prev => prev.filter(a => a.id !== id));
      if (selected?.id === id) setSelected(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败');
    }
  }

  function payloadText(a: Artifact): string {
    try {
      return JSON.stringify(a.payload, null, 2);
    } catch {
      return String(a.payload);
    }
  }

  return (
    <div>
      <PageHeader title="结果存档" subtitle="Agent 产出物持久化 · 可随时重新导出" icon="fa-box-archive" />

      <Card className="mb-6">
        <div className="flex items-end gap-3">
          <div className="flex-1">
            <Input
              label="按 Agent 筛选（留空显示全部）"
              icon="fa-robot"
              placeholder="如 reviewer / writing / coordinator"
              value={agentFilter}
              onChange={e => setAgentFilter(e.target.value)}
            />
          </div>
          <Button onClick={() => void load()} loading={loading}>
            <i className="fas fa-rotate mr-1.5" />刷新
          </Button>
        </div>
      </Card>

      {error && <ErrorBanner message={error} />}

      {!loading && items.length === 0 && !error && (
        <Card>
          <p className="py-6 text-center text-sm text-ink-bg/50">
            暂无产出物。在智能路由页勾选「保存结果」或调用 POST /api/v1/artifacts 保存 Agent 产出。
          </p>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {items.map(a => (
          <Card key={a.id} className={selected?.id === a.id ? 'border-copper' : ''}>
            <div className="mb-2 flex items-start justify-between gap-2">
              <div>
                <div className="text-sm font-medium text-ink-bg">{a.title}</div>
                <div className="mt-1 flex items-center gap-2 text-xs text-ink-bg/50">
                  <span className="rounded-full border border-copper/20 bg-copper/5 px-2 py-0.5 text-copper-light">
                    {a.agent}
                  </span>
                  {a.created_at && <span>{new Date(a.created_at).toLocaleString()}</span>}
                </div>
              </div>
              <div className="flex shrink-0 gap-1.5">
                <button
                  onClick={() => { setSelected(selected?.id === a.id ? null : a); setCopied(false); }}
                  className="cursor-pointer rounded-md border border-copper/20 px-2 py-1 text-xs text-copper-light hover:bg-copper/10"
                  title="查看 payload"
                >
                  <i className="fas fa-eye" />
                </button>
                <button
                  onClick={() => void handleDelete(a.id)}
                  className="cursor-pointer rounded-md border border-red-500/20 px-2 py-1 text-xs text-red-400 hover:bg-red-500/10"
                  title="删除"
                >
                  <i className="fas fa-trash" />
                </button>
              </div>
            </div>
            {selected?.id === a.id && (
              <div className="mt-2">
                <pre className="max-h-72 overflow-auto rounded-md bg-ink-dark/60 p-3 text-xs text-ink-bg/80">
                  {payloadText(a)}
                </pre>
                <div className="mt-2 flex items-center gap-2">
                  <Button
                    onClick={() => {
                      void navigator.clipboard.writeText(payloadText(a));
                      setCopied(true);
                    }}
                  >
                    <i className="fas fa-copy mr-1.5" />{copied ? '已复制' : '复制 JSON'}
                  </Button>
                  <span className="text-xs text-ink-bg/40">重新导出：复制后粘贴到数据导出页</span>
                </div>
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}

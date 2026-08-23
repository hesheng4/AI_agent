// 统计审计页
import { useState, type FormEvent } from 'react';
import { PageHeader, Button, Card, Textarea, Loading, EmptyState } from '../components/ui';
import { statsApi } from '../api';

export default function StatsPage() {
  const [task, setTask] = useState<string>('audit');
  const [content, setContent] = useState('');
  const [journal, setJournal] = useState('nature');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!content.trim()) { setResult(null); return; }
    setLoading(true); setResult(null);
    try {
      const res = await statsApi.process({ task: task as 'audit' | 'draft' | 'check_test' | 'check_multiple_comparison', content: content.trim(), journal });
      setResult(res.result);
    } catch (e) { setResult({ error: e instanceof Error ? e.message : '处理失败' }); }
    finally { setLoading(false); }
  }

  return (
    <div>
      <PageHeader title="统计审计" subtitle="统计方法审计 · 起草 · 检验检查" icon="fa-chart-pie" />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">任务</span>
                <select value={task} onChange={e => setTask(e.target.value)}
                  className="cursor-pointer rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none focus:ring-1 focus:ring-copper/30">
                  <option value="audit" className="bg-ink-dark">审计</option>
                  <option value="draft" className="bg-ink-dark">起草</option>
                  <option value="check_test" className="bg-ink-dark">检验检查</option>
                  <option value="check_multiple_comparison" className="bg-ink-dark">多重比较</option>
                </select>
              </label>
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">期刊</span>
                <select value={journal} onChange={e => setJournal(e.target.value)}
                  className="cursor-pointer rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none focus:ring-1 focus:ring-copper/30">
                  <option value="nature" className="bg-ink-dark">Nature</option>
                  <option value="nat-comms" className="bg-ink-dark">Nat Comms</option>
                  <option value="science" className="bg-ink-dark">Science</option>
                </select>
              </label>
            </div>
            <Textarea label="统计内容" placeholder="粘贴统计方法描述或结果..."
              value={content} onChange={e => setContent(e.target.value)} rows={8} />
            <Button type="submit" loading={loading}><i className="fas fa-chart-pie mr-1.5" />处理</Button>
          </form>
        </Card>
        <Card>
          <h3 className="mb-3 text-sm font-medium text-ink-bg">结果</h3>
          {loading ? <Loading text="处理中" /> : result ? (
            <pre className="max-h-96 overflow-auto rounded-lg bg-ink-dark/60 p-3 text-xs text-ink-bg/70 whitespace-pre-wrap">{JSON.stringify(result, null, 2)}</pre>
          ) : <EmptyState icon="fa-chart-pie" title="统计方法审计" />}
        </Card>
      </div>
    </div>
  );
}

// 润色页 — 独立润色端点
import { useState, type FormEvent } from 'react';
import { PageHeader, Button, Card, Textarea, Loading, EmptyState } from '../components/ui';
import { polishingApi } from '../api';

export default function PolishingPage() {
  const [task, setTask] = useState<string>('polish');
  const [content, setContent] = useState('');
  const [journal, setJournal] = useState('nature');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!content.trim()) { setResult(null); return; }
    setLoading(true); setResult(null);
    try {
      const res = await polishingApi.process({ task: task as 'polish' | 'diagnose' | 'terminology' | 'latex_layout' | 'translate', content: content.trim(), journal });
      setResult(res.result);
    } catch (e) { setResult({ error: e instanceof Error ? e.message : '处理失败' }); }
    finally { setLoading(false); }
  }

  return (
    <div>
      <PageHeader title="专业润色" subtitle="Nature级润色 · 诊断 · 术语 · LaTeX排版 · 翻译" icon="fa-feather-pointed" />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">任务</span>
                <select value={task} onChange={e => setTask(e.target.value)}
                  className="cursor-pointer rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none focus:ring-1 focus:ring-copper/30">
                  <option value="polish" className="bg-ink-dark">润色</option>
                  <option value="diagnose" className="bg-ink-dark">诊断</option>
                  <option value="terminology" className="bg-ink-dark">术语</option>
                  <option value="latex_layout" className="bg-ink-dark">LaTeX 排版</option>
                  <option value="translate" className="bg-ink-dark">翻译</option>
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
            <Textarea label="内容" placeholder="粘贴需要润色的论文内容..."
              value={content} onChange={e => setContent(e.target.value)} rows={10} className="font-mono text-sm" />
            <Button type="submit" loading={loading}><i className="fas fa-feather-pointed mr-1.5" />处理</Button>
          </form>
        </Card>
        <Card>
          <h3 className="mb-3 text-sm font-medium text-ink-bg">结果</h3>
          {loading ? <Loading text="润色处理中" /> : result ? (
            <pre className="max-h-96 overflow-auto rounded-lg bg-ink-dark/60 p-3 text-xs text-ink-bg/70 whitespace-pre-wrap">{JSON.stringify(result, null, 2)}</pre>
          ) : <EmptyState icon="fa-feather-pointed" title="专业润色" />}
        </Card>
      </div>
    </div>
  );
}

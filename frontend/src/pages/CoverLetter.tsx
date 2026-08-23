// Cover Letter 页
import { useState, type FormEvent } from 'react';
import { PageHeader, Button, Card, Textarea, Loading, EmptyState } from '../components/ui';
import { coverApi } from '../api';

export default function CoverLetter() {
  const [task, setTask] = useState<string>('draft');
  const [content, setContent] = useState('');
  const [journal, setJournal] = useState('nature');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true); setResult(null);
    try {
      const res = await coverApi.process({ task: task as 'draft' | 'audit' | 'shorten', content: content.trim() || undefined, journal });
      setResult(res.result);
    } catch (e) { setResult({ error: e instanceof Error ? e.message : '处理失败' }); }
    finally { setLoading(false); }
  }

  return (
    <div>
      <PageHeader title="Cover Letter" subtitle="投稿信生成 · 审计 · 精简" icon="fa-envelope" />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">任务</span>
                <select value={task} onChange={e => setTask(e.target.value)}
                  className="cursor-pointer rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none focus:ring-1 focus:ring-copper/30">
                  <option value="draft" className="bg-ink-dark">起草</option>
                  <option value="audit" className="bg-ink-dark">审计</option>
                  <option value="shorten" className="bg-ink-dark">精简</option>
                </select>
              </label>
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">期刊</span>
                <select value={journal} onChange={e => setJournal(e.target.value)}
                  className="cursor-pointer rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none focus:ring-1 focus:ring-copper/30">
                  <option value="nature" className="bg-ink-dark">Nature</option>
                  <option value="nat-comms" className="bg-ink-dark">Nature Communications</option>
                  <option value="science" className="bg-ink-dark">Science</option>
                  <option value="cell" className="bg-ink-dark">Cell</option>
                </select>
              </label>
            </div>
            <Textarea label="稿件内容（可选）" placeholder="粘贴稿件摘要或全文..."
              value={content} onChange={e => setContent(e.target.value)} rows={8} />
            <Button type="submit" loading={loading}><i className="fas fa-envelope mr-1.5" />处理</Button>
          </form>
        </Card>
        <Card>
          <h3 className="mb-3 text-sm font-medium text-ink-bg">结果</h3>
          {loading ? <Loading text="处理中" /> : result ? (
            <pre className="max-h-96 overflow-auto rounded-lg bg-ink-dark/60 p-3 text-xs text-ink-bg/70 whitespace-pre-wrap">{JSON.stringify(result, null, 2)}</pre>
          ) : <EmptyState icon="fa-envelope" title="生成 Cover Letter" />}
        </Card>
      </div>
    </div>
  );
}

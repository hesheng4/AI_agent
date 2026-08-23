// 投稿打包页
import { useState, type FormEvent } from 'react';
import { PageHeader, Button, Card, Textarea, Loading, EmptyState } from '../components/ui';
import { submissionPackageApi } from '../api';

export default function SubmissionPackagePage() {
  const [task, setTask] = useState<string>('checklist');
  const [abstractText, setAbstractText] = useState('');
  const [journal, setJournal] = useState('nature');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true); setResult(null);
    try {
      const res = await submissionPackageApi.process({ task: task as 'checklist' | 'match_journal' | 'consistency_check', abstract: abstractText.trim() || undefined, journal });
      setResult(res.result);
    } catch (e) { setResult({ error: e instanceof Error ? e.message : '处理失败' }); }
    finally { setLoading(false); }
  }

  return (
    <div>
      <PageHeader title="投稿打包" subtitle="Checklist · 期刊匹配 · 一致性检查" icon="fa-box" />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">任务</span>
                <select value={task} onChange={e => setTask(e.target.value)}
                  className="cursor-pointer rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none focus:ring-1 focus:ring-copper/30">
                  <option value="checklist" className="bg-ink-dark">Checklist</option>
                  <option value="match_journal" className="bg-ink-dark">期刊匹配</option>
                  <option value="consistency_check" className="bg-ink-dark">一致性检查</option>
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
            <Textarea label="摘要" placeholder="粘贴论文摘要..."
              value={abstractText} onChange={e => setAbstractText(e.target.value)} rows={6} />
            <Button type="submit" loading={loading}><i className="fas fa-box mr-1.5" />处理</Button>
          </form>
        </Card>
        <Card>
          <h3 className="mb-3 text-sm font-medium text-ink-bg">结果</h3>
          {loading ? <Loading text="处理中" /> : result ? (
            <pre className="max-h-96 overflow-auto rounded-lg bg-ink-dark/60 p-3 text-xs text-ink-bg/70 whitespace-pre-wrap">{JSON.stringify(result, null, 2)}</pre>
          ) : <EmptyState icon="fa-box" title="投稿打包检查" />}
        </Card>
      </div>
    </div>
  );
}

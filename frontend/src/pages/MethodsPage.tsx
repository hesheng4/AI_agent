// 方法论写作页
import { useState, type FormEvent } from 'react';
import { PageHeader, Button, Card, Textarea, Loading, EmptyState } from '../components/ui';
import { methodsApi } from '../api';

export default function MethodsPage() {
  const [task, setTask] = useState<string>('audit');
  const [content, setContent] = useState('');
  const [studyType, setStudyType] = useState('wet-lab');
  const [journal, setJournal] = useState('nature');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true); setResult(null);
    try {
      const res = await methodsApi.process({ task: task as 'audit' | 'draft' | 'check_ethics' | 'remove_vague', content: content.trim() || undefined, study_type: studyType, journal });
      setResult(res.result);
    } catch (e) { setResult({ error: e instanceof Error ? e.message : '处理失败' }); }
    finally { setLoading(false); }
  }

  return (
    <div>
      <PageHeader title="方法论写作" subtitle="Methods 审计 · 起草 · 伦理检查" icon="fa-microscope" />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-3 gap-3">
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">任务</span>
                <select value={task} onChange={e => setTask(e.target.value)}
                  className="cursor-pointer rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none focus:ring-1 focus:ring-copper/30">
                  <option value="audit" className="bg-ink-dark">审计</option>
                  <option value="draft" className="bg-ink-dark">起草</option>
                  <option value="check_ethics" className="bg-ink-dark">伦理检查</option>
                  <option value="remove_vague" className="bg-ink-dark">消除模糊</option>
                </select>
              </label>
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">研究类型</span>
                <select value={studyType} onChange={e => setStudyType(e.target.value)}
                  className="cursor-pointer rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none focus:ring-1 focus:ring-copper/30">
                  <option value="wet-lab" className="bg-ink-dark">Wet Lab</option>
                  <option value="dry-lab" className="bg-ink-dark">Dry Lab</option>
                  <option value="clinical" className="bg-ink-dark">Clinical</option>
                  <option value="survey" className="bg-ink-dark">Survey</option>
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
            <Textarea label="方法论内容" placeholder="粘贴 Methods 部分..."
              value={content} onChange={e => setContent(e.target.value)} rows={8} />
            <Button type="submit" loading={loading}><i className="fas fa-microscope mr-1.5" />处理</Button>
          </form>
        </Card>
        <Card>
          <h3 className="mb-3 text-sm font-medium text-ink-bg">结果</h3>
          {loading ? <Loading text="处理中" /> : result ? (
            <pre className="max-h-96 overflow-auto rounded-lg bg-ink-dark/60 p-3 text-xs text-ink-bg/70 whitespace-pre-wrap">{JSON.stringify(result, null, 2)}</pre>
          ) : <EmptyState icon="fa-microscope" title="Methods 审计与优化" />}
        </Card>
      </div>
    </div>
  );
}

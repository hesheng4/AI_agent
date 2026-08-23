// 论文转专利页 — 论文→中国发明专利草稿
import { useState, type FormEvent } from 'react';
import { PageHeader, Button, Card, Textarea, Loading, EmptyState } from '../components/ui';
import { paperToPatentApi } from '../api';
import type { PatentDraftResult } from '../types';

export default function PaperToPatent() {
  const [content, setContent] = useState('');
  const [taskMode, setTaskMode] = useState<string>('full_draft');
  const [inventionType, setInventionType] = useState<string>('algorithm');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PatentDraftResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!content.trim() || content.trim().length < 100) { setResult(null); return; }
    setLoading(true); setResult(null); setError(null);
    try {
      const res = await paperToPatentApi.draft({ content: content.trim(), task_mode: taskMode as 'full_draft' | 'claims_only' | 'audit', invention_type: inventionType as 'algorithm' | 'apparatus' | 'process' | 'mixed' });
      setResult(res);
    } catch (e) { setError(e instanceof Error ? e.message : '处理失败'); }
    finally { setLoading(false); }
  }

  return (
    <div>
      <PageHeader title="论文转专利" subtitle="论文→中国发明专利草稿" icon="fa-award" />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <form onSubmit={handleSubmit} className="space-y-4">
            <Textarea label="论文内容" placeholder="粘贴论文全文（至少 100 字符）..."
              value={content} onChange={e => setContent(e.target.value)} rows={10} className="font-mono text-sm" />
            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">任务模式</span>
                <select value={taskMode} onChange={e => setTaskMode(e.target.value)}
                  className="cursor-pointer rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none focus:ring-1 focus:ring-copper/30">
                  <option value="full_draft" className="bg-ink-dark">完整草稿</option>
                  <option value="claims_only" className="bg-ink-dark">仅权利要求</option>
                  <option value="audit" className="bg-ink-dark">审计</option>
                </select>
              </label>
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">发明类型</span>
                <select value={inventionType} onChange={e => setInventionType(e.target.value)}
                  className="cursor-pointer rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none focus:ring-1 focus:ring-copper/30">
                  <option value="algorithm" className="bg-ink-dark">算法</option>
                  <option value="apparatus" className="bg-ink-dark">装置</option>
                  <option value="process" className="bg-ink-dark">方法</option>
                  <option value="mixed" className="bg-ink-dark">混合</option>
                </select>
              </label>
            </div>
            <Button type="submit" loading={loading}><i className="fas fa-award mr-1.5" />生成专利草稿</Button>
          </form>
        </Card>
        <Card>
          <h3 className="mb-3 text-sm font-medium text-ink-bg">专利草稿</h3>
          {loading ? <Loading text="生成专利草稿" /> : error ? (
            <div className="rounded-lg border border-red-400/30 bg-red-500/10 p-3 text-xs text-red-300 whitespace-pre-wrap">{error}</div>
          ) : result ? (
            <div className="space-y-4">
              {result.claims && (
                <div>
                  <h4 className="mb-1.5 text-xs font-medium text-copper-light"><i className="fas fa-list-ol mr-1" />权利要求</h4>
                  <div className="rounded-lg bg-ink-dark/60 p-3 text-xs text-ink-bg/70 whitespace-pre-wrap">{result.claims}</div>
                </div>
              )}
              {result.specification && (
                <div>
                  <h4 className="mb-1.5 text-xs font-medium text-copper-light"><i className="fas fa-file-lines mr-1" />说明书</h4>
                  <div className="max-h-60 overflow-auto rounded-lg bg-ink-dark/60 p-3 text-xs text-ink-bg/70 whitespace-pre-wrap">{result.specification}</div>
                </div>
              )}
              {result.abstract && (
                <div>
                  <h4 className="mb-1.5 text-xs font-medium text-copper-light"><i className="fas fa-align-left mr-1" />摘要</h4>
                  <div className="rounded-lg bg-ink-dark/60 p-3 text-xs text-ink-bg/70 whitespace-pre-wrap">{result.abstract}</div>
                </div>
              )}
            </div>
          ) : <EmptyState icon="fa-award" title="粘贴论文生成专利草稿" />}
        </Card>
      </div>
    </div>
  );
}

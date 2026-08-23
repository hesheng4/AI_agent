// 论文转PPT页 — 论文→Nature风格中文PPTX
import { useState, type FormEvent } from 'react';
import { PageHeader, Button, Card, Textarea, Loading, EmptyState } from '../components/ui';
import { paper2pptApi } from '../api';
import type { Paper2PPTResult, Paper2PPTRequest } from '../types';

export default function Paper2PPT() {
  const [content, setContent] = useState('');
  const [paperType, setPaperType] = useState('auto');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Paper2PPTResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!content.trim() || content.trim().length < 100) { setResult(null); return; }
    setLoading(true); setResult(null); setError(null);
    try {
      const res = await paper2pptApi.generate({ content: content.trim(), paper_type: paperType as Paper2PPTRequest['paper_type'] });
      setResult(res);
    } catch (e) { setError(e instanceof Error ? e.message : '处理失败'); }
    finally { setLoading(false); }
  }

  return (
    <div>
      <PageHeader title="论文转PPT" subtitle="论文→Nature风格中文PPTX" icon="fa-file-powerpoint" />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <form onSubmit={handleSubmit} className="space-y-4">
            <Textarea label="论文内容" placeholder="粘贴论文全文（至少 100 字符）..."
              value={content} onChange={e => setContent(e.target.value)} rows={10} className="font-mono text-sm" />
            <label className="block">
              <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">论文类型</span>
              <select value={paperType} onChange={e => setPaperType(e.target.value)}
                className="cursor-pointer rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none focus:ring-1 focus:ring-copper/30">
                <option value="auto" className="bg-ink-dark">自动检测</option>
                <option value="discovery" className="bg-ink-dark">Discovery</option>
                <option value="methods" className="bg-ink-dark">Methods</option>
                <option value="resource" className="bg-ink-dark">Resource</option>
                <option value="clinical" className="bg-ink-dark">Clinical</option>
                <option value="materials" className="bg-ink-dark">Materials</option>
                <option value="review" className="bg-ink-dark">Review</option>
              </select>
            </label>
            <Button type="submit" loading={loading}><i className="fas fa-file-powerpoint mr-1.5" />生成 PPT</Button>
          </form>
        </Card>
        <Card>
          <h3 className="mb-3 text-sm font-medium text-ink-bg">生成结果</h3>
          {loading ? <Loading text="生成 PPTX 中" /> : error ? (
            <div className="rounded-lg border border-red-400/30 bg-red-500/10 p-3 text-xs text-red-300 whitespace-pre-wrap">{error}</div>
          ) : result ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-xs text-ink-bg/60">
                <span className="rounded bg-copper/10 px-2 py-1 text-copper-light">{result.slide_count} 张幻灯片</span>
                {result.pptx_path && <span className="font-mono">{result.pptx_path}</span>}
              </div>
              {result.slides?.map((s, i) => (
                <div key={i} className="rounded-lg border border-copper/10 bg-ink-dark/40 p-3">
                  <h4 className="text-xs font-medium text-copper-light">Slide {i + 1}: {s.title}</h4>
                  <p className="mt-1 text-xs text-ink-bg/60">{s.content}</p>
                </div>
              ))}
            </div>
          ) : <EmptyState icon="fa-file-powerpoint" title="粘贴论文生成 PPT" />}
        </Card>
      </div>
    </div>
  );
}

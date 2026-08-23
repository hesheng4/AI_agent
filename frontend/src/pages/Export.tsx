// 导出页 — CSV · JSON · BibTeX · RIS · Markdown
import { useState } from 'react';
import { PageHeader, Button, Card, Textarea, Input, ErrorBanner } from '../components/ui';
import { exportApi } from '../api';

type TabKey = 'csv' | 'json' | 'bibtex' | 'ris' | 'markdown';

const TABS: Array<{ key: TabKey; label: string; icon: string; desc: string }> = [
  { key: 'csv', label: 'CSV', icon: 'fa-file-csv', desc: '通用表格格式，兼容 Excel' },
  { key: 'json', label: 'JSON', icon: 'fa-file-code', desc: '结构化数据格式' },
  { key: 'bibtex', label: 'BibTeX', icon: 'fa-book', desc: 'LaTeX 参考文献格式' },
  { key: 'ris', label: 'RIS', icon: 'fa-file-lines', desc: '文献管理软件通用格式' },
  { key: 'markdown', label: 'Markdown', icon: 'fa-markdown', desc: 'Markdown 表格格式' },
];

export default function ExportPage() {
  const [tab, setTab] = useState<TabKey>('csv');
  const [dataText, setDataText] = useState('');
  const [filename, setFilename] = useState('export');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  function parseData(): Array<Record<string, unknown>> {
    try {
      const parsed = JSON.parse(dataText);
      return Array.isArray(parsed) ? parsed : [parsed];
    } catch {
      return [];
    }
  }

  async function handleExport() {
    const data = parseData();
    if (data.length === 0) {
      setError('请输入有效的 JSON 数据（数组格式）');
      return;
    }
    setLoading(true); setError(''); setSuccess('');
    try {
      let blob: Blob;
      if (tab === 'bibtex' || tab === 'ris') {
        blob = await (tab === 'bibtex' ? exportApi.bibtex : exportApi.ris)({ papers: data, filename });
      } else {
        const apiFn = tab === 'csv' ? exportApi.csv : tab === 'json' ? exportApi.json : exportApi.markdown;
        blob = await apiFn({ data, filename });
      }
      // 下载文件
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const ext = tab === 'bibtex' ? 'bib' : tab === 'ris' ? 'ris' : tab === 'markdown' ? 'md' : tab;
      a.download = `${filename}.${ext}`;
      a.click();
      URL.revokeObjectURL(url);
      setSuccess(`已导出 ${filename}.${ext}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : '导出失败');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <PageHeader title="数据导出" subtitle="CSV · JSON · BibTeX · RIS · Markdown" icon="fa-download" />

      <div className="mb-6 flex flex-wrap gap-2">
        {TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`flex cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-all ${
              tab === t.key
                ? 'border-copper bg-copper/10 text-copper-light'
                : 'border-copper/15 text-ink-bg/50 hover:border-copper/30 hover:text-ink-bg'
            }`}>
            <i className={`fas ${t.icon}`} />{t.label}
          </button>
        ))}
      </div>

      <Card className="mb-6">
        <div className="space-y-4">
          <div className="flex items-end gap-4">
            <div className="flex-1">
              <Input label="文件名" icon="fa-file" value={filename} onChange={e => setFilename(e.target.value)} />
            </div>
            <div className="pb-0.5 text-xs text-ink-bg/60">.{tab === 'bibtex' ? 'bib' : tab === 'ris' ? 'ris' : tab === 'markdown' ? 'md' : tab}</div>
          </div>
          <Textarea
            label={`数据（JSON 数组格式）${(tab === 'bibtex' || tab === 'ris') ? ' — 每项为文献对象' : ''}`}
            placeholder={tab === 'bibtex' || tab === 'ris'
              ? '[\n  { "title": "Paper Title", "authors": ["Author"], "year": 2024, "journal": "Nature" }\n]'
              : '[\n  { "column1": "value1", "column2": "value2" }\n]'}
            value={dataText}
            onChange={e => setDataText(e.target.value)}
            rows={10}
            className="font-mono text-sm"
          />
          <div className="flex items-center gap-3">
            <Button onClick={handleExport} loading={loading}>
              <i className="fas fa-download mr-1.5" />导出 {TABS.find(t => t.key === tab)?.label}
            </Button>
            {success && <span className="text-xs text-jade">{success}</span>}
          </div>
        </div>
      </Card>

      {error && <ErrorBanner message={error} />}

      <Card>
        <h3 className="mb-2 text-sm font-medium text-ink-bg">
          <i className="fas fa-info-circle mr-1.5 text-copper-light" />
          格式说明
        </h3>
        <p className="text-xs text-ink-bg/50">
          {TABS.find(t => t.key === tab)?.desc}。输入 JSON 数组，每个对象代表一条记录。
          {(tab === 'bibtex' || tab === 'ris') && '文献字段应包含 title、authors、year、journal 等。'}
        </p>
      </Card>
    </div>
  );
}

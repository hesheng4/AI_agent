// 引用管理页 — 添加引用 · 验证引用 · 格式化参考文献
import { useState, type FormEvent } from 'react';
import { motion } from 'motion/react';
import { PageHeader, Button, Card, Textarea, Loading, ErrorBanner } from '../components/ui';
import { citationApi } from '../api';
import type { AddCitationsResult, VerifyCitationsResult, FormatReferencesResult } from '../types';

type TabKey = 'add' | 'verify' | 'format';

export default function CitationPage() {
  const [tab, setTab] = useState<TabKey>('add');
  const [content, setContent] = useState('');
  const [journalScope, setJournalScope] = useState('general');
  const [referencesText, setReferencesText] = useState('');
  const [style, setStyle] = useState('apa');

  const [addResult, setAddResult] = useState<AddCitationsResult | null>(null);
  const [verifyResult, setVerifyResult] = useState<VerifyCitationsResult | null>(null);
  const [formatResult, setFormatResult] = useState<FormatReferencesResult | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleAdd(e: FormEvent) {
    e.preventDefault();
    if (!content.trim()) {
      setError('请输入论文内容');
      return;
    }
    setLoading(true);
    setError('');
    setAddResult(null);
    try {
      const res = await citationApi.add({
        content: content.trim(),
        journal_scope: journalScope as 'nature' | 'science' | 'cell' | 'general',
      });
      setAddResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : '添加引用失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleVerify(e: FormEvent) {
    e.preventDefault();
    if (!content.trim()) {
      setError('请输入论文内容');
      return;
    }
    setLoading(true);
    setError('');
    setVerifyResult(null);
    const refs = referencesText.split('\n').map(l => l.trim()).filter(Boolean);
    try {
      const res = await citationApi.verify({
        content: content.trim(),
        references: refs.length > 0 ? refs : undefined,
      });
      setVerifyResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : '验证引用失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleFormat(e: FormEvent) {
    e.preventDefault();
    const refs = referencesText.split('\n').map(l => l.trim()).filter(Boolean);
    if (refs.length === 0) {
      setError('请输入至少一条参考文献');
      return;
    }
    setLoading(true);
    setError('');
    setFormatResult(null);
    try {
      const res = await citationApi.formatReferences({
        references: refs,
        style: style as 'apa' | 'mla' | 'chicago' | 'ieee' | 'vancouver' | 'harvard' | 'gbt7714',
      });
      setFormatResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : '格式化失败');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <PageHeader title="引用管理" subtitle="添加引用 · 验证 · 格式化" icon="fa-quote-right" />

      <div className="mb-6 flex gap-6 border-b border-copper/10">
        {([
          { key: 'add' as TabKey, label: '添加引用', icon: 'fa-plus' },
          { key: 'verify' as TabKey, label: '验证引用', icon: 'fa-check' },
          { key: 'format' as TabKey, label: '格式化', icon: 'fa-palette' },
        ]).map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex cursor-pointer items-center gap-2 px-1 pb-3 text-sm transition-colors ${
              tab === t.key
                ? 'border-b-2 border-copper text-copper-light'
                : 'border-b-2 border-transparent text-ink-bg/50 hover:text-ink-bg'
            }`}
          >
            <i className={`fas ${t.icon} text-xs`} />
            {t.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4">
          <ErrorBanner message={error} />
        </div>
      )}

      {tab === 'add' && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="mb-6">
            <form onSubmit={handleAdd} className="space-y-4">
              <Textarea
                label="论文内容"
                placeholder="粘贴需要添加引用的论文内容..."
                value={content}
                onChange={e => setContent(e.target.value)}
                rows={8}
              />
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">期刊范围</span>
                <select
                  value={journalScope}
                  onChange={e => setJournalScope(e.target.value)}
                  className="cursor-pointer rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none focus:ring-1 focus:ring-copper/30"
                >
                  <option value="general" className="bg-ink-dark">General</option>
                  <option value="nature" className="bg-ink-dark">Nature</option>
                  <option value="science" className="bg-ink-dark">Science</option>
                  <option value="cell" className="bg-ink-dark">Cell</option>
                </select>
              </label>
              <Button type="submit" loading={loading}>
                <i className="fas fa-plus mr-1.5" />
                自动添加引用
              </Button>
            </form>
          </Card>
          {loading && <Loading text="分析内容，添加引用" />}
          {addResult && (
            <div className="space-y-4">
              <Card>
                <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg">
                  <i className="fas fa-quote-right text-copper-light" />
                  标注文本
                </h3>
                <div className="rounded-lg bg-ink-dark/60 p-4 text-sm text-ink-bg/80 whitespace-pre-wrap">
                  {addResult.annotated_text}
                </div>
              </Card>
              {addResult.citations && (
                <Card>
                  <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg">
                    <i className="fas fa-book text-copper-light" />
                    引用列表
                  </h3>
                  <div className="rounded-lg bg-ink-dark/60 p-3 text-xs text-ink-bg/70 whitespace-pre-wrap">
                    {addResult.citations}
                  </div>
                </Card>
              )}
              {addResult.segments && (
                <Card>
                  <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg">
                    <i className="fas fa-list text-copper-light" />
                    可引用段落
                  </h3>
                  <div className="rounded-lg bg-ink-dark/60 p-3 text-xs text-ink-bg/70 whitespace-pre-wrap">
                    {addResult.segments}
                  </div>
                </Card>
              )}
            </div>
          )}
        </motion.div>
      )}

      {tab === 'verify' && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="mb-6">
            <form onSubmit={handleVerify} className="space-y-4">
              <Textarea
                label="论文内容"
                placeholder="粘贴论文内容..."
                value={content}
                onChange={e => setContent(e.target.value)}
                rows={6}
              />
              <Textarea
                label="参考文献列表（每行一条，可选）"
                placeholder="Smith et al. 2023...&#10;Wang et al. 2024..."
                value={referencesText}
                onChange={e => setReferencesText(e.target.value)}
                rows={4}
              />
              <Button type="submit" loading={loading}>
                <i className="fas fa-check mr-1.5" />
                验证引用
              </Button>
            </form>
          </Card>
          {loading && <Loading text="验证引用匹配度" />}
          {verifyResult && (
            <Card>
              <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg">
                <i className="fas fa-clipboard-check text-copper-light" />
                验证结果
              </h3>
              <div className="rounded-lg bg-ink-dark/60 p-4 text-sm text-ink-bg/80 whitespace-pre-wrap">
                {verifyResult.verification}
              </div>
              <div className="mt-3 text-[11px] text-ink-bg/60">
                参考文献数: {verifyResult.total_references}
              </div>
            </Card>
          )}
        </motion.div>
      )}

      {tab === 'format' && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="mb-6">
            <form onSubmit={handleFormat} className="space-y-4">
              <Textarea
                label="参考文献列表（每行一条）"
                placeholder="Smith, J. et al. (2023). Title...&#10;Wang, L. et al. (2024). Title..."
                value={referencesText}
                onChange={e => setReferencesText(e.target.value)}
                rows={6}
              />
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">格式风格</span>
                <select
                  value={style}
                  onChange={e => setStyle(e.target.value)}
                  className="cursor-pointer rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none focus:ring-1 focus:ring-copper/30"
                >
                  <option value="apa" className="bg-ink-dark">APA</option>
                  <option value="mla" className="bg-ink-dark">MLA</option>
                  <option value="chicago" className="bg-ink-dark">Chicago</option>
                  <option value="ieee" className="bg-ink-dark">IEEE</option>
                  <option value="vancouver" className="bg-ink-dark">Vancouver</option>
                  <option value="harvard" className="bg-ink-dark">Harvard</option>
                  <option value="gbt7714" className="bg-ink-dark">GB/T 7714</option>
                </select>
              </label>
              <Button type="submit" loading={loading}>
                <i className="fas fa-palette mr-1.5" />
                格式化
              </Button>
            </form>
          </Card>
          {loading && <Loading text="格式化参考文献" />}
          {formatResult && (
            <Card>
              <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg">
                <i className="fas fa-palette text-copper-light" />
                格式化结果
              </h3>
              <div className="rounded-lg bg-ink-dark/60 p-4 text-sm text-ink-bg/80 whitespace-pre-wrap">
                {formatResult.formatted_references}
              </div>
              <div className="mt-3 flex gap-3 text-[11px] text-ink-bg/60">
                <span>风格: {formatResult.style}</span>
                <span>条数: {formatResult.total_references}</span>
              </div>
            </Card>
          )}
        </motion.div>
      )}
    </div>
  );
}

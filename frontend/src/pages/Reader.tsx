// 精读页 — 全文中英对照 Markdown Reader
import { useState, type FormEvent } from 'react';
import { motion } from 'motion/react';
import { PageHeader, Button, Card, Input, Textarea, Loading, EmptyState, ErrorBanner } from '../components/ui';
import { readerApi, literatureApi } from '../api';
import type { ReadFullResponse, Paper } from '../types';

type TabKey = 'paste' | 'fromSearch';

export default function Reader() {
  const [tab, setTab] = useState<TabKey>('paste');

  // 粘贴模式
  const [content, setContent] = useState('');
  const [sourceFormat, setSourceFormat] = useState<string>('auto');
  const [journal, setJournal] = useState<string>('generic');
  const [language, setLanguage] = useState<string>('zh-to-en');

  // 搜索模式
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<Paper[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState('');

  const [result, setResult] = useState<ReadFullResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleRead(e: FormEvent) {
    e.preventDefault();
    if (!content.trim() || content.trim().length < 50) {
      setError('内容至少 50 个字符');
      return;
    }
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const res = await readerApi.readFull({
        content: content.trim(),
        source_format: sourceFormat as ReadFullResponse extends { source_map: string } ? never : never,
        journal: journal as 'nature' | 'nat-comms' | 'generic',
        language: language as 'zh-to-en' | 'en',
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : '精读失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleSearch() {
    if (!searchQuery.trim()) return;
    setSearchLoading(true);
    setSearchError('');
    setSearchResults([]);
    try {
      const res = await literatureApi.search({ query: searchQuery.trim() });
      setSearchResults(res.papers || []);
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : '搜索失败');
    } finally {
      setSearchLoading(false);
    }
  }

  function handleSelectPaper(paper: Paper) {
    const text = [
      paper.title,
      paper.authors?.join(', '),
      paper.abstract,
    ].filter(Boolean).join('\n\n');
    setContent(text);
    setTab('paste');
  }

  return (
    <div>
      <PageHeader
        title="论文精读"
        subtitle="全文中英对照 · Markdown Reader"
        icon="fa-book-open"
      />

      <div className="mb-6 flex gap-6 border-b border-copper/10">
        {([
          { key: 'paste' as TabKey, label: '粘贴全文', icon: 'fa-paste' },
          { key: 'fromSearch' as TabKey, label: '从检索选择', icon: 'fa-search' },
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

      {/* 从检索选择 Tab */}
      {tab === 'fromSearch' && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="mb-4">
            <div className="flex gap-3">
              <div className="flex-1">
                <Input
                  icon="fa-search"
                  placeholder="搜索论文..."
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleSearch()}
                />
              </div>
              <Button onClick={handleSearch} loading={searchLoading}>
                <i className="fas fa-search mr-1.5" />搜索
              </Button>
            </div>
          </Card>
          {searchError && <div className="mb-4"><ErrorBanner message={searchError} /></div>}
          {searchLoading && <Loading text="搜索中" />}
          {!searchLoading && searchResults.length > 0 && (
            <div className="space-y-2">
              {searchResults.map((paper, i) => (
                <Card key={paper.paper_id || paper.id || i} className="p-4 transition-colors hover:border-copper/30">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-serif text-sm text-ink-bg">{paper.title}</h3>
                      {paper.authors && (
                        <p className="mt-1 text-xs text-ink-bg/50 truncate">
                          {paper.authors.slice(0, 3).join(', ')}
                        </p>
                      )}
                      {paper.abstract && (
                        <p className="mt-1 line-clamp-2 text-xs text-ink-bg/60">{paper.abstract}</p>
                      )}
                    </div>
                    <Button variant="secondary" size="sm" onClick={() => handleSelectPaper(paper)}>
                      <i className="fas fa-book-open mr-1" />精读
                    </Button>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </motion.div>
      )}

      {/* 粘贴全文 Tab */}
      {tab === 'paste' && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="mb-6">
            <form onSubmit={handleRead} className="space-y-4">
              <Textarea
                label="论文全文"
                placeholder="粘贴论文全文内容（至少 50 字符）..."
                value={content}
                onChange={e => setContent(e.target.value)}
                rows={10}
                className="font-mono text-sm"
              />
              <div className="flex flex-wrap gap-4">
                <label className="block">
                  <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">源格式</span>
                  <select
                    value={sourceFormat}
                    onChange={e => setSourceFormat(e.target.value)}
                    className="cursor-pointer rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none focus:ring-1 focus:ring-copper/30"
                  >
                    <option value="auto" className="bg-ink-dark">自动检测</option>
                    <option value="pdf-text" className="bg-ink-dark">PDF 文本</option>
                    <option value="scanned-pdf" className="bg-ink-dark">扫描 PDF</option>
                    <option value="html" className="bg-ink-dark">HTML</option>
                    <option value="doi-arxiv" className="bg-ink-dark">DOI/arXiv</option>
                    <option value="pasted-text" className="bg-ink-dark">粘贴文本</option>
                  </select>
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">期刊</span>
                  <select
                    value={journal}
                    onChange={e => setJournal(e.target.value)}
                    className="cursor-pointer rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none focus:ring-1 focus:ring-copper/30"
                  >
                    <option value="generic" className="bg-ink-dark">通用</option>
                    <option value="nature" className="bg-ink-dark">Nature</option>
                    <option value="nat-comms" className="bg-ink-dark">Nature Communications</option>
                  </select>
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">语言</span>
                  <select
                    value={language}
                    onChange={e => setLanguage(e.target.value)}
                    className="cursor-pointer rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none focus:ring-1 focus:ring-copper/30"
                  >
                    <option value="zh-to-en" className="bg-ink-dark">中→英对照</option>
                    <option value="en" className="bg-ink-dark">英文</option>
                  </select>
                </label>
              </div>
              <Button type="submit" loading={loading} className="w-full sm:w-auto">
                <i className="fas fa-book-open mr-1.5" />
                开始精读
              </Button>
            </form>
          </Card>

          {error && <div className="mb-4"><ErrorBanner message={error} /></div>}
          {loading && <Loading text="全文精读分析中" />}

          {result && (
            <div className="space-y-4">
              {/* 统计 */}
              {result.stats && Object.keys(result.stats).length > 0 && (
                <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                  {Object.entries(result.stats).map(([k, v]) => (
                    <Card key={k} className="p-3">
                      <div className="text-[10px] text-ink-bg/60">{k}</div>
                      <div className="mt-0.5 font-serif text-sm text-ink-bg">{String(v)}</div>
                    </Card>
                  ))}
                </div>
              )}

              {/* 精读结果 */}
              <Card>
                <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg">
                  <i className="fas fa-book-open text-copper-light" />
                  精读 Markdown
                </h3>
                <div className="prose prose-invert max-w-none rounded-lg bg-ink-dark/60 p-4 text-sm text-ink-bg/80 whitespace-pre-wrap">
                  {result.paper_md}
                </div>
              </Card>

              {/* 术语表 */}
              {result.terminology_ledger && (
                <Card>
                  <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg">
                    <i className="fas fa-book text-copper-light" />
                    术语表
                  </h3>
                  <div className="rounded-lg bg-ink-dark/60 p-3 text-xs text-ink-bg/70 whitespace-pre-wrap">
                    {result.terminology_ledger}
                  </div>
                </Card>
              )}

              {/* 翻译注释 */}
              {result.translation_notes && (
                <Card>
                  <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg">
                    <i className="fas fa-sticky-note text-copper-light" />
                    翻译注释
                  </h3>
                  <div className="rounded-lg bg-ink-dark/60 p-3 text-xs text-ink-bg/70 whitespace-pre-wrap">
                    {result.translation_notes}
                  </div>
                </Card>
              )}

              {/* Source Map */}
              {result.source_map && (
                <Card>
                  <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg">
                    <i className="fas fa-map text-copper-light" />
                    源映射
                  </h3>
                  <pre className="max-h-60 overflow-auto rounded-lg bg-ink-dark/60 p-3 text-xs text-ink-bg/70">
                    {result.source_map}
                  </pre>
                </Card>
              )}
            </div>
          )}

          {!loading && !result && (
            <EmptyState
              icon="fa-book-open"
              title="粘贴论文全文开始精读"
              hint="支持 PDF 文本、HTML、arXiv 等格式，自动生成中英对照 Markdown"
            />
          )}
        </motion.div>
      )}
    </div>
  );
}

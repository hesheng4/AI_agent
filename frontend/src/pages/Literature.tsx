// 文献检索页 — SaaS Dashboard 风格
import { useState, type FormEvent } from 'react';
import { motion } from 'motion/react';
import { Input, Button, Card, Loading, EmptyState, ErrorBanner } from '../components/ui';
import { literatureApi, libraryApi } from '../api';
import type { Paper } from '../types';

export default function Literature() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [results, setResults] = useState<Paper[]>([]);
  const [suggestions, setSuggestions] = useState('');
  const [total, setTotal] = useState(0);
  const [collecting, setCollecting] = useState<string | null>(null);
  const [collected, setCollected] = useState<Set<string>>(new Set());

  async function handleSearch(e: FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError('');
    setResults([]);
    try {
      const res = await literatureApi.search({ query: query.trim() });
      setResults(res.papers || []);
      setSuggestions(res.suggestions || '');
      setTotal(res.total_results || 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : '搜索失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleCollect(paper: Paper) {
    const paperId = paper.paper_id || paper.id || paper.title;
    if (!paperId) return;
    setCollecting(paperId);
    try {
      await libraryApi.addPaper({
        paper_id: paperId,
        title: paper.title,
        authors: paper.authors || [],
        abstract: paper.abstract,
        year: paper.year,
        journal: paper.journal,
        url: paper.url,
        source: paper.source || 'search',
      });
      setCollected(prev => new Set(prev).add(paperId));
    } catch (err) {
      setError(err instanceof Error ? err.message : '收藏失败');
    } finally {
      setCollecting(null);
    }
  }

  const hasSearched = results.length > 0 || loading || error;

  return (
    <div className="mx-auto max-w-5xl">
      {/* ===== 搜索主区 — 居中书本图标 + 分层文字 ===== */}
      {!hasSearched && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="flex flex-col items-center pt-8 pb-12"
        >
          {/* 居中书本图标 */}
          <div className="relative mb-6">
            <div className="absolute inset-0 rounded-full bg-primary/10 blur-2xl" />
            <div className="relative flex h-20 w-20 items-center justify-center rounded-2xl border border-primary-border bg-primary-muted">
              <i className="fas fa-book-open text-3xl text-primary" />
            </div>
          </div>

          <h1 className="mb-2 text-center text-2xl font-bold text-txt sm:text-3xl">
            文献智能检索
          </h1>

          <p className="text-center text-xs text-txt-muted sm:text-sm">
            聚合 Semantic Scholar · arXiv · Crossref 多源数据，AI 辅助筛选与摘要
          </p>
        </motion.div>
      )}

      {/* ===== 搜索栏 ===== */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
        className={`search-glow mb-6 rounded-xl border border-border bg-surface p-4 shadow-card ${hasSearched ? '' : 'shadow-elevated'}`}
      >
        <form onSubmit={handleSearch} className="flex flex-col gap-3 sm:flex-row">
          <div className="flex-1">
            <Input
              icon="fa-search"
              placeholder="输入关键词，如 transformer medical imaging"
              value={query}
              onChange={e => setQuery(e.target.value)}
              className="h-12 text-base"
              autoFocus={!hasSearched}
            />
          </div>
          <Button type="submit" loading={loading} className="h-12 shrink-0 sm:px-8">
            <i className="fas fa-search mr-1.5" />
            搜索
          </Button>
        </form>
        {suggestions && (
          <p className="mt-3 text-xs text-txt-muted">
            <i className="fas fa-lightbulb mr-1 text-primary/60" />
            {suggestions}
          </p>
        )}
      </motion.div>

      {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

      {/* 结果统计 */}
      {results.length > 0 && (
        <p className="mb-4 text-xs text-txt-muted">
          共找到 <span className="font-medium text-primary">{total}</span> 条结果，显示前 {results.length} 条
        </p>
      )}

      {/* 加载中 */}
      {loading && <Loading text="正在检索文献" />}

      {/* 空状态 — 搜索后无结果 */}
      {!loading && results.length === 0 && error && (
        <EmptyState
          icon="fa-search"
          title="未找到相关文献"
          hint="尝试更换关键词或扩大搜索范围"
        />
      )}

      {/* 初始空状态 — 快捷搜索建议 */}
      {!hasSearched && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="flex flex-wrap items-center justify-center gap-2"
        >
          <span className="text-xs text-txt-light">快捷搜索：</span>
          {['large language model', 'CRISPR gene editing', 'quantum computing', 'climate change'].map(tag => (
            <button
              key={tag}
              onClick={() => setQuery(tag)}
              className="cursor-pointer rounded-full border border-border bg-bg-muted px-3 py-1 text-xs text-txt-muted transition-colors hover:border-primary-border hover:bg-primary-muted hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-ring"
            >
              {tag}
            </button>
          ))}
        </motion.div>
      )}

      {/* 结果列表 */}
      {!loading && results.length > 0 && (
        <div className="space-y-3">
          {results.map((paper, i) => {
            const paperId = paper.paper_id || paper.id || paper.title;
            const isCollected = collected.has(paperId);
            return (
              <motion.div
                key={paperId || i}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
              >
                <Card className="transition-colors hover:border-border-strong">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <h3 className="text-base font-medium text-txt hover:text-primary">
                        {paper.url ? (
                          <a href={paper.url} target="_blank" rel="noopener noreferrer" className="hover:underline">
                            {paper.title}
                          </a>
                        ) : (
                          paper.title
                        )}
                      </h3>
                      {paper.authors && paper.authors.length > 0 && (
                        <p className="mt-1 text-xs text-txt-muted">
                          {paper.authors.slice(0, 5).join(', ')}
                          {paper.authors.length > 5 && ' et al.'}
                        </p>
                      )}
                      {paper.abstract && (
                        <p className="mt-2 line-clamp-3 text-sm text-txt-muted">{paper.abstract}</p>
                      )}
                      <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-txt-light">
                        {paper.year && <span><i className="far fa-calendar mr-1" />{paper.year}</span>}
                        {paper.journal && <span><i className="far fa-newspaper mr-1" />{paper.journal}</span>}
                        {paper.citation_count !== undefined && (
                          <span><i className="fas fa-quote-right mr-1" />{paper.citation_count}</span>
                        )}
                        {paper.source && (
                          <span className="rounded bg-primary-muted px-1.5 py-0.5 text-primary">{paper.source}</span>
                        )}
                      </div>
                    </div>
                    <Button
                      variant={isCollected ? 'secondary' : 'primary'}
                      size="sm"
                      loading={collecting === paperId}
                      onClick={() => handleCollect(paper)}
                      disabled={isCollected}
                      className="shrink-0"
                    >
                      <i className={`fas ${isCollected ? 'fa-check' : 'fa-bookmark'} mr-1.5`} />
                      {isCollected ? '已收藏' : '收藏'}
                    </Button>
                  </div>
                </Card>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}

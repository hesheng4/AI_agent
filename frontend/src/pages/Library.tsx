// 文献库页 — 收藏列表 + 分类/标签管理 + 统计概览 + 分页排序批量操作
// P0 优化：TanStack Query 替代手写 useState+useEffect+loading/error
import { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { PageHeader, Button, Card, Loading, EmptyState, ErrorBanner, Input } from '../components/ui';
import ConfirmDialog from '../components/ConfirmDialog';
import { exportApi } from '../api';
import { usePapers, useCategories, useTags, useLibraryStats, useUpdatePaper, useDeletePaper, useCreateCategory, useCreateTag, useDeleteCategory, useDeleteTag } from '../hooks/useLibrary';
import type { Paper } from '../types';

type SortKey = 'title' | 'year' | 'citation_count' | 'created_at';
type SortDir = 'asc' | 'desc';

const PAGE_SIZE = 20;

export default function Library() {
  const [filter, setFilter] = useState<{ category?: string; tag?: string; favorite?: number; search?: string }>({});
  const [showAddCategory, setShowAddCategory] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState('');
  const [showAddTag, setShowAddTag] = useState(false);
  const [newTagName, setNewTagName] = useState('');

  // 分页
  const [page, setPage] = useState(1);

  // 排序
  const [sortKey, setSortKey] = useState<SortKey>('created_at');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  // 批量操作
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [batchLoading, setBatchLoading] = useState(false);

  // 确认对话框
  const [confirmState, setConfirmState] = useState<{ open: boolean; title: string; message: string; onConfirm: () => void }>({ open: false, title: '', message: '', onConfirm: () => {} });
  const showConfirm = (title: string, message: string, onConfirm: () => void) => setConfirmState({ open: true, title, message, onConfirm });

  // ===== TanStack Query 数据层（替代手写 useState+useEffect+loadAll） =====
  const offset = (page - 1) * PAGE_SIZE;
  const { data: rawPapers, isLoading: papersLoading, error: papersError } = usePapers({ ...filter, limit: PAGE_SIZE, offset });
  const { data: categories = [] } = useCategories();
  const { data: tags = [] } = useTags();
  const { data: stats } = useLibraryStats();

  const updatePaper = useUpdatePaper();
  const deletePaper = useDeletePaper();
  const createCategory = useCreateCategory();
  const createTag = useCreateTag();

  // 客户端排序
  const papers = useMemo(() => {
    if (!rawPapers) return [];
    return [...rawPapers].sort((a, b) => {
      const av = a[sortKey] ?? '';
      const bv = b[sortKey] ?? '';
      const cmp = String(av).localeCompare(String(bv), undefined, { numeric: true });
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [rawPapers, sortKey, sortDir]);

  const total = stats?.total_papers || rawPapers?.length || 0;
  const loading = papersLoading;
  const error = papersError ? (papersError instanceof Error ? papersError.message : '加载失败') : '';

  useEffect(() => { setPage(1); }, [filter]);

  function toggleSelect(id: string) {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    if (selected.size === papers.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(papers.map(p => p.id || p.paper_id || '').filter(Boolean)));
    }
  }

  function handleBatchDelete() {
    if (selected.size === 0) return;
    showConfirm('批量删除', `确认删除 ${selected.size} 篇文献？`, async () => {
      setBatchLoading(true);
      try {
        await Promise.all(Array.from(selected).map(id => deletePaper.mutateAsync(id)));
        setSelected(new Set());
      } catch (err) {
        // deletePaper 的 onSuccess 已自动失效缓存
      } finally {
        setBatchLoading(false);
      }
    });
  }

  async function handleBatchExport() {
    if (selected.size === 0) return;
    const selectedPapers = papers.filter(p => {
      const id = p.id || p.paper_id || '';
      return selected.has(id);
    });
    try {
      const blob = await exportApi.json({
        data: selectedPapers as unknown as Array<Record<string, unknown>>,
        filename: 'selected_papers',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'selected_papers.json';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      // 导出失败静默处理（非关键路径）
    }
  }

  async function handleToggleFavorite(paper: Paper) {
    const id = paper.id || paper.paper_id;
    if (!id) return;
    updatePaper.mutate({ id, data: { is_favorite: paper.is_favorite ? 0 : 1 } });
  }

  function handleDelete(paper: Paper) {
    const id = paper.id || paper.paper_id;
    if (!id) return;
    showConfirm('删除文献', `确认删除「${paper.title}」？`, async () => {
      deletePaper.mutate(id);
    });
  }

  async function handleAddCategory() {
    if (!newCategoryName.trim()) return;
    createCategory.mutate({ name: newCategoryName.trim() }, {
      onSuccess: () => { setNewCategoryName(''); setShowAddCategory(false); },
    });
  }

  async function handleAddTag() {
    if (!newTagName.trim()) return;
    createTag.mutate({ name: newTagName.trim() }, {
      onSuccess: () => { setNewTagName(''); setShowAddTag(false); },
    });
  }

  const deleteCategory = useDeleteCategory();
  const deleteTag = useDeleteTag();

  function handleDeleteCategory(id: string, name: string) {
    showConfirm('删除分类', `确认删除分类「${name}」？`, async () => {
      deleteCategory.mutate(id, {
        onSuccess: () => { if (filter.category === name) setFilter({ ...filter, category: undefined }); },
      });
    });
  }

  function handleDeleteTag(id: string, name: string) {
    showConfirm('删除标签', `确认删除标签「${name}」？`, async () => {
      deleteTag.mutate(id, {
        onSuccess: () => { if (filter.tag === name) setFilter({ ...filter, tag: undefined }); },
      });
    });
  }

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const allSelected = papers.length > 0 && selected.size === papers.length;

  return (
    <div>
      <PageHeader
        title="文献库"
        subtitle="收藏管理 · 分类标签 · 统计概览"
        icon="fa-bookmark"
        action={
          <Button variant="secondary" size="sm" onClick={() => setFilter({})}>
            <i className="fas fa-redo mr-1.5" />
            刷新
          </Button>
        }
      />

      {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

      {/* 统计卡片 */}
      {stats && (
        <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
          {[
            { label: '收藏文献', value: stats.total_papers, icon: 'fa-book', color: 'text-copper-light' },
            { label: '分类', value: stats.total_categories, icon: 'fa-folder', color: 'text-jade' },
            { label: '标签', value: stats.total_tags, icon: 'fa-tags', color: 'text-indigo' },
            { label: '星标', value: stats.favorite_count, icon: 'fa-star', color: 'text-vermillion' },
          ].map(s => (
            <Card key={s.label} className="p-4">
              <div className="flex items-center gap-3">
                <i className={`fas ${s.icon} ${s.color}`} />
                <div>
                  <div className="font-serif text-2xl text-ink-bg">{s.value}</div>
                  <div className="text-[10px] text-ink-bg/60">{s.label}</div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {loading ? (
        <Loading text="加载文献库" />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1fr_280px]">
          {/* 文献列表 */}
          <div>
            {/* 过滤栏 + 排序 + 批量操作 */}
            <Card className="mb-4 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <Input
                  icon="fa-search"
                  placeholder="搜索标题..."
                  value={filter.search || ''}
                  onChange={e => setFilter({ ...filter, search: e.target.value || undefined })}
                  className="w-48"
                />
                <Button
                  variant={filter.favorite ? 'primary' : 'secondary'}
                  size="sm"
                  onClick={() => setFilter({ ...filter, favorite: filter.favorite ? undefined : 1 })}
                >
                  <i className="fas fa-star mr-1" />
                  仅看星标
                </Button>

                {/* 排序 */}
                <select
                  value={`${sortKey}:${sortDir}`}
                  onChange={e => {
                    const [k, d] = e.target.value.split(':');
                    setSortKey(k as SortKey);
                    setSortDir(d as SortDir);
                  }}
                  className="cursor-pointer rounded-lg border border-copper/20 bg-ink-dark/40 px-2 py-1.5 text-xs text-ink-bg focus:border-copper focus:outline-none"
                >
                  <option value="created_at:desc" className="bg-ink-dark">最新添加</option>
                  <option value="created_at:asc" className="bg-ink-dark">最早添加</option>
                  <option value="year:desc" className="bg-ink-dark">年份 ↓</option>
                  <option value="year:asc" className="bg-ink-dark">年份 ↑</option>
                  <option value="title:asc" className="bg-ink-dark">标题 A→Z</option>
                  <option value="title:desc" className="bg-ink-dark">标题 Z→A</option>
                  <option value="citation_count:desc" className="bg-ink-dark">引用 ↓</option>
                  <option value="citation_count:asc" className="bg-ink-dark">引用 ↑</option>
                </select>

                {(filter.category || filter.tag || filter.search || filter.favorite) && (
                  <Button variant="ghost" size="sm" onClick={() => setFilter({})}>
                    <i className="fas fa-times mr-1" />
                    清除筛选
                  </Button>
                )}
              </div>

              {/* 批量操作栏 */}
              {selected.size > 0 && (
                <div className="mt-2 flex items-center gap-2 border-t border-copper/10 pt-2">
                  <span className="text-xs text-ink-bg/60">已选 {selected.size} 篇</span>
                  <Button variant="secondary" size="sm" loading={batchLoading} onClick={handleBatchDelete}>
                    <i className="fas fa-trash mr-1" />删除
                  </Button>
                  <Button variant="secondary" size="sm" onClick={handleBatchExport}>
                    <i className="fas fa-download mr-1" />导出
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>
                    <i className="fas fa-times mr-1" />取消选择
                  </Button>
                </div>
              )}
            </Card>

            {papers.length === 0 ? (
              <EmptyState icon="fa-bookmark" title="文献库为空" hint="去文献检索页收藏第一篇文献" />
            ) : (
              <>
                {/* 全选 checkbox */}
                <div className="mb-2 flex items-center gap-2 px-1">
                  <button
                    onClick={toggleSelectAll}
                    className={`flex h-4 w-4 cursor-pointer items-center justify-center rounded border transition-colors ${
                      allSelected ? 'border-copper bg-copper text-ink-dark' : 'border-copper/30 hover:border-copper/60'
                    }`}
                  >
                    {allSelected && <i className="fas fa-check text-[8px]" />}
                  </button>
                  <span className="text-[10px] text-ink-bg/60">
                    {selected.size > 0 ? `已选 ${selected.size}/${papers.length}` : `共 ${papers.length} 篇`}
                  </span>
                </div>

                <div className="space-y-2">
                  {papers.map(paper => {
                    const pid = paper.id || paper.paper_id || '';
                    const isSelected = selected.has(pid);
                    return (
                      <Card key={paper.id} className={`p-4 transition-colors hover:border-copper/30 ${isSelected ? 'border-copper/40 bg-copper/5' : ''}`}>
                        <div className="flex items-start gap-3">
                          <button
                            onClick={() => pid && toggleSelect(pid)}
                            className={`mt-1 flex h-4 w-4 shrink-0 cursor-pointer items-center justify-center rounded border transition-colors ${
                              isSelected ? 'border-copper bg-copper text-ink-dark' : 'border-copper/30 hover:border-copper/60'
                            }`}
                          >
                            {isSelected && <i className="fas fa-check text-[8px]" />}
                          </button>
                          <div className="flex-1">
                            <h3 className="font-serif text-sm text-ink-bg">
                              {paper.url ? (
                                <a href={paper.url} target="_blank" rel="noopener noreferrer" className="hover:text-copper-light">
                                  {paper.title}
                                </a>
                              ) : paper.title}
                            </h3>
                            {paper.authors && paper.authors.length > 0 && (
                              <p className="mt-0.5 text-xs text-ink-bg/60">{paper.authors.slice(0, 3).join(', ')}</p>
                            )}
                            <div className="mt-2 flex flex-wrap items-center gap-2 text-[10px]">
                              {paper.category && paper.category !== 'uncategorized' && (
                                <span className="rounded bg-jade/10 px-1.5 py-0.5 text-jade">{paper.category}</span>
                              )}
                              {paper.tags?.map(tag => (
                                <span key={tag} className="rounded bg-indigo/10 px-1.5 py-0.5 text-indigo">{tag}</span>
                              ))}
                              {paper.year && <span className="text-ink-bg/50">{paper.year}</span>}
                              {paper.citation_count !== undefined && (
                                <span className="text-ink-bg/50"><i className="fas fa-quote-right mr-0.5" />{paper.citation_count}</span>
                              )}
                              {paper.rating && (
                                <span className="text-vermillion">{'★'.repeat(paper.rating)}</span>
                              )}
                            </div>
                          </div>
                          <div className="flex shrink-0 gap-1">
                            <button
                              onClick={() => handleToggleFavorite(paper)}
                              className={`cursor-pointer rounded p-1.5 transition-colors hover:bg-copper/10 ${paper.is_favorite ? 'text-vermillion' : 'text-ink-bg/50'}`}
                              title={paper.is_favorite ? '取消星标' : '加星标'}
                            >
                              <i className="fas fa-star text-xs" />
                            </button>
                            <button
                              onClick={() => handleDelete(paper)}
                              className="cursor-pointer rounded p-1.5 text-ink-bg/50 transition-colors hover:bg-vermillion/10 hover:text-vermillion"
                              title="删除"
                            >
                              <i className="fas fa-trash text-xs" />
                            </button>
                          </div>
                        </div>
                      </Card>
                    );
                  })}
                </div>

                {/* 分页 */}
                {totalPages > 1 && (
                  <div className="mt-4 flex items-center justify-center gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={page <= 1}
                      onClick={() => setPage(p => p - 1)}
                    >
                      <i className="fas fa-chevron-left mr-1" />上一页
                    </Button>
                    <span className="text-xs text-ink-bg/60">
                      {page} / {totalPages}
                    </span>
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={page >= totalPages}
                      onClick={() => setPage(p => p + 1)}
                    >
                      下一页<i className="fas fa-chevron-right ml-1" />
                    </Button>
                  </div>
                )}
              </>
            )}
          </div>

          {/* 侧边：分类 + 标签 */}
          <div className="space-y-4">
            {/* 分类 */}
            <Card className="p-4">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-xs font-medium text-ink-bg/60">分类</h3>
                <button
                  onClick={() => setShowAddCategory(!showAddCategory)}
                  className="cursor-pointer text-copper-light hover:text-copper"
                >
                  <i className="fas fa-plus text-xs" />
                </button>
              </div>
              <AnimatePresence>
                {showAddCategory && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="mb-3 flex gap-2 overflow-hidden"
                  >
                    <Input
                      placeholder="分类名"
                      value={newCategoryName}
                      onChange={e => setNewCategoryName(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && handleAddCategory()}
                      className="flex-1"
                    />
                    <Button size="sm" onClick={handleAddCategory}>添加</Button>
                  </motion.div>
                )}
              </AnimatePresence>
              <div className="space-y-1">
                <button
                  onClick={() => setFilter({ ...filter, category: undefined })}
                  className={`flex w-full cursor-pointer items-center justify-between rounded px-2 py-1.5 text-xs ${!filter.category ? 'bg-copper/10 text-copper-light' : 'text-ink-bg/50 hover:bg-copper/5'}`}
                >
                  <span>全部</span>
                  <span className="text-ink-bg/50">{stats?.total_papers || 0}</span>
                </button>
                {categories.map(cat => (
                  <div key={cat.id} className="group flex items-center justify-between rounded px-2 py-1.5 hover:bg-copper/5">
                    <button
                      onClick={() => setFilter({ ...filter, category: cat.name })}
                      className={`flex flex-1 cursor-pointer items-center justify-between text-xs ${filter.category === cat.name ? 'text-copper-light' : 'text-ink-bg/50'}`}
                    >
                      <span>{cat.name}</span>
                      <span className="text-ink-bg/50">{cat.paper_count}</span>
                    </button>
                    <button
                      onClick={() => handleDeleteCategory(cat.id, cat.name)}
                      className="ml-1 cursor-pointer text-ink-bg/20 opacity-0 transition-opacity hover:text-vermillion group-hover:opacity-100"
                    >
                      <i className="fas fa-times text-[10px]" />
                    </button>
                  </div>
                ))}
              </div>
            </Card>

            {/* 标签 */}
            <Card className="p-4">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-xs font-medium text-ink-bg/60">标签</h3>
                <button
                  onClick={() => setShowAddTag(!showAddTag)}
                  className="cursor-pointer text-copper-light hover:text-copper"
                >
                  <i className="fas fa-plus text-xs" />
                </button>
              </div>
              <AnimatePresence>
                {showAddTag && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="mb-3 flex gap-2 overflow-hidden"
                  >
                    <Input
                      placeholder="标签名"
                      value={newTagName}
                      onChange={e => setNewTagName(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && handleAddTag()}
                      className="flex-1"
                    />
                    <Button size="sm" onClick={handleAddTag}>添加</Button>
                  </motion.div>
                )}
              </AnimatePresence>
              <div className="flex flex-wrap gap-1.5">
                {tags.length === 0 ? (
                  <p className="text-xs text-ink-bg/50">暂无标签</p>
                ) : (
                  tags.map(tag => (
                    <span
                      key={tag.id}
                      className={`group flex cursor-pointer items-center gap-1 rounded px-2 py-1 text-[10px] ${filter.tag === tag.name ? 'bg-indigo/20 text-indigo' : 'bg-ink-bg/5 text-ink-bg/50 hover:bg-indigo/10'}`}
                      onClick={() => setFilter({ ...filter, tag: filter.tag === tag.name ? undefined : tag.name })}
                    >
                      {tag.name}
                      <span className="text-ink-bg/50">{tag.usage_count}</span>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDeleteTag(tag.id, tag.name); }}
                        className="ml-0.5 text-ink-bg/20 opacity-0 hover:text-vermillion group-hover:opacity-100"
                      >
                        <i className="fas fa-times text-[8px]" />
                      </button>
                    </span>
                  ))
                )}
              </div>
            </Card>
          </div>
        </div>
      )}
      <ConfirmDialog
        open={confirmState.open}
        title={confirmState.title}
        message={confirmState.message}
        onConfirm={confirmState.onConfirm}
        onCancel={() => setConfirmState(s => ({ ...s, open: false }))}
      />
    </div>
  );
}

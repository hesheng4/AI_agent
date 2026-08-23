// 论文写作辅助页 — 大纲生成 · AI 润色(带diff) · 语法检查 · 草稿自动保存
import { useState, useEffect, useCallback, type FormEvent } from 'react';
import { PageHeader, Button, Card, Textarea, Input, Loading, EmptyState, ErrorBanner } from '../components/ui';
import { writingApi } from '../api';
import type { OutlineResponse, PolishResponse, CheckResponse } from '../types';

type Tab = 'outline' | 'polish' | 'check';
type PaperType = 'research' | 'methods' | 'hypothesis' | 'algorithmic' | 'review' | 'auto';

const TABS: Array<{ value: Tab; label: string; icon: string }> = [
  { value: 'outline', label: '大纲生成', icon: 'fa-list-ul' },
  { value: 'polish', label: 'AI 润色', icon: 'fa-feather' },
  { value: 'check', label: '语法检查', icon: 'fa-spell-check' },
];

const PAPER_TYPES: Array<{ value: PaperType; label: string }> = [
  { value: 'research', label: 'research' },
  { value: 'methods', label: 'methods' },
  { value: 'hypothesis', label: 'hypothesis' },
  { value: 'algorithmic', label: 'algorithmic' },
  { value: 'review', label: 'review' },
  { value: 'auto', label: 'auto' },
];

const DRAFT_KEY = 'moguan_writing_draft';

function issueTypeColor(type: string): string {
  const t = type.toLowerCase();
  if (t === 'warning') return 'bg-copper/10 text-copper-light border-copper/30';
  if (t === 'error') return 'bg-vermillion/10 text-vermillion border-vermillion/30';
  if (t === 'style') return 'bg-indigo/10 text-indigo border-indigo/30';
  return 'bg-ink-bg/5 text-ink-bg/60 border-ink-bg/20';
}

// Simple diff: highlight additions and deletions between two texts
function computeDiff(oldText: string, newText: string): Array<{ type: 'same' | 'add' | 'del'; text: string }> {
  const oldLines = oldText.split('\n');
  const newLines = newText.split('\n');
  const result: Array<{ type: 'same' | 'add' | 'del'; text: string }> = [];

  const maxLen = Math.max(oldLines.length, newLines.length);
  for (let i = 0; i < maxLen; i++) {
    const oldLine = oldLines[i];
    const newLine = newLines[i];
    if (oldLine === newLine) {
      result.push({ type: 'same', text: oldLine });
    } else {
      if (oldLine !== undefined) result.push({ type: 'del', text: oldLine });
      if (newLine !== undefined) result.push({ type: 'add', text: newLine });
    }
  }
  return result;
}

function DiffView({ oldText, newText }: { oldText: string; newText: string }) {
  const diff = computeDiff(oldText, newText);
  return (
    <div className="max-h-96 overflow-auto rounded-lg bg-ink-dark/40 p-3 font-mono text-xs">
      {diff.map((d, i) => (
        <div
          key={i}
          className={`whitespace-pre-wrap ${
            d.type === 'add'
              ? 'bg-jade/10 text-jade border-l-2 border-jade pl-2'
              : d.type === 'del'
              ? 'bg-vermillion/10 text-vermillion/60 line-through border-l-2 border-vermillion/40 pl-2'
              : 'text-ink-bg/60'
          }`}
        >
          <span className="inline-block w-4 text-ink-bg/20 select-none">
            {d.type === 'add' ? '+' : d.type === 'del' ? '-' : ' '}
          </span>
          {d.text}
        </div>
      ))}
    </div>
  );
}

export default function Writing() {
  const [tab, setTab] = useState<Tab>('outline');

  // 大纲
  const [topic, setTopic] = useState('');
  const [paperType, setPaperType] = useState<PaperType>('research');
  const [outlineLoading, setOutlineLoading] = useState(false);
  const [outlineError, setOutlineError] = useState('');
  const [outline, setOutline] = useState<OutlineResponse | null>(null);

  // 全文生成（F4: outline → generate 流水线）
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState('');
  const [generatedContent, setGeneratedContent] = useState('');

  // 润色
  const [polishContent, setPolishContent] = useState('');
  const [polishLoading, setPolishLoading] = useState(false);
  const [polishError, setPolishError] = useState('');
  const [polished, setPolished] = useState<PolishResponse | null>(null);

  // 检查
  const [checkContent, setCheckContent] = useState('');
  const [checkLoading, setCheckLoading] = useState(false);
  const [checkError, setCheckError] = useState('');
  const [checked, setChecked] = useState<CheckResponse | null>(null);

  // 草稿自动保存
  const [draftSaved, setDraftSaved] = useState(false);

  // Load draft on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(DRAFT_KEY);
      if (saved) {
        const data = JSON.parse(saved);
        if (data.polishContent) setPolishContent(data.polishContent);
        if (data.checkContent) setCheckContent(data.checkContent);
      }
    } catch {}
  }, []);

  // Auto-save draft
  const saveDraft = useCallback(() => {
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify({
        polishContent,
        checkContent,
        savedAt: Date.now(),
      }));
      setDraftSaved(true);
      setTimeout(() => setDraftSaved(false), 2000);
    } catch {}
  }, [polishContent, checkContent]);

  // Auto-save every 30s if there's content
  useEffect(() => {
    if (!polishContent && !checkContent) return;
    const timer = setInterval(saveDraft, 30000);
    return () => clearInterval(timer);
  }, [polishContent, checkContent, saveDraft]);

  function clearDraft() {
    localStorage.removeItem(DRAFT_KEY);
    setPolishContent('');
    setCheckContent('');
  }

  async function handleOutline(e: FormEvent) {
    e.preventDefault();
    setOutlineError('');
    setOutline(null);
    setGeneratedContent('');
    if (!topic.trim()) {
      setOutlineError('请输入研究主题');
      return;
    }
    setOutlineLoading(true);
    try {
      const res = await writingApi.outline({ topic: topic.trim(), paper_type: paperType });
      setOutline(res);
    } catch (err) {
      setOutlineError(err instanceof Error ? err.message : '大纲生成失败');
    } finally {
      setOutlineLoading(false);
    }
  }

  // F4: 基于大纲生成全文（outline → generate）
  async function handleGenerate() {
    if (!outline) return;
    setGenerating(true);
    setGenerateError('');
    setGeneratedContent('');
    try {
      const res = await writingApi.generate({
        outline: {
          optimized_outline: outline.optimized_outline,
          core_chain: outline.core_chain,
          template: outline.template,
        },
        section: 'introduction',
        paper_type: paperType,
      });
      setGeneratedContent(res.content || '');
    } catch (err) {
      setGenerateError(err instanceof Error ? err.message : '全文生成失败');
    } finally {
      setGenerating(false);
    }
  }

  async function handlePolish(e: FormEvent) {
    e.preventDefault();
    setPolishError('');
    setPolished(null);
    if (!polishContent.trim()) {
      setPolishError('请输入待润色文本');
      return;
    }
    setPolishLoading(true);
    try {
      const res = await writingApi.polish({ content: polishContent });
      setPolished(res);
    } catch (err) {
      setPolishError(err instanceof Error ? err.message : '润色失败');
    } finally {
      setPolishLoading(false);
    }
  }

  async function handleCheck(e: FormEvent) {
    e.preventDefault();
    setCheckError('');
    setChecked(null);
    if (!checkContent.trim()) {
      setCheckError('请输入待检查文本');
      return;
    }
    setCheckLoading(true);
    try {
      const res = await writingApi.check({ content: checkContent });
      setChecked(res);
    } catch (err) {
      setCheckError(err instanceof Error ? err.message : '检查失败');
    } finally {
      setCheckLoading(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="论文写作"
        subtitle="大纲 · 润色 · 检查"
        icon="fa-pen-fancy"
        action={
          (polishContent || checkContent) ? (
            <div className="flex items-center gap-2">
              {draftSaved && (
                <span className="text-[10px] text-jade"><i className="fas fa-check mr-1" />已保存</span>
              )}
              <Button variant="ghost" size="sm" onClick={saveDraft}>
                <i className="fas fa-save mr-1" />保存草稿
              </Button>
              <Button variant="ghost" size="sm" onClick={clearDraft}>
                <i className="fas fa-trash mr-1" />清空
              </Button>
            </div>
          ) : undefined
        }
      />

      {/* Tab 切换 */}
      <div className="mb-6 flex gap-6 border-b border-copper/10">
        {TABS.map(t => (
          <button
            key={t.value}
            type="button"
            onClick={() => setTab(t.value)}
            className={`flex items-center gap-2 pb-3 text-sm transition-colors ${
              tab === t.value
                ? 'border-b-2 border-copper text-copper-light'
                : 'border-b-2 border-transparent text-ink-bg/50 hover:text-ink-bg/70'
            }`}
          >
            <i className={`fas ${t.icon}`} />
            {t.label}
          </button>
        ))}
      </div>

      {/* 大纲生成 */}
      {tab === 'outline' && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <form onSubmit={handleOutline} className="space-y-4">
              <h3 className="font-serif text-sm text-ink-bg">大纲生成</h3>
              <Input
                label="研究主题"
                placeholder="如：深度学习在医学影像中的应用"
                value={topic}
                onChange={e => setTopic(e.target.value)}
              />
              <div>
                <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">论文类型</span>
                <div className="flex flex-wrap gap-2">
                  {PAPER_TYPES.map(p => (
                    <button
                      key={p.value}
                      type="button"
                      onClick={() => setPaperType(p.value)}
                      className={`rounded-lg border px-3 py-1.5 text-xs transition-colors ${
                        paperType === p.value
                          ? 'border-copper bg-copper text-ink-bg'
                          : 'border-copper/20 text-ink-bg/50 hover:border-copper/40 hover:text-ink-bg/70'
                      }`}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>
              <Button type="submit" loading={outlineLoading} disabled={!topic.trim()}>
                <i className="fas fa-list-ul mr-1.5" />生成大纲
              </Button>
            </form>
          </Card>

          <Card>
            <h3 className="mb-3 font-serif text-sm text-ink-bg">生成结果</h3>
            {outlineLoading ? (
              <Loading text="正在生成大纲" />
            ) : outlineError ? (
              <ErrorBanner message={outlineError} />
            ) : outline ? (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded bg-copper/10 px-2 py-1 text-xs text-copper-light">
                    <i className="fas fa-tag mr-1" />{outline.paper_type}
                  </span>
                </div>
                <div>
                  <h4 className="mb-1.5 text-xs font-medium text-ink-bg/60">核心链路</h4>
                  <p className="text-sm leading-relaxed text-ink-bg/70">{outline.core_chain}</p>
                </div>
                <div>
                  <h4 className="mb-1.5 text-xs font-medium text-ink-bg/60">撰写顺序</h4>
                  <ol className="space-y-1.5">
                    {outline.drafting_order.map((step, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-sm text-ink-bg/70">
                        <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded bg-copper/10 text-xs text-copper-light">
                          {idx + 1}
                        </span>
                        <span>{step}</span>
                      </li>
                    ))}
                  </ol>
                </div>
                <div>
                  <h4 className="mb-1.5 text-xs font-medium text-ink-bg/60">优化后大纲</h4>
                  <pre className="max-h-96 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                    {outline.optimized_outline}
                  </pre>
                </div>

                {/* F4: 大纲 → 全文生成 */}
                <div className="border-t border-copper/10 pt-4">
                  <Button onClick={handleGenerate} loading={generating}>
                    <i className="fas fa-file-lines mr-1.5" />
                    基于大纲生成全文
                  </Button>
                  {generateError && <div className="mt-3"><ErrorBanner message={generateError} /></div>}
                  {generatedContent && (
                    <div className="mt-4">
                      <h4 className="mb-2 flex items-center gap-2 text-xs font-medium text-ink-bg/60">
                        <i className="fas fa-file-lines text-copper-light" />
                        生成全文
                      </h4>
                      <pre className="max-h-[28rem] overflow-auto whitespace-pre-wrap rounded-lg bg-ink-dark/40 p-4 font-serif text-sm leading-relaxed text-ink-bg/80">
                        {generatedContent}
                      </pre>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setTab('polish');
                            setPolishContent(generatedContent);
                          }}
                        >
                          <i className="fas fa-feather mr-1" />送去润色
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setTab('check');
                            setCheckContent(generatedContent);
                          }}
                        >
                          <i className="fas fa-spell-check mr-1" />送去检查
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <EmptyState icon="fa-list-ul" title="输入主题以生成大纲" />
            )}
          </Card>
        </div>
      )}

      {/* AI 润色 */}
      {tab === 'polish' && (
        <div className="space-y-6">
          <Card>
            <form onSubmit={handlePolish} className="space-y-4">
              <h3 className="font-serif text-sm text-ink-bg">AI 润色</h3>
              <Textarea
                label="待润色文本"
                rows={8}
                placeholder="粘贴需要润色的论文段落..."
                value={polishContent}
                onChange={e => setPolishContent(e.target.value)}
              />
              <Button type="submit" loading={polishLoading} disabled={!polishContent.trim()}>
                <i className="fas fa-feather mr-1.5" />润色
              </Button>
            </form>
          </Card>

          {polishLoading ? (
            <Card><Loading text="正在润色文本" /></Card>
          ) : polishError ? (
            <Card><ErrorBanner message={polishError} /></Card>
          ) : polished ? (
            <Card>
              <h3 className="mb-3 font-serif text-sm text-ink-bg">
                <i className="fas fa-feather mr-1.5 text-copper-light" />
                润色对比
              </h3>
              <DiffView oldText={polished.original} newText={polished.polished} />
              <div className="mt-3 grid gap-4 lg:grid-cols-2">
                <div>
                  <h4 className="mb-1.5 text-xs font-medium text-ink-bg/60">原文</h4>
                  <pre className="max-h-60 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70 whitespace-pre-wrap">
                    {polished.original}
                  </pre>
                </div>
                <div>
                  <h4 className="mb-1.5 text-xs font-medium text-copper-light">
                    <i className="fas fa-feather mr-1" />润色后
                  </h4>
                  <pre className="max-h-60 overflow-auto rounded-lg border border-copper/40 bg-ink-dark/40 p-3 text-xs text-ink-bg/70 whitespace-pre-wrap">
                    {polished.polished}
                  </pre>
                </div>
              </div>
            </Card>
          ) : null}
        </div>
      )}

      {/* 语法检查 */}
      {tab === 'check' && (
        <div className="space-y-6">
          <Card>
            <form onSubmit={handleCheck} className="space-y-4">
              <h3 className="font-serif text-sm text-ink-bg">语法检查</h3>
              <Textarea
                label="待检查文本"
                rows={8}
                placeholder="粘贴需要检查的论文文本..."
                value={checkContent}
                onChange={e => setCheckContent(e.target.value)}
              />
              <Button type="submit" loading={checkLoading} disabled={!checkContent.trim()}>
                <i className="fas fa-spell-check mr-1.5" />检查
              </Button>
            </form>
          </Card>

          {checkLoading ? (
            <Card><Loading text="正在检查文本" /></Card>
          ) : checkError ? (
            <Card><ErrorBanner message={checkError} /></Card>
          ) : checked ? (
            <Card>
              <div className="mb-4 flex items-center justify-between">
                <h3 className="font-serif text-sm text-ink-bg">检查结果</h3>
                <span className="rounded bg-copper/10 px-2.5 py-1 text-xs text-copper-light">
                  <i className="fas fa-flag mr-1" />共 {checked.total_issues} 个问题
                </span>
              </div>
              {checked.issues.length === 0 ? (
                <EmptyState icon="fa-check-circle" title="未发现问题" hint="文本质量良好" />
              ) : (
                <ul className="space-y-2.5">
                  {checked.issues.map((issue, idx) => (
                    <li key={idx} className="flex items-start gap-3 rounded-lg border border-copper/10 bg-ink-dark/40 p-3">
                      <span className={`shrink-0 rounded border px-2 py-0.5 text-xs font-medium ${issueTypeColor(issue.type)}`}>
                        {issue.type}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm text-ink-bg/80">{issue.message}</p>
                        {issue.position && (
                          <p className="mt-1 text-xs text-ink-bg/60">
                            <i className="fas fa-map-marker-alt mr-1" />{issue.position}
                          </p>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          ) : null}
        </div>
      )}
    </div>
  );
}

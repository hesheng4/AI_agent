// 审稿页 — 模拟 Nature 审稿人评估
import { useState, type FormEvent } from 'react';
import { PageHeader, Button, Card, Textarea, Loading, EmptyState, ErrorBanner } from '../components/ui';
import { reviewerApi, responseApi } from '../api';
import type { AssessResponse, QuickCheckResponse, DraftResponseResult } from '../types';

type TabKey = 'assess' | 'quickCheck';

export default function Reviewer() {
  const [tab, setTab] = useState<TabKey>('assess');
  const [content, setContent] = useState('');
  const [paperType, setPaperType] = useState('research');

  const [assessResult, setAssessResult] = useState<AssessResponse | null>(null);
  const [assessLoading, setAssessLoading] = useState(false);
  const [assessError, setAssessError] = useState('');

  const [draftResult, setDraftResult] = useState<DraftResponseResult | null>(null);
  const [draftLoading, setDraftLoading] = useState(false);
  const [draftError, setDraftError] = useState('');

  const [quickResult, setQuickResult] = useState<QuickCheckResponse | null>(null);
  const [quickLoading, setQuickLoading] = useState(false);
  const [quickError, setQuickError] = useState('');

  async function handleAssess(e: FormEvent) {
    e.preventDefault();
    if (!content.trim()) return;
    setAssessLoading(true);
    setAssessError('');
    setAssessResult(null);
    try {
      const res = await reviewerApi.assess({ content: content.trim(), paper_type: paperType });
      setAssessResult(res);
    } catch (err) {
      setAssessError(err instanceof Error ? err.message : '审稿评估失败');
    } finally {
      setAssessLoading(false);
    }
  }

  async function handleQuickCheck(e: FormEvent) {
    e.preventDefault();
    if (!content.trim()) return;
    setQuickLoading(true);
    setQuickError('');
    setQuickResult(null);
    try {
      const res = await reviewerApi.quickCheck({ content: content.trim(), paper_type: paperType });
      setQuickResult(res);
    } catch (err) {
      setQuickError(err instanceof Error ? err.message : '快速预审失败');
    } finally {
      setQuickLoading(false);
    }
  }

  // B3 串联：一键将审稿结果转成审稿回复信（response.draft 自动从 review_result 派生意见）
  async function handleGenerateReply() {
    if (!assessResult) return;
    setDraftLoading(true);
    setDraftError('');
    setDraftResult(null);
    try {
      const res = await responseApi.draft({
        review_result: assessResult,
        manuscript_content: content.trim() || undefined,
      });
      setDraftResult(res);
    } catch (err) {
      setDraftError(err instanceof Error ? err.message : '生成回复失败');
    } finally {
      setDraftLoading(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="模拟审稿"
        subtitle="Nature 风格审稿人评估"
        icon="fa-user-check"
      />

      <div className="mb-6 flex gap-6 border-b border-copper/10">
        {([
          { key: 'assess' as TabKey, label: '完整审稿', icon: 'fa-file-lines' },
          { key: 'quickCheck' as TabKey, label: '快速预审', icon: 'fa-bolt' },
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

      {/* 输入区 */}
      <Card className="mb-6">
        <form onSubmit={tab === 'assess' ? handleAssess : handleQuickCheck} className="space-y-4">
          <Textarea
            label="稿件内容"
            placeholder="粘贴论文稿件内容..."
            value={content}
            onChange={e => setContent(e.target.value)}
            rows={8}
            className="font-mono text-sm"
          />
          <div className="flex flex-wrap items-end gap-4">
            <label className="block">
              <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">论文类型</span>
              <select
                value={paperType}
                onChange={e => setPaperType(e.target.value)}
                className="cursor-pointer rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none focus:ring-1 focus:ring-copper/30"
              >
                <option value="research" className="bg-ink-dark">Research Article</option>
                <option value="review" className="bg-ink-dark">Review</option>
                <option value="methods" className="bg-ink-dark">Methods</option>
                <option value="hypothesis" className="bg-ink-dark">Hypothesis</option>
              </select>
            </label>
            <Button type="submit" loading={tab === 'assess' ? assessLoading : quickLoading}>
              <i className={`fas ${tab === 'assess' ? 'fa-file-lines' : 'fa-bolt'} mr-1.5`} />
              {tab === 'assess' ? '开始审稿' : '快速预审'}
            </Button>
          </div>
        </form>
      </Card>

      {/* 完整审稿结果 */}
      {tab === 'assess' && (
        <>
          {assessError && <div className="mb-4"><ErrorBanner message={assessError} /></div>}
          {assessLoading && <Loading text="3 位审稿人评估中" />}
          {assessResult && (
            <div className="space-y-4">
              <Card>
                <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg">
                  <i className="fas fa-database text-copper-light" />
                  事实基础
                </h3>
                <div className="rounded-lg bg-ink-dark/60 p-4 text-sm text-ink-bg/80 whitespace-pre-wrap">
                  {assessResult.fact_base}
                </div>
              </Card>
              <Card>
                <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg">
                  <i className="fas fa-gavel text-copper-light" />
                  审稿意见
                </h3>
                <div className="rounded-lg bg-ink-dark/60 p-4 text-sm text-ink-bg/80 whitespace-pre-wrap">
                  {assessResult.review_result}
                </div>
              </Card>
              <div className="flex flex-wrap items-center gap-4">
                <Button onClick={handleGenerateReply} loading={draftLoading}>
                  <i className="fas fa-reply mr-1.5" />
                  一键生成回复
                </Button>
                {draftError && (
                  <span className="text-xs text-red-400">
                    <i className="fas fa-circle-exclamation mr-1" />
                    {draftError}
                  </span>
                )}
              </div>
              {draftResult && (
                <Card>
                  <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg">
                    <i className="fas fa-reply text-copper-light" />
                    审稿回复信
                    <span className="ml-auto text-[11px] text-ink-bg/60">
                      {draftResult.decision_type} · 共 {draftResult.total_comments} 条意见
                    </span>
                  </h3>
                  <div className="rounded-lg bg-ink-dark/60 p-4 text-sm text-ink-bg/80 whitespace-pre-wrap">
                    {draftResult.response_letter}
                  </div>
                </Card>
              )}
              <div className="flex gap-3 text-[11px] text-ink-bg/60">
                <span>类型: {assessResult.paper_type}</span>
                <span>范围: {assessResult.input_scope}</span>
              </div>
            </div>
          )}
          {!assessLoading && !assessResult && (
            <EmptyState
              icon="fa-user-check"
              title="粘贴稿件开始审稿"
              hint="模拟 3 位审稿人 + 交叉综述，返回结构化审稿意见"
            />
          )}
        </>
      )}

      {/* 快速预审结果 */}
      {tab === 'quickCheck' && (
        <>
          {quickError && <div className="mb-4"><ErrorBanner message={quickError} /></div>}
          {quickLoading && <Loading text="快速预审中" />}
          {quickResult && (
            <Card>
              <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg">
                <i className="fas fa-bolt text-copper-light" />
                预审结果
              </h3>
              <div className="rounded-lg bg-ink-dark/60 p-4 text-sm text-ink-bg/80 whitespace-pre-wrap">
                {quickResult.quick_check}
              </div>
              <div className="mt-3 text-[11px] text-ink-bg/60">
                论文类型: {quickResult.paper_type}
              </div>
            </Card>
          )}
          {!quickLoading && !quickResult && (
            <EmptyState
              icon="fa-bolt"
              title="快速预审检查"
              hint="快速检查稿件格式、结构、语言等基础问题"
            />
          )}
        </>
      )}
    </div>
  );
}

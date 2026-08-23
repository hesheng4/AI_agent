// 审稿回复页 — 起草 · 审计 · 修改
import { useState, type FormEvent } from 'react';
import { motion } from 'motion/react';
import { PageHeader, Button, Card, Textarea, Loading, ErrorBanner } from '../components/ui';
import { responseApi } from '../api';
import type { AssessResponse, DraftResponseResult, AuditResponseResult, ReviseResponseResult } from '../types';

type TabKey = 'draft' | 'audit' | 'revise';

export default function ResponsePage() {
  const [tab, setTab] = useState<TabKey>('draft');

  const [commentsText, setCommentsText] = useState('');
  const [content, setContent] = useState('');
  const [decisionType, setDecisionType] = useState('major');
  const [reviewResultJson, setReviewResultJson] = useState('');
  const [feedback, setFeedback] = useState('');

  const [draftResult, setDraftResult] = useState<DraftResponseResult | null>(null);
  const [auditResult, setAuditResult] = useState<AuditResponseResult | null>(null);
  const [reviseResult, setReviseResult] = useState<ReviseResponseResult | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  function parseComments(text: string): string[] {
    return text.split('\n').map(l => l.trim()).filter(Boolean);
  }

  async function handleDraft(e: FormEvent) {
    e.preventDefault();
    let reviewResult: AssessResponse | null = null;
    if (reviewResultJson.trim()) {
      try {
        const parsed = JSON.parse(reviewResultJson) as AssessResponse;
        if (!parsed || typeof parsed !== 'object' || typeof parsed.review_result !== 'string') {
          setError('审稿结果 JSON 格式不正确：缺少 review_result 字段（请粘贴审稿页的完整审稿结果）');
          return;
        }
        reviewResult = parsed;
      } catch {
        setError('审稿结果 JSON 解析失败，请检查是否为合法 JSON');
        return;
      }
    }
    const comments = parseComments(commentsText);
    if (!reviewResult && comments.length === 0) { setError('请输入至少一条审稿意见，或粘贴审稿结果 JSON'); return; }
    setLoading(true); setError(''); setDraftResult(null);
    try {
      const res = await responseApi.draft(reviewResult
        ? { review_result: reviewResult, manuscript_content: content || undefined }
        : {
            reviewer_comments: comments,
            decision_type: decisionType as 'minor' | 'major' | 'revise-and-resubmit',
            manuscript_content: content || undefined,
          });
      setDraftResult(res);
    } catch (err) { setError(err instanceof Error ? err.message : '起草失败'); }
    finally { setLoading(false); }
  }

  async function handleAudit(e: FormEvent) {
    e.preventDefault();
    if (!content.trim()) { setError('请输入回复内容'); return; }
    setLoading(true); setError(''); setAuditResult(null);
    try {
      const res = await responseApi.audit({
        response_content: content.trim(),
        reviewer_comments: parseComments(commentsText),
      });
      setAuditResult(res);
    } catch (err) { setError(err instanceof Error ? err.message : '审计失败'); }
    finally { setLoading(false); }
  }

  async function handleRevise(e: FormEvent) {
    e.preventDefault();
    if (!content.trim() || !feedback.trim()) { setError('请输入回复内容和修改反馈'); return; }
    setLoading(true); setError(''); setReviseResult(null);
    try {
      const res = await responseApi.revise({
        response_content: content.trim(),
        feedback: feedback.trim(),
        reviewer_comments: parseComments(commentsText),
      });
      setReviseResult(res);
    } catch (err) { setError(err instanceof Error ? err.message : '修改失败'); }
    finally { setLoading(false); }
  }

  return (
    <div>
      <PageHeader title="审稿回复" subtitle="起草 · 审计 · 修改" icon="fa-reply" />

      <div className="mb-6 flex gap-6 border-b border-copper/10">
        {([
          { key: 'draft' as TabKey, label: '起草回复', icon: 'fa-pen' },
          { key: 'audit' as TabKey, label: '审计回复', icon: 'fa-magnifying-glass' },
          { key: 'revise' as TabKey, label: '修改回复', icon: 'fa-pen-to-square' },
        ]).map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`flex cursor-pointer items-center gap-2 px-1 pb-3 text-sm transition-colors ${
              tab === t.key ? 'border-b-2 border-copper text-copper-light' : 'border-b-2 border-transparent text-ink-bg/50 hover:text-ink-bg'
            }`}>
            <i className={`fas ${t.icon} text-xs`} />{t.label}
          </button>
        ))}
      </div>

      {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

      {tab === 'draft' && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="mb-6">
            <form onSubmit={handleDraft} className="space-y-4">
              <Textarea label="审稿意见（每行一条）" placeholder="Reviewer 1: The methodology...&#10;Reviewer 2: Please clarify..."
                value={commentsText} onChange={e => setCommentsText(e.target.value)} rows={5} />
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">决策类型</span>
                <select value={decisionType} onChange={e => setDecisionType(e.target.value)}
                  className="cursor-pointer rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none focus:ring-1 focus:ring-copper/30">
                  <option value="minor" className="bg-ink-dark">Minor Revision</option>
                  <option value="major" className="bg-ink-dark">Major Revision</option>
                  <option value="revise-and-resubmit" className="bg-ink-dark">Revise & Resubmit</option>
                </select>
              </label>
              <Textarea label="稿件内容（可选）" placeholder="粘贴稿件内容以获取更精准的回复..."
                value={content} onChange={e => setContent(e.target.value)} rows={4} />
              <Textarea label="审稿结果 JSON（可选，与上方审稿意见二选一）" placeholder='从「审稿」页复制完整审稿结果（AssessResponse JSON），例如 {"status":"ok","review_result":"...","paper_type":"research",...}'
                value={reviewResultJson} onChange={e => setReviewResultJson(e.target.value)} rows={4} />
              <Button type="submit" loading={loading}><i className="fas fa-pen mr-1.5" />起草回复信</Button>
            </form>
          </Card>
          {loading && <Loading text="起草审稿回复信" />}
          {draftResult && (
            <div className="space-y-4">
              <Card>
                <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg">
                  <i className="fas fa-reply text-copper-light" />回复信
                </h3>
                <div className="rounded-lg bg-ink-dark/60 p-4 text-sm text-ink-bg/80 whitespace-pre-wrap">{draftResult.response_letter}</div>
              </Card>
              <div className="flex gap-3 text-[11px] text-ink-bg/60">
                <span>决策: {draftResult.decision_type}</span><span>意见数: {draftResult.total_comments}</span>
              </div>
            </div>
          )}
        </motion.div>
      )}

      {tab === 'audit' && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="mb-6">
            <form onSubmit={handleAudit} className="space-y-4">
              <Textarea label="回复内容" placeholder="粘贴已起草的回复内容..."
                value={content} onChange={e => setContent(e.target.value)} rows={8} />
              <Textarea label="原审稿意见（可选）" placeholder="Reviewer 1: ..."
                value={commentsText} onChange={e => setCommentsText(e.target.value)} rows={3} />
              <Button type="submit" loading={loading}><i className="fas fa-magnifying-glass mr-1.5" />审计回复</Button>
            </form>
          </Card>
          {loading && <Loading text="审计回复完整性" />}
          {auditResult && (
            <Card>
              <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg">
                <i className="fas fa-clipboard-check text-copper-light" />审计结果
              </h3>
              <div className="rounded-lg bg-ink-dark/60 p-4 text-sm text-ink-bg/80 whitespace-pre-wrap">{auditResult.audit_result}</div>
            </Card>
          )}
        </motion.div>
      )}

      {tab === 'revise' && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="mb-6">
            <form onSubmit={handleRevise} className="space-y-4">
              <Textarea label="当前回复内容" placeholder="粘贴当前回复内容..."
                value={content} onChange={e => setContent(e.target.value)} rows={6} />
              <Textarea label="修改反馈" placeholder="请补充对 Reviewer 2 的具体实验数据..."
                value={feedback} onChange={e => setFeedback(e.target.value)} rows={3} />
              <Textarea label="原审稿意见（可选）" placeholder="Reviewer 1: ..."
                value={commentsText} onChange={e => setCommentsText(e.target.value)} rows={3} />
              <Button type="submit" loading={loading}><i className="fas fa-pen-to-square mr-1.5" />修改回复</Button>
            </form>
          </Card>
          {loading && <Loading text="修改回复中" />}
          {reviseResult && (
            <div className="space-y-4">
              <Card>
                <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg">
                  <i className="fas fa-pen-to-square text-copper-light" />修改后回复
                </h3>
                <div className="rounded-lg bg-ink-dark/60 p-4 text-sm text-ink-bg/80 whitespace-pre-wrap">{reviseResult.revised_response}</div>
              </Card>
              {reviseResult.feedback_applied && (
                <Card>
                  <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg">
                    <i className="fas fa-check text-copper-light" />已应用反馈
                  </h3>
                  <div className="rounded-lg bg-ink-dark/60 p-3 text-xs text-ink-bg/70 whitespace-pre-wrap">{reviseResult.feedback_applied}</div>
                </Card>
              )}
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
}

// 审稿迭代闭环页（H1）— 审稿 → 修订 → 再审稿 自动迭代
import { useState, type FormEvent } from 'react';
import {
  PageHeader, Button, Card, Textarea, Loading, EmptyState, ErrorBanner,
} from '../components/ui';
import { reviewLoopApi } from '../api';
import type { ReviewLoopResponse, ReviewLoopRound } from '../types';

// 停止原因 → 中文文案
const STOP_REASON_LABELS: Record<string, string> = {
  score_achieved: '分数达标',
  score_unavailable: '无法评分，提前收敛',
  no_suggestions: '审稿无改进意见',
  revise_no_change: '修订未产生实质变化',
  max_rounds: '已达最大迭代轮数',
};

// 评分维度 → 中文名（未知维度回退原键）
const AXIS_LABELS: Record<string, string> = {
  novelty: '新颖性',
  quality: '质量',
  validity: '有效性',
  clarity: '清晰度',
  impact: '影响力',
  rigor: '严谨性',
};

function axisLabel(key: string): string {
  return AXIS_LABELS[key] ?? key;
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  const pct = Math.max(0, Math.min(100, (value / 10) * 100));
  const good = value >= 7;
  return (
    <div className="flex items-center gap-3">
      <span className="w-14 shrink-0 text-xs text-ink-bg/60">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-ink-dark/60">
        <div
          className={`h-full rounded-full ${good ? 'bg-copper-light' : 'bg-amber-400/80'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-8 shrink-0 text-right text-xs font-medium text-ink-bg/80">
        {value.toFixed(1)}
      </span>
    </div>
  );
}

function RoundCard({ round, target }: { round: ReviewLoopRound; target: number }) {
  const met = round.score !== null && round.score >= target;
  return (
    <Card className={`border-l-2 ${met ? 'border-l-copper-light' : 'border-l-amber-400/60'}`}>
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <h4 className="flex items-center gap-2 text-sm font-medium text-ink-bg">
          <i className="fas fa-rotate text-copper-light" />
          第 {round.round} 轮
        </h4>
        {round.score !== null ? (
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
              met ? 'bg-copper/15 text-copper-light' : 'bg-amber-400/10 text-amber-300'
            }`}
          >
            {met ? '达标' : '未达标'} · {round.score.toFixed(1)} / 10
          </span>
        ) : (
          <span className="rounded-full bg-ink-dark/40 px-2.5 py-0.5 text-xs text-ink-bg/50">
            无法评分
          </span>
        )}
        <span className="text-[11px] text-ink-bg/60">{round.suggestion_count} 条意见</span>
      </div>

      {Object.keys(round.axes).length > 0 && (
        <div className="mb-3 space-y-2">
          {Object.entries(round.axes).map(([key, value]) => (
            <ScoreBar key={key} label={axisLabel(key)} value={value} />
          ))}
        </div>
      )}

      {round.change_summary && (
        <p className="rounded-lg bg-ink-dark/40 px-3 py-2 text-xs text-ink-bg/70">
          <i className="fas fa-pen-to-square mr-1.5 text-copper-light" />
          {round.change_summary}
        </p>
      )}
    </Card>
  );
}

export default function ReviewLoop() {
  const [content, setContent] = useState('');
  const [paperType, setPaperType] = useState('research');
  const [maxRounds, setMaxRounds] = useState(3);
  const [targetScore, setTargetScore] = useState(7.0);

  const [result, setResult] = useState<ReviewLoopResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);

  async function handleRun(e: FormEvent) {
    e.preventDefault();
    if (!content.trim()) return;
    setLoading(true);
    setError('');
    setResult(null);
    setCopied(false);
    try {
      const res = await reviewLoopApi.run({
        content: content.trim(),
        paper_type: paperType,
        max_rounds: maxRounds,
        target_score: targetScore,
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : '运行审稿迭代失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleCopy() {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result.final_content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  const finalScore = result?.rounds.length
    ? result.rounds[result.rounds.length - 1].score
    : null;

  return (
    <div>
      <PageHeader
        title="审稿迭代闭环"
        subtitle="审稿 → 修订 → 再审稿，自动迭代至达标"
        icon="fa-rotate"
      />

      {/* 输入区 */}
      <Card className="mb-6">
        <form onSubmit={handleRun} className="space-y-4">
          <Textarea
            label="稿件内容"
            placeholder="粘贴论文稿件内容，系统将自动审稿并迭代修订..."
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
            <label className="block">
              <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">
                最大轮数（{maxRounds}）
              </span>
              <input
                type="number"
                min={1}
                max={10}
                value={maxRounds}
                onChange={e => setMaxRounds(Number(e.target.value))}
                className="w-24 rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none focus:ring-1 focus:ring-copper/30"
              />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">
                目标分数（{targetScore.toFixed(1)}）
              </span>
              <input
                type="number"
                min={0}
                max={10}
                step={0.5}
                value={targetScore}
                onChange={e => setTargetScore(Number(e.target.value))}
                className="w-24 rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none focus:ring-1 focus:ring-copper/30"
              />
            </label>
            <Button type="submit" loading={loading}>
              <i className="fas fa-play mr-1.5" />
              运行迭代
            </Button>
          </div>
        </form>
      </Card>

      {error && <div className="mb-4"><ErrorBanner message={error} /></div>}
      {loading && (
        <Loading text={`迭代审稿中（每轮含审稿 + 评分 + 修订，最多 ${maxRounds} 轮）`} />
      )}

      {result && (
        <div className="space-y-4">
          {/* 概览 */}
          <Card>
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
              <div>
                <div className="text-[11px] text-ink-bg/60">迭代轮数</div>
                <div className="text-lg font-semibold text-ink-bg">{result.total_rounds}</div>
              </div>
              <div>
                <div className="text-[11px] text-ink-bg/60">最终评分</div>
                <div className="text-lg font-semibold text-ink-bg">
                  {finalScore !== null ? `${finalScore.toFixed(1)} / 10` : '—'}
                </div>
              </div>
              <div>
                <div className="text-[11px] text-ink-bg/60">停止原因</div>
                <div
                  className={`text-sm font-medium ${
                    result.converged ? 'text-copper-light' : 'text-amber-300'
                  }`}
                >
                  <i className={`fas ${result.converged ? 'fa-check-circle' : 'fa-hourglass-half'} mr-1.5`} />
                  {STOP_REASON_LABELS[result.stop_reason] ?? result.stop_reason}
                </div>
              </div>
              <div className="text-[11px] text-ink-bg/60">
                目标 {result.target_score.toFixed(1)} · 上限 {result.max_rounds} 轮
              </div>
            </div>
          </Card>

          {/* 轮次明细 */}
          <div className="space-y-3">
            {result.rounds.map(r => (
              <RoundCard key={r.round} round={r} target={result.target_score} />
            ))}
          </div>

          {/* 最终稿件 */}
          <Card>
            <div className="mb-3 flex items-center gap-2">
              <h3 className="flex items-center gap-2 text-sm font-medium text-ink-bg">
                <i className="fas fa-file-lines text-copper-light" />
                最终稿件
              </h3>
              <Button
                className="ml-auto !px-3 !py-1 text-xs"
                onClick={handleCopy}
              >
                <i className={`fas ${copied ? 'fa-check' : 'fa-copy'} mr-1`} />
                {copied ? '已复制' : '复制'}
              </Button>
            </div>
            <div className="max-h-96 overflow-auto rounded-lg bg-ink-dark/60 p-4 text-sm text-ink-bg/80 whitespace-pre-wrap">
              {result.final_content}
            </div>
          </Card>
        </div>
      )}

      {!loading && !result && (
        <EmptyState
          icon="fa-rotate"
          title="自动迭代打磨稿件"
          hint="系统将重复执行审稿 → 评分 → 修订，直到分数达标或达到最大轮数"
        />
      )}
    </div>
  );
}

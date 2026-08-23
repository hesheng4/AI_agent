// 精度对齐 — 状态监控 + 触发对齐 + 报告查看 + 阈值配置
import { useState, useEffect, useCallback } from 'react';
import { PageHeader, Button, Card, Input, Loading, EmptyState, ErrorBanner } from '../../components/ui';
import { alignmentApi } from '../../api';

export default function Alignment() {
  const [status, setStatus] = useState<{ running: boolean; last_result: unknown; error: string | null } | null>(null);
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [thresholds, setThresholds] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [running, setRunning] = useState(false);

  // 表单
  const [baselineUrl, setBaselineUrl] = useState('');
  const [npuUrl, setNpuUrl] = useState('');
  const [model, setModel] = useState('');
  const [maxTokens, setMaxTokens] = useState('128');
  const [temperature, setTemperature] = useState('0');
  const [compareEmbedding, setCompareEmbedding] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, t] = await Promise.all([
        alignmentApi.status(),
        alignmentApi.thresholds().catch(() => null),
      ]);
      setStatus(s);
      setThresholds(t);
      if (!s.running) {
        alignmentApi.report().then(setReport).catch(() => {});
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // 轮询运行状态
  useEffect(() => {
    if (!status?.running) return;
    const timer = setInterval(load, 3000);
    return () => clearInterval(timer);
  }, [status?.running, load]);

  async function handleRun() {
    setRunning(true);
    setError('');
    try {
      await alignmentApi.run({
        baseline_url: baselineUrl,
        npu_url: npuUrl,
        model,
        temperature: parseFloat(temperature),
        max_tokens: parseInt(maxTokens),
        compare_embedding: compareEmbedding,
      });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '触发失败');
    } finally {
      setRunning(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="精度对齐"
        subtitle="GPU 基线 vs NPU 推理结果对比"
        icon="fa-balance-scale"
        action={
          <Button variant="secondary" size="sm" onClick={load}>
            <i className="fas fa-redo mr-1.5" />
            刷新
          </Button>
        }
      />

      {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

      {/* 运行状态 */}
      {status && (
        <Card className="mb-4">
          <div className="flex items-center gap-3">
            <div className={`flex h-3 w-3 items-center justify-center rounded-full ${status.running ? 'bg-jade animate-pulse' : 'bg-ink-bg/30'}`} />
            <span className="text-sm text-ink-bg/80">
              {status.running ? '对齐任务运行中...' : '空闲'}
            </span>
            {status.error && <span className="text-xs text-vermillion">{status.error}</span>}
          </div>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {/* 配置表单 */}
        <Card>
          <h3 className="mb-4 text-sm font-medium text-ink-bg/80">对齐配置</h3>
          <div className="space-y-3">
            <Input label="基线 URL（GPU）" placeholder="http://gpu-host:8000/v1" value={baselineUrl} onChange={e => setBaselineUrl(e.target.value)} />
            <Input label="NPU URL" placeholder="http://npu-host:8000/v1" value={npuUrl} onChange={e => setNpuUrl(e.target.value)} />
            <Input label="模型名称" placeholder="Qwen3.5-27B" value={model} onChange={e => setModel(e.target.value)} />
            <div className="grid grid-cols-2 gap-3">
              <Input label="温度" type="number" step="0.1" value={temperature} onChange={e => setTemperature(e.target.value)} />
              <Input label="最大 tokens" type="number" value={maxTokens} onChange={e => setMaxTokens(e.target.value)} />
            </div>
            <label className="flex cursor-pointer items-center gap-2 text-xs text-ink-bg/60">
              <input type="checkbox" checked={compareEmbedding} onChange={e => setCompareEmbedding(e.target.checked)} className="accent-copper" />
              对比 Embedding 一致性
            </label>
            <Button onClick={handleRun} loading={running} disabled={status?.running}>
              <i className="fas fa-play mr-1.5" />
              {status?.running ? '任务运行中' : '触发对齐'}
            </Button>
          </div>
        </Card>

        {/* 阈值配置 */}
        <Card>
          <h3 className="mb-4 text-sm font-medium text-ink-bg/80">对齐阈值</h3>
          {loading ? <Loading /> : thresholds ? (
            <pre className="max-h-80 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
              {JSON.stringify(thresholds, null, 2)}
            </pre>
          ) : <EmptyState icon="fa-sliders" title="无阈值数据" />}
        </Card>
      </div>

      {/* 对齐报告 */}
      <Card className="mt-4">
        <h3 className="mb-4 text-sm font-medium text-ink-bg/80">对齐报告</h3>
        {report && Object.keys(report).length > 0 ? (
          <pre className="max-h-96 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
            {JSON.stringify(report, null, 2)}
          </pre>
        ) : (
          <EmptyState icon="fa-file-alt" title="暂无对齐报告" hint="触发对齐后报告将显示在此处" />
        )}
      </Card>
    </div>
  );
}

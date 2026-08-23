// 性能采集 — msprofleprof 采集 + ACL Graph + 任务监控
import { useState, useEffect, useCallback } from 'react';
import { PageHeader, Button, Card, Input, Textarea, Loading, EmptyState, ErrorBanner } from '../../components/ui';
import { profilingApi } from '../../api';

export default function Profiling() {
  // 状态数据
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [levels, setLevels] = useState<Record<string, unknown> | null>(null);
  const [envCheck, setEnvCheck] = useState<Record<string, unknown> | null>(null);
  const [results, setResults] = useState<{ count: number; output_dir?: string; results: unknown[] } | null>(null);
  const [checklist, setChecklist] = useState<Record<string, unknown> | null>(null);

  // 交互状态
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [generating, setGenerating] = useState(false);
  const [running, setRunning] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [generatedCmd, setGeneratedCmd] = useState<Record<string, unknown> | null>(null);

  // 任务状态（来自 taskStatus API）
  const [taskStatus, setTaskStatus] = useState<Record<string, unknown> | null>(null);

  // 结果目录
  const [resultsOutputDir, setResultsOutputDir] = useState('./profiling_output');

  // 表单字段
  const [modelPath, setModelPath] = useState('');
  const [inputShape, setInputShape] = useState('');
  const [level, setLevel] = useState('');
  const [outputDir, setOutputDir] = useState('');
  const [command, setCommand] = useState('');

  // 加载所有数据
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, l, e, r, c, ts] = await Promise.all([
        profilingApi.status(),
        profilingApi.levels().catch(() => null),
        profilingApi.envCheck().catch(() => null),
        profilingApi.results(resultsOutputDir).catch(() => null),
        profilingApi.checklist().catch(() => null),
        profilingApi.taskStatus().catch(() => null),
      ]);
      setStatus(s);
      setLevels(l);
      setEnvCheck(e);
      setResults(r);
      setChecklist(c);
      setTaskStatus(ts);
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, [resultsOutputDir]);

  useEffect(() => { load(); }, [load]);

  // 轮询运行状态（3 秒），使用 taskStatus API
  const isRunning = (taskStatus?.running as boolean) || (taskStatus?.status === 'running');

  useEffect(() => {
    if (!isRunning) return;
    const timer = setInterval(async () => {
      try {
        const ts = await profilingApi.taskStatus();
        setTaskStatus(ts);
        // 如果任务已结束，刷新全量数据
        const stillRunning = (ts?.running as boolean) || (ts?.status === 'running');
        if (!stillRunning) load();
      } catch {
        // 轮询失败静默处理
      }
    }, 3000);
    return () => clearInterval(timer);
  }, [isRunning, load]);

  // 生成采集命令
  async function handleGenerate() {
    setGenerating(true);
    setError('');
    try {
      const payload: Record<string, unknown> = {
        model_path: modelPath,
        input_shape: inputShape,
        level,
        output_dir: outputDir,
      };
      if (command.trim()) payload.command = command;
      const res = await profilingApi.generate(payload);
      setGeneratedCmd(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : '生成命令失败');
    } finally {
      setGenerating(false);
    }
  }

  // 启动采集
  async function handleRun() {
    setRunning(true);
    setError('');
    try {
      const payload: Record<string, unknown> = {
        model_path: modelPath,
        input_shape: inputShape,
        level,
        output_dir: outputDir,
      };
      if (command.trim()) payload.command = command;
      await profilingApi.run(payload);
      // 启动后立即刷新状态，触发轮询
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '启动采集失败');
    } finally {
      setRunning(false);
    }
  }

  // 停止采集
  async function handleStop() {
    setStopping(true);
    setError('');
    try {
      await profilingApi.stop();
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '停止采集失败');
    } finally {
      setStopping(false);
    }
  }

  // DeepSpeed 表单字段
  const [dsOutputDir, setDsOutputDir] = useState('./profiling_output');
  const [dsSkipFirst, setDsSkipFirst] = useState('0');
  const [dsWait, setDsWait] = useState('5');
  const [dsWarmup, setDsWarmup] = useState('3');
  const [dsActive, setDsActive] = useState('2');
  const [dsRepeat, setDsRepeat] = useState('1');
  const [dsGenerating, setDsGenerating] = useState(false);
  const [dsResult, setDsResult] = useState<Record<string, unknown> | null>(null);

  // 生成 DeepSpeed 脚本
  async function handleGenerateDeepspeed() {
    setDsGenerating(true);
    setError('');
    try {
      const res = await profilingApi.generateDeepspeed({
        output_dir: dsOutputDir,
        skip_first: Number(dsSkipFirst) || 0,
        wait: Number(dsWait) || 5,
        warmup: Number(dsWarmup) || 3,
        active: Number(dsActive) || 2,
        repeat: Number(dsRepeat) || 1,
      });
      setDsResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : '生成 DeepSpeed 脚本失败');
    } finally {
      setDsGenerating(false);
    }
  }

  // 解析 levels 选项
  // 后端 /profiling/levels 返回 { levels: [{name, description, data_size, use_case, is_default}, ...] }
  const levelOptions: Array<{ value: string; label: string }> = (() => {
    if (!levels) return [];
    const arr = levels.levels as Array<{ name: string; description?: string; is_default?: boolean }> | undefined;
    if (Array.isArray(arr)) {
      return arr.map(o => ({
        value: o.name,
        label: o.is_default ? `${o.name} (默认)` : o.name,
      }));
    }
    return [];
  })();

  // 当前是否运行中（使用 taskStatus 派生的 isRunning，已在上方定义）

  // 环境是否就绪
  const envReady = envCheck ? (envCheck.ready as boolean) ?? (envCheck.status === 'ok') : null;

  return (
    <div>
      <PageHeader
        title="性能采集"
        subtitle="msprofleprof 采集 · ACL Graph · 任务监控"
        icon="fa-stopwatch"
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
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`flex h-3 w-3 items-center justify-center rounded-full ${isRunning ? 'bg-jade animate-pulse' : 'bg-ink-bg/30'}`} />
              <span className="text-sm text-ink-bg/80">
                {isRunning ? '采集任务运行中...' : '空闲'}
              </span>
              {status.error ? <span className="text-xs text-vermillion">{String(status.error)}</span> : null}
              {status.message ? <span className="text-xs text-ink-bg/50">{String(status.message)}</span> : null}
              {taskStatus?.pid ? <span className="text-xs text-ink-bg/60">PID: {String(taskStatus.pid)}</span> : null}
              {taskStatus?.start_time ? <span className="text-xs text-ink-bg/60">启动: {String(taskStatus.start_time)}</span> : null}
            </div>
            {isRunning && (
              <Button variant="secondary" size="sm" onClick={handleStop} loading={stopping}>
                <i className="fas fa-stop mr-1.5" />
                停止采集
              </Button>
            )}
          </div>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {/* 环境检查 */}
        <Card>
          <h3 className="mb-4 text-sm font-medium text-ink-bg/80">环境检查</h3>
          {loading ? <Loading /> : envCheck ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <div className={`flex h-2.5 w-2.5 items-center justify-center rounded-full ${envReady ? 'bg-jade' : 'bg-vermillion'}`} />
                <span className={`text-sm ${envReady ? 'text-jade' : 'text-vermillion'}`}>
                  {envReady ? '环境就绪' : '环境异常'}
                </span>
              </div>
              <pre className="max-h-80 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                {JSON.stringify(envCheck, null, 2)}
              </pre>
            </div>
          ) : <EmptyState icon="fa-vial" title="无环境检查数据" />}
        </Card>

        {/* 采集等级 */}
        <Card>
          <h3 className="mb-4 text-sm font-medium text-ink-bg/80">采集等级</h3>
          {loading ? <Loading /> : levels ? (
            <pre className="max-h-80 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
              {JSON.stringify(levels, null, 2)}
            </pre>
          ) : <EmptyState icon="fa-layer-group" title="无采集等级数据" />}
        </Card>
      </div>

      {/* 采集配置表单 */}
      <Card className="mt-4">
        <h3 className="mb-4 text-sm font-medium text-ink-bg/80">采集配置</h3>
        <div className="space-y-3">
          <Input
            label="模型路径"
            placeholder="/models/Qwen3.5-27B"
            value={modelPath}
            onChange={e => setModelPath(e.target.value)}
          />
          <Input
            label="输入形状"
            placeholder="1,128"
            value={inputShape}
            onChange={e => setInputShape(e.target.value)}
          />
          <label className="block">
            <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">采集等级</span>
            <select
              value={level}
              onChange={e => setLevel(e.target.value)}
              className="w-full rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none focus:ring-1 focus:ring-copper/30"
            >
              <option value="">选择采集等级</option>
              {levelOptions.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </label>
          <Input
            label="输出目录"
            placeholder="/output/profiling"
            value={outputDir}
            onChange={e => setOutputDir(e.target.value)}
          />
          <Textarea
            label="启动命令（可选）"
            rows={3}
            placeholder="自定义启动命令，留空则使用默认命令"
            value={command}
            onChange={e => setCommand(e.target.value)}
          />
          <div className="flex flex-wrap gap-3">
            <Button onClick={handleGenerate} loading={generating} disabled={isRunning}>
              <i className="fas fa-code mr-1.5" />
              生成命令
            </Button>
            <Button onClick={handleRun} loading={running} disabled={isRunning}>
              <i className="fas fa-play mr-1.5" />
              {isRunning ? '任务运行中' : '启动采集'}
            </Button>
          </div>
        </div>
      </Card>

      {/* 生成的命令 */}
      {generatedCmd && (
        <Card className="mt-4">
          <h3 className="mb-4 text-sm font-medium text-ink-bg/80">生成的命令</h3>
          <pre className="max-h-80 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
            {JSON.stringify(generatedCmd, null, 2)}
          </pre>
        </Card>
      )}

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {/* 采集结果 */}
        <Card>
          <h3 className="mb-4 text-sm font-medium text-ink-bg/80">
            采集结果{results ? `（${results.count}）` : ''}
          </h3>
          <div className="mb-3 flex gap-2">
            <Input
              placeholder="输出目录"
              value={resultsOutputDir}
              onChange={e => setResultsOutputDir(e.target.value)}
              className="flex-1"
            />
            <Button variant="secondary" size="sm" onClick={load}>
              <i className="fas fa-sync-alt mr-1.5" />
              刷新结果
            </Button>
          </div>
          {loading ? <Loading /> : results && results.results && results.results.length > 0 ? (
            <div className="space-y-2">
              {results.output_dir && (
                <div className="text-xs text-ink-bg/50">目录: {results.output_dir}</div>
              )}
              {(results.results as Array<Record<string, unknown>>).map((r, i) => (
                <div key={i} className="rounded-lg border border-copper/10 bg-ink-dark/20 p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-ink-bg/80">
                      {String(r.name || r.path || `结果 ${i + 1}`)}
                    </span>
                    {r.total_size_mb != null && <span className="text-xs text-ink-bg/50">{String(r.total_size_mb)} MB</span>}
                  </div>
                  {r.path != null && <div className="mt-1 text-xs text-ink-bg/60">{String(r.path)}</div>}
                  <div className="mt-1 flex gap-3 text-xs text-ink-bg/50">
                    {r.file_count != null && <span>文件数: {String(r.file_count)}</span>}
                    {r.created_at != null && <span>创建: {String(r.created_at)}</span>}
                  </div>
                </div>
              ))}
            </div>
          ) : <EmptyState icon="fa-folder-open" title="暂无采集结果" hint="启动采集后结果将显示在此处" />}
        </Card>

        {/* 采集清单 */}
        <Card>
          <h3 className="mb-4 text-sm font-medium text-ink-bg/80">采集清单</h3>
          {loading ? <Loading /> : checklist ? (
            <pre className="max-h-80 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
              {JSON.stringify(checklist, null, 2)}
            </pre>
          ) : <EmptyState icon="fa-list-check" title="无采集清单数据" />}
        </Card>
      </div>

      {/* DeepSpeed 采集 */}
      <Card className="mt-4">
        <h3 className="mb-4 text-sm font-medium text-ink-bg/80">
          <i className="fas fa-bolt mr-1.5 text-copper" />
          DeepSpeed 采集
        </h3>
        <div className="grid gap-3 lg:grid-cols-3">
          <Input
            label="输出目录"
            placeholder="./profiling_output"
            value={dsOutputDir}
            onChange={e => setDsOutputDir(e.target.value)}
          />
          <Input
            label="跳过前 N 步 (skip_first)"
            placeholder="0"
            value={dsSkipFirst}
            onChange={e => setDsSkipFirst(e.target.value)}
          />
          <Input
            label="等待步数 (wait)"
            placeholder="5"
            value={dsWait}
            onChange={e => setDsWait(e.target.value)}
          />
          <Input
            label="预热步数 (warmup)"
            placeholder="3"
            value={dsWarmup}
            onChange={e => setDsWarmup(e.target.value)}
          />
          <Input
            label="活跃步数 (active)"
            placeholder="2"
            value={dsActive}
            onChange={e => setDsActive(e.target.value)}
          />
          <Input
            label="重复次数 (repeat)"
            placeholder="1"
            value={dsRepeat}
            onChange={e => setDsRepeat(e.target.value)}
          />
        </div>
        <div className="mt-4">
          <Button onClick={handleGenerateDeepspeed} loading={dsGenerating}>
            <i className="fas fa-file-code mr-1.5" />
            生成脚本
          </Button>
        </div>
        {dsResult && (
          <div className="mt-4 space-y-3">
            {typeof dsResult.script === 'string' && dsResult.script && (
              <div>
                <h4 className="mb-2 text-xs font-medium text-ink-bg/60">生成的脚本</h4>
                <pre className="bg-ink p-3 rounded text-sm overflow-auto max-h-96 text-ink-bg/80">
                  {dsResult.script}
                </pre>
              </div>
            )}
            {Array.isArray(dsResult.key_points) && (
              <div>
                <h4 className="mb-2 text-xs font-medium text-ink-bg/60">关键要点</h4>
                <ul className="list-inside list-disc space-y-1 text-sm text-ink-bg/70">
                  {(dsResult.key_points as string[]).map((p, i) => (
                    <li key={i}>{p}</li>
                  ))}
                </ul>
              </div>
            )}
            {typeof dsResult.command === 'string' && dsResult.command && (
              <div>
                <h4 className="mb-2 text-xs font-medium text-ink-bg/60">启动命令</h4>
                <pre className="bg-ink p-3 rounded text-sm overflow-auto max-h-96 text-ink-bg/80">
                  {dsResult.command}
                </pre>
              </div>
            )}
            {/* 兜底：展示完整返回 */}
            {!dsResult.script && !dsResult.key_points && !dsResult.command && (
              <pre className="bg-ink p-3 rounded text-sm overflow-auto max-h-96 text-ink-bg/80">
                {JSON.stringify(dsResult, null, 2)}
              </pre>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}

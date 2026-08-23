// 性能调优 — TCMalloc · NUMA · 推荐配置 · 启动命令
import { useState, useEffect, useCallback } from 'react';
import { PageHeader, Button, Card, Input, Textarea, Badge, Loading, EmptyState, ErrorBanner } from '../../components/ui';
import { perfTuningApi } from '../../api';

export default function PerfTuning() {
  // 状态数据
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [configs, setConfigs] = useState<Record<string, unknown> | null>(null);
  const [tcmalloc, setTcmalloc] = useState<Record<string, unknown> | null>(null);
  const [numa, setNuma] = useState<Record<string, unknown> | null>(null);
  const [verifyEnv, setVerifyEnv] = useState<Record<string, unknown> | null>(null);
  const [quickRef, setQuickRef] = useState<Record<string, unknown> | null>(null);

  // 加载与错误
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState('');
  const [actionMsg, setActionMsg] = useState('');

  // 脚本分析
  const [scriptText, setScriptText] = useState('');
  const [scriptResult, setScriptResult] = useState<Record<string, unknown> | null>(null);
  const [scriptLoading, setScriptLoading] = useState(false);

  // 瓶颈诊断
  const [bnNpuUtil, setBnNpuUtil] = useState('');
  const [bnCubeRatio, setBnCubeRatio] = useState('');
  const [bnCommRatio, setBnCommRatio] = useState('');
  const [bnFreeTimeRatio, setBnFreeTimeRatio] = useState('');
  const [bnCpuOpRatio, setBnCpuOpRatio] = useState('');
  const [bnMemPeakRatio, setBnMemPeakRatio] = useState('');
  const [bnDequeueBlock, setBnDequeueBlock] = useState('');
  const [bnMallocRatio, setBnMallocRatio] = useState('');
  const [bottleneckResult, setBottleneckResult] = useState<Record<string, unknown> | null>(null);
  const [bottleneckLoading, setBottleneckLoading] = useState(false);

  // 代码层优化建议
  const [modelCode, setModelCode] = useState('');
  const [codeOptResult, setCodeOptResult] = useState<Record<string, unknown> | null>(null);
  const [codeOptLoading, setCodeOptLoading] = useState(false);

  // 启动命令结果
  const [launchResult, setLaunchResult] = useState<{ command: string; config: Record<string, unknown> } | null>(null);

  // 表单字段
  const [modelPath, setModelPath] = useState('');
  const [tensorParallelSize, setTensorParallelSize] = useState('1');
  const [maxModelLen, setMaxModelLen] = useState('4096');
  const [maxNumSeqs, setMaxNumSeqs] = useState('256');
  const [enableAclGraph, setEnableAclGraph] = useState(true);
  const [enableTaskQueue, setEnableTaskQueue] = useState(true);

  // 统一加载
  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [s, c, t, n, v, q] = await Promise.all([
        perfTuningApi.status(),
        perfTuningApi.recommendedConfigs().catch(() => null),
        perfTuningApi.detectTcmalloc().catch(() => null),
        perfTuningApi.detectNuma().catch(() => null),
        perfTuningApi.verifyEnv().catch(() => null),
        perfTuningApi.quickReference().catch(() => null),
      ]);
      setStatus(s);
      setConfigs(c);
      setTcmalloc(t);
      setNuma(n);
      setVerifyEnv(v);
      setQuickRef(q);
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // 构造表单数据
  function buildFormData(): Record<string, unknown> {
    return {
      model_path: modelPath,
      tensor_parallel_size: parseInt(tensorParallelSize) || 1,
      max_model_len: parseInt(maxModelLen) || 4096,
      max_num_seqs: parseInt(maxNumSeqs) || 256,
      enable_acl_graph: enableAclGraph,
      enable_task_queue: enableTaskQueue,
    };
  }

  // 生成启动命令
  async function handleLaunch() {
    setActionLoading('launch');
    setActionMsg('');
    try {
      const res = await perfTuningApi.launchCommand(buildFormData());
      setLaunchResult(res);
      setActionMsg('启动命令已生成');
    } catch (e) {
      setActionMsg(e instanceof Error ? e.message : '生成命令失败');
    } finally {
      setActionLoading('');
    }
  }

  // 应用配置
  async function handleApply() {
    setActionLoading('apply');
    setActionMsg('');
    try {
      const res = await perfTuningApi.apply(buildFormData());
      setActionMsg(`配置已应用：${JSON.stringify(res)}`);
      load();
    } catch (e) {
      setActionMsg(e instanceof Error ? e.message : '应用配置失败');
    } finally {
      setActionLoading('');
    }
  }

  // 脚本分析
  async function handleAnalyzeScript() {
    if (!scriptText.trim()) {
      setScriptResult({ error: '请输入 vLLM 启动脚本内容' });
      return;
    }
    setScriptLoading(true);
    setScriptResult(null);
    try {
      const res = await perfTuningApi.analyzeScript(scriptText);
      setScriptResult(res);
    } catch (e) {
      setScriptResult({ error: e instanceof Error ? e.message : '分析脚本失败' });
    } finally {
      setScriptLoading(false);
    }
  }

  // 瓶颈诊断
  async function handleDiagnoseBottleneck() {
    // 校验至少填写一个有效数值
    const vals = [bnNpuUtil, bnCubeRatio, bnCommRatio, bnFreeTimeRatio, bnCpuOpRatio, bnMemPeakRatio, bnDequeueBlock, bnMallocRatio];
    const hasValidInput = vals.some(v => v.trim() !== '' && !isNaN(parseFloat(v)));
    if (!hasValidInput) {
      setBottleneckResult({ error: '请至少填写一个有效的 Profiling 指标数值' });
      return;
    }
    setBottleneckLoading(true);
    setBottleneckResult(null);
    try {
      const data = {
        npu_utilization: parseFloat(bnNpuUtil) || 0,
        cube_op_ratio: parseFloat(bnCubeRatio) || 0,
        communication_op_ratio: parseFloat(bnCommRatio) || 0,
        free_time_ratio: parseFloat(bnFreeTimeRatio) || 0,
        cpu_op_ratio: parseFloat(bnCpuOpRatio) || 0,
        memory_peak_ratio: parseFloat(bnMemPeakRatio) || 0,
        dequeue_block_ratio: parseFloat(bnDequeueBlock) || 0,
        malloc_free_ratio: parseFloat(bnMallocRatio) || 0,
      };
      const res = await perfTuningApi.diagnoseBottleneck(data);
      setBottleneckResult(res);
    } catch (e) {
      setBottleneckResult({ error: e instanceof Error ? e.message : '诊断瓶颈失败' });
    } finally {
      setBottleneckLoading(false);
    }
  }

  // 代码层优化建议
  async function handleSuggestCodeOpt() {
    setCodeOptLoading(true);
    setCodeOptResult(null);
    try {
      const res = await perfTuningApi.suggestCodeOptimizations(modelCode);
      setCodeOptResult(res);
    } catch (e) {
      setCodeOptResult({ error: e instanceof Error ? e.message : '获取建议失败' });
    } finally {
      setCodeOptLoading(false);
    }
  }

  // 安全取值辅助
  const mode = (status?.mode as string) || (status?.llm_mode as string) || 'unknown';
  const optimizationEnabled = Boolean(status?.optimization_enabled ?? status?.optimized ?? false);

  return (
    <div>
      <PageHeader
        title="性能调优"
        subtitle="TCMalloc · NUMA · 推荐配置 · 启动命令"
        icon="fa-gauge-high"
        action={
          <Button variant="secondary" size="sm" onClick={load}>
            <i className="fas fa-redo mr-1.5" />
            刷新
          </Button>
        }
      />

      {error && <div className="mb-4"><ErrorBanner message={error} /></div>}
      {actionMsg && (
        <div className="mb-4 rounded-lg border border-copper/30 bg-copper/10 px-4 py-2.5 text-sm text-copper-light">
          <i className="fas fa-info-circle mr-2" />
          {actionMsg}
        </div>
      )}

      {loading ? (
        <Loading text="加载性能调优信息" />
      ) : (
        <div className="space-y-4">
          {/* 状态卡片 */}
          <Card>
            <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
              <i className="fas fa-circle-info text-copper" />
              调优状态
            </h3>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-lg border border-copper/10 bg-ink-dark/40 p-3">
                <p className="text-xs text-ink-bg/60">当前模式</p>
                <p className="mt-1 text-sm text-copper-light">{mode}</p>
              </div>
              <div className="rounded-lg border border-copper/10 bg-ink-dark/40 p-3">
                <p className="text-xs text-ink-bg/60">优化启用</p>
                <p className="mt-1">
                  <span className={`rounded px-1.5 py-0.5 text-[10px] ${optimizationEnabled ? 'bg-jade/10 text-jade' : 'bg-vermillion/10 text-vermillion'}`}>
                    {optimizationEnabled ? '已启用' : '未启用'}
                  </span>
                </p>
              </div>
              <div className="rounded-lg border border-copper/10 bg-ink-dark/40 p-3">
                <p className="text-xs text-ink-bg/60">原始状态</p>
                <pre className="mt-1 max-h-20 overflow-auto text-[10px] text-ink-bg/60">
                  {JSON.stringify(status, null, 2)}
                </pre>
              </div>
            </div>
          </Card>

          {/* 环境检测：TCMalloc + NUMA */}
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
                <i className="fas fa-memory text-copper" />
                TCMalloc 检测
              </h3>
              {tcmalloc ? (
                <div className="space-y-2 text-xs">
                  <Row label="是否安装" value={
                    <span className={`rounded px-1.5 py-0.5 text-[10px] ${tcmalloc.installed || tcmalloc.available ? 'bg-jade/10 text-jade' : 'bg-vermillion/10 text-vermillion'}`}>
                      {(tcmalloc.installed || tcmalloc.available) ? '已安装' : '未安装'}
                    </span>
                  } />
                  <Row label="版本" value={String(tcmalloc.version ?? tcmalloc.lib_version ?? '-')} />
                  <Row label="路径" value={String(tcmalloc.path ?? tcmalloc.lib_path ?? '-')} />
                  {tcmalloc.error ? (
                    <Row label="错误" value={<span className="text-vermillion">{String(tcmalloc.error)}</span>} />
                  ) : null}
                </div>
              ) : (
                <EmptyState icon="fa-memory" title="无 TCMalloc 检测数据" />
              )}
            </Card>

            <Card>
              <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
                <i className="fas fa-network-wired text-copper" />
                NUMA 检测
              </h3>
              {numa ? (
                <div className="space-y-2 text-xs">
                  <Row label="NUMA 节点数" value={String(numa.numa_nodes ?? numa.node_count ?? '-')} />
                  <Row label="可用" value={
                    <span className={`rounded px-1.5 py-0.5 text-[10px] ${numa.available ? 'bg-jade/10 text-jade' : 'bg-vermillion/10 text-vermillion'}`}>
                      {numa.available ? '是' : '否'}
                    </span>
                  } />
                  <Row label="绑定建议" value={String(numa.bind_advice ?? numa.binding_advice ?? numa.recommendation ?? '-')} />
                  {numa.error ? (
                    <Row label="错误" value={<span className="text-vermillion">{String(numa.error)}</span>} />
                  ) : null}
                </div>
              ) : (
                <EmptyState icon="fa-network-wired" title="无 NUMA 检测数据" />
              )}
            </Card>
          </div>

          {/* 推荐配置 */}
          <Card>
            <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
              <i className="fas fa-list-check text-copper" />
              推荐配置
            </h3>
            {configs ? (
              <pre className="max-h-80 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                {JSON.stringify(configs, null, 2)}
              </pre>
            ) : (
              <EmptyState icon="fa-list-check" title="无推荐配置数据" />
            )}
          </Card>

          {/* 生成启动命令表单 */}
          <Card>
            <h3 className="mb-4 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
              <i className="fas fa-terminal text-copper" />
              生成启动命令
            </h3>
            <div className="space-y-3">
              <Input
                label="模型路径 (model_path)"
                icon="fa-folder-open"
                placeholder="/models/Qwen3.5-27B"
                value={modelPath}
                onChange={e => setModelPath(e.target.value)}
              />
              <div className="grid grid-cols-3 gap-3">
                <Input
                  label="张量并行 (tensor_parallel_size)"
                  type="number"
                  min={1}
                  value={tensorParallelSize}
                  onChange={e => setTensorParallelSize(e.target.value)}
                />
                <Input
                  label="最大序列长度 (max_model_len)"
                  type="number"
                  value={maxModelLen}
                  onChange={e => setMaxModelLen(e.target.value)}
                />
                <Input
                  label="最大批大小 (max_num_seqs)"
                  type="number"
                  value={maxNumSeqs}
                  onChange={e => setMaxNumSeqs(e.target.value)}
                />
              </div>
              <div className="flex flex-wrap gap-6">
                <label className="flex cursor-pointer items-center gap-2 text-xs text-ink-bg/60">
                  <input
                    type="checkbox"
                    checked={enableAclGraph}
                    onChange={e => setEnableAclGraph(e.target.checked)}
                    className="accent-copper"
                  />
                  启用 ACL Graph (enable_acl_graph)
                </label>
                <label className="flex cursor-pointer items-center gap-2 text-xs text-ink-bg/60">
                  <input
                    type="checkbox"
                    checked={enableTaskQueue}
                    onChange={e => setEnableTaskQueue(e.target.checked)}
                    className="accent-copper"
                  />
                  启用 Task Queue (enable_task_queue)
                </label>
              </div>
              <div className="flex gap-2">
                <Button onClick={handleLaunch} loading={actionLoading === 'launch'}>
                  <i className="fas fa-wand-magic-sparkles mr-1.5" />
                  生成命令
                </Button>
                <Button variant="secondary" onClick={handleApply} loading={actionLoading === 'apply'}>
                  <i className="fas fa-check mr-1.5" />
                  应用配置
                </Button>
              </div>

              {/* 启动命令结果 */}
              {launchResult && (
                <div className="space-y-2">
                  <p className="text-xs text-ink-bg/60">启动命令</p>
                  <pre className="overflow-auto rounded-lg border border-copper/20 bg-ink-dark/60 p-3 text-xs text-copper-light">
                    {launchResult.command}
                  </pre>
                  <p className="text-xs text-ink-bg/60">解析后的配置</p>
                  <pre className="max-h-60 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                    {JSON.stringify(launchResult.config, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </Card>

          {/* 环境验证 */}
          <Card>
            <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
              <i className="fas fa-shield-halved text-copper" />
              环境验证
            </h3>
            {verifyEnv ? (
              <pre className="max-h-80 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                {JSON.stringify(verifyEnv, null, 2)}
              </pre>
            ) : (
              <EmptyState icon="fa-shield-halved" title="无环境验证数据" />
            )}
          </Card>

          {/* 快速参考 */}
          <Card>
            <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
              <i className="fas fa-book text-copper" />
              快速参考
            </h3>
            {quickRef ? (
              <pre className="max-h-96 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                {JSON.stringify(quickRef, null, 2)}
              </pre>
            ) : (
              <EmptyState icon="fa-book" title="无快速参考数据" />
            )}
          </Card>

          {/* 脚本分析 */}
          <Card>
            <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
              <i className="fas fa-file-code text-copper" />
              脚本分析
            </h3>
            <div className="space-y-3">
              <Textarea
                label="vLLM 启动脚本内容"
                placeholder="粘贴 vLLM 启动脚本，如 python -m vllm.entrypoints.openai.api_server ..."
                rows={6}
                value={scriptText}
                onChange={e => setScriptText(e.target.value)}
              />
              <Button onClick={handleAnalyzeScript} loading={scriptLoading}>
                <i className="fas fa-magnifying-glass-chart mr-1.5" />
                分析脚本
              </Button>

              {scriptResult && !scriptResult.error && (
                <div className="space-y-3">
                  {/* 摘要 */}
                  {scriptResult.summary ? (
                    <div className="rounded-lg border border-copper/10 bg-ink-dark/40 p-3">
                      <p className="mb-1 text-xs font-medium text-ink-bg/50">摘要</p>
                      <p className="text-sm text-ink-bg/80">{String(scriptResult.summary)}</p>
                    </div>
                  ) : null}

                  {/* 模型架构推断 */}
                  {scriptResult.architecture ? (
                    <div className="rounded-lg border border-copper/10 bg-ink-dark/40 p-3">
                      <p className="mb-1 text-xs font-medium text-ink-bg/50">模型架构推断</p>
                      <p className="text-sm text-ink-bg/80">{String(scriptResult.architecture)}</p>
                    </div>
                  ) : null}

                  {/* 已应用优化列表 */}
                  {Array.isArray(scriptResult.detected_optimizations) && scriptResult.detected_optimizations.length > 0 && (
                    <div className="rounded-lg border border-copper/10 bg-ink-dark/40 p-3">
                      <p className="mb-2 text-xs font-medium text-ink-bg/50">已应用优化</p>
                      <div className="flex flex-wrap gap-1.5">
                        {(scriptResult.detected_optimizations as string[]).map((opt, i) => (
                          <Badge key={i} variant="jade">{opt}</Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 缺失优化建议 */}
                  {Array.isArray(scriptResult.missing_recommendations) && scriptResult.missing_recommendations.length > 0 && (
                    <div className="rounded-lg border border-copper/10 bg-ink-dark/40 p-3">
                      <p className="mb-2 text-xs font-medium text-ink-bg/50">缺失优化建议</p>
                      <div className="space-y-1.5">
                        {(scriptResult.missing_recommendations as Array<{ name?: string; recommendation?: string; impact?: string }>).map((rec, i) => {
                          const impactVariant = rec.impact === 'High' ? 'jade' as const : rec.impact === 'Medium' ? 'copper' as const : 'default' as const;
                          return (
                            <div key={i} className="flex items-center gap-2 text-xs">
                              <Badge variant="vermillion">missing</Badge>
                              <span className="text-ink-bg/70">{rec.name || rec.recommendation || String(rec)}</span>
                              {rec.impact && <Badge variant={impactVariant}>{rec.impact}</Badge>}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Top 3 高影响建议 */}
                  {Array.isArray(scriptResult.top_3_by_impact) && scriptResult.top_3_by_impact.length > 0 && (
                    <div className="rounded-lg border border-jade/20 bg-jade/5 p-3">
                      <p className="mb-2 text-xs font-medium text-jade">
                        <i className="fas fa-bolt mr-1" />
                        Top 3 高影响建议
                      </p>
                      <ol className="list-inside list-decimal space-y-1 text-xs text-ink-bg/80">
                        {(scriptResult.top_3_by_impact as string[]).map((s, i) => (
                          <li key={i}>{s}</li>
                        ))}
                      </ol>
                    </div>
                  )}

                  {/* 警告 */}
                  {Array.isArray(scriptResult.warnings) && scriptResult.warnings.length > 0 && (
                    <div className="rounded-lg border border-vermillion/20 bg-vermillion/5 p-3">
                      <p className="mb-2 text-xs font-medium text-vermillion">
                        <i className="fas fa-triangle-exclamation mr-1" />
                        警告
                      </p>
                      <ul className="space-y-1 text-xs text-vermillion">
                        {(scriptResult.warnings as string[]).map((w, i) => (
                          <li key={i}>{w}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
              {scriptResult?.error ? (
                <p className="text-sm text-vermillion">{String(scriptResult.error)}</p>
              ) : null}
            </div>
          </Card>

          {/* 瓶颈诊断 */}
          <Card>
            <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
              <i className="fas fa-stethoscope text-copper" />
              瓶颈诊断
            </h3>
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Input label="NPU 利用率 (%)" type="number" min={0} max={100} placeholder="0-100" value={bnNpuUtil} onChange={e => setBnNpuUtil(e.target.value)} />
                <Input label="Cube 算子占比 (%)" type="number" min={0} max={100} placeholder="0-100" value={bnCubeRatio} onChange={e => setBnCubeRatio(e.target.value)} />
                <Input label="通信算子占比 (%)" type="number" min={0} max={100} placeholder="0-100" value={bnCommRatio} onChange={e => setBnCommRatio(e.target.value)} />
                <Input label="Free Time 占比 (%)" type="number" min={0} max={100} placeholder="0-100" value={bnFreeTimeRatio} onChange={e => setBnFreeTimeRatio(e.target.value)} />
                <Input label="CPU 算子占比 (%)" type="number" min={0} max={100} placeholder="0-100" value={bnCpuOpRatio} onChange={e => setBnCpuOpRatio(e.target.value)} />
                <Input label="内存峰值占比 (%)" type="number" min={0} max={100} placeholder="0-100" value={bnMemPeakRatio} onChange={e => setBnMemPeakRatio(e.target.value)} />
                <Input label="Dequeue 阻塞占比 (%)" type="number" min={0} max={100} placeholder="0-100" value={bnDequeueBlock} onChange={e => setBnDequeueBlock(e.target.value)} />
                <Input label="malloc/free 占比 (%)" type="number" min={0} max={100} placeholder="0-100" value={bnMallocRatio} onChange={e => setBnMallocRatio(e.target.value)} />
              </div>
              <Button onClick={handleDiagnoseBottleneck} loading={bottleneckLoading}>
                <i className="fas fa-magnifying-glass mr-1.5" />
                诊断瓶颈
              </Button>

              {bottleneckResult && !bottleneckResult.error && (
                <div className="space-y-3">
                  {/* 瓶颈类型 */}
                  {bottleneckResult.bottleneck_type != null && String(bottleneckResult.bottleneck_type) ? (
                    <div className="flex items-center gap-3 rounded-lg border border-copper/10 bg-ink-dark/40 p-3">
                      <span className="text-xs text-ink-bg/50">瓶颈类型</span>
                      <Badge variant={
                        (bottleneckResult.bottleneck_type as string).includes('compute') ? 'jade' :
                        (bottleneckResult.bottleneck_type as string).includes('communication') ? 'copper' :
                        (bottleneckResult.bottleneck_type as string).includes('memory') ? 'vermillion' : 'default'
                      } className="!px-3 !py-1 !text-sm">
                        {String(bottleneckResult.bottleneck_type)}
                      </Badge>
                    </div>
                  ) : null}

                  {/* 置信度 */}
                  {bottleneckResult.confidence != null && String(bottleneckResult.confidence) ? (
                    <div className="rounded-lg border border-copper/10 bg-ink-dark/40 p-3">
                      <p className="text-xs text-ink-bg/50">置信度</p>
                      <p className="mt-1 text-sm text-ink-bg/80">{String(bottleneckResult.confidence)}</p>
                    </div>
                  ) : null}

                  {/* 各维度评分 */}
                  {bottleneckResult.scores != null && typeof bottleneckResult.scores === 'object' && (
                    <div className="rounded-lg border border-copper/10 bg-ink-dark/40 p-3">
                      <p className="mb-2 text-xs font-medium text-ink-bg/50">各维度评分</p>
                      <pre className="overflow-auto text-xs text-ink-bg/70">
                        {JSON.stringify(bottleneckResult.scores, null, 2)}
                      </pre>
                    </div>
                  )}

                  {/* 原因说明 */}
                  {bottleneckResult.reason != null && String(bottleneckResult.reason) ? (
                    <div className="rounded-lg border border-copper/10 bg-ink-dark/40 p-3">
                      <p className="mb-1 text-xs font-medium text-ink-bg/50">原因说明</p>
                      <p className="text-sm text-ink-bg/80">{String(bottleneckResult.reason)}</p>
                    </div>
                  ) : null}

                  {/* 优化建议列表 */}
                  {Array.isArray(bottleneckResult.recommendations) && bottleneckResult.recommendations.length > 0 && (
                    <div className="rounded-lg border border-copper/10 bg-ink-dark/40 p-3">
                      <p className="mb-2 text-xs font-medium text-ink-bg/50">优化建议</p>
                      <ul className="list-inside list-disc space-y-1 text-xs text-ink-bg/80">
                        {(bottleneckResult.recommendations as string[]).map((r, i) => (
                          <li key={i}>{r}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
              {bottleneckResult?.error ? (
                <p className="text-sm text-vermillion">{String(bottleneckResult.error)}</p>
              ) : null}
            </div>
          </Card>

          {/* 代码层优化建议 */}
          <Card>
            <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
              <i className="fas fa-code text-copper" />
              代码层优化建议
            </h3>
            <div className="space-y-3">
              <Textarea
                label="模型代码（可选，不提供则返回通用建议库）"
                placeholder="粘贴模型 Python 代码，如 model.py 内容..."
                rows={6}
                value={modelCode}
                onChange={e => setModelCode(e.target.value)}
              />
              <Button onClick={handleSuggestCodeOpt} loading={codeOptLoading}>
                <i className="fas fa-lightbulb mr-1.5" />
                获取建议
              </Button>

              {codeOptResult && !codeOptResult.error && (
                <div className="space-y-3">
                  {/* 摘要 */}
                  {codeOptResult.summary ? (
                    <div className="rounded-lg border border-copper/10 bg-ink-dark/40 p-3">
                      <p className="mb-1 text-xs font-medium text-ink-bg/50">摘要</p>
                      <p className="text-sm text-ink-bg/80">{String(codeOptResult.summary)}</p>
                    </div>
                  ) : null}

                  {/* 检测到的可优化路径 */}
                  {Array.isArray(codeOptResult.detected_patterns) && codeOptResult.detected_patterns.length > 0 && (
                    <div className="rounded-lg border border-copper/10 bg-ink-dark/40 p-3">
                      <p className="mb-2 text-xs font-medium text-ink-bg/50">检测到的可优化路径</p>
                      <div className="space-y-2">
                        {(codeOptResult.detected_patterns as Array<{ name?: string; pattern?: string; suggested_apis?: string[] }>).map((p, i) => (
                          <div key={i} className="rounded border border-copper/10 bg-ink-dark/30 p-2">
                            <p className="text-xs font-medium text-copper-light">{p.name || p.pattern || `路径 ${i + 1}`}</p>
                            {Array.isArray(p.suggested_apis) && p.suggested_apis.length > 0 && (
                              <div className="mt-1 flex flex-wrap gap-1">
                                {p.suggested_apis.map((api, j) => (
                                  <Badge key={j} variant="jade">{api}</Badge>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 优化原则 */}
                  {Array.isArray(codeOptResult.principles) && codeOptResult.principles.length > 0 && (
                    <div className="rounded-lg border border-copper/10 bg-ink-dark/40 p-3">
                      <p className="mb-2 text-xs font-medium text-ink-bg/50">优化原则</p>
                      <ul className="list-inside list-disc space-y-1 text-xs text-ink-bg/80">
                        {(codeOptResult.principles as string[]).map((p, i) => (
                          <li key={i}>{p}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* 验证清单 */}
                  {Array.isArray(codeOptResult.verification_checklist) && codeOptResult.verification_checklist.length > 0 && (
                    <div className="rounded-lg border border-copper/10 bg-ink-dark/40 p-3">
                      <p className="mb-2 text-xs font-medium text-ink-bg/50">验证清单</p>
                      <ul className="space-y-1 text-xs text-ink-bg/80">
                        {(codeOptResult.verification_checklist as string[]).map((item, i) => (
                          <li key={i} className="flex items-start gap-2">
                            <i className="fas fa-square-check mt-0.5 text-jade" />
                            <span>{item}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* 完整建议库（未提供代码时） */}
                  {codeOptResult.all_suggestions ? (
                    <div className="rounded-lg border border-copper/10 bg-ink-dark/40 p-3">
                      <p className="mb-2 text-xs font-medium text-ink-bg/50">完整建议库</p>
                      <pre className="bg-ink p-3 rounded text-sm overflow-auto max-h-96 text-ink-bg/70">
                        {typeof codeOptResult.all_suggestions === 'string'
                          ? codeOptResult.all_suggestions
                          : JSON.stringify(codeOptResult.all_suggestions, null, 2)}
                      </pre>
                    </div>
                  ) : null}

                  {/* Fallback 模板代码 */}
                  {codeOptResult.fallback_template ? (
                    <div className="rounded-lg border border-copper/10 bg-ink-dark/40 p-3">
                      <p className="mb-2 text-xs font-medium text-ink-bg/50">Fallback 模板代码</p>
                      <pre className="bg-ink p-3 rounded text-sm overflow-auto max-h-96 text-ink-bg/70">
                        {String(codeOptResult.fallback_template)}
                      </pre>
                    </div>
                  ) : null}
                </div>
              )}
              {codeOptResult?.error ? (
                <p className="text-sm text-vermillion">{String(codeOptResult.error)}</p>
              ) : null}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

// 行展示辅助
function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-copper/5 pb-1.5">
      <span className="shrink-0 text-ink-bg/60">{label}</span>
      <span className="break-all text-right text-ink-bg/80">{value}</span>
    </div>
  );
}

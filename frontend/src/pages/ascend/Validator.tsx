// 模型验证 — 部署命令 · 精度验证 · 性能基准 · 端到端 · 模型库
import { useState, useEffect, useCallback } from 'react';
import { PageHeader, Button, Card, Input, Textarea, Loading, EmptyState, ErrorBanner } from '../../components/ui';
import { validatorApi } from '../../api';

// Tab 定义
const TABS = [
  { key: 'deploy', label: '部署命令', icon: 'fa-rocket' },
  { key: 'accuracy', label: '精度验证', icon: 'fa-bullseye' },
  { key: 'benchmark', label: '性能基准', icon: 'fa-tachometer-alt' },
  { key: 'e2e', label: '端到端', icon: 'fa-check-double' },
  { key: 'models', label: '模型库', icon: 'fa-database' },
] as const;

type TabKey = typeof TABS[number]['key'];

// 精度任务选项
const ACCURACY_TASKS = ['mmlu', 'cmmlu', 'ceval', 'gsm8k'] as const;

export default function Validator() {
  // 当前 Tab
  const [activeTab, setActiveTab] = useState<TabKey>('deploy');

  // 顶部状态数据
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [envCheck, setEnvCheck] = useState<Record<string, unknown> | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);

  // 快速参考
  const [quickRef, setQuickRef] = useState<Record<string, unknown> | null>(null);

  // 全局错误
  const [error, setError] = useState('');

  // ===== Tab 1 - 部署命令 =====
  const [deployModel, setDeployModel] = useState('');
  const [deployTp, setDeployTp] = useState('1');
  const [deployPort, setDeployPort] = useState('8000');
  const [deployQuant, setDeployQuant] = useState('');
  const [deployLoading, setDeployLoading] = useState(false);
  const [deployResult, setDeployResult] = useState<Record<string, unknown> | null>(null);

  // ===== Tab 2 - 精度验证 =====
  const [accModel, setAccModel] = useState('');
  const [accDataset, setAccDataset] = useState('');
  const [accTask, setAccTask] = useState<string>('mmlu');
  const [accBatch, setAccBatch] = useState('8');
  const [accLoading, setAccLoading] = useState(false);
  const [accResult, setAccResult] = useState<Record<string, unknown> | null>(null);

  // ===== Tab 3 - 性能基准 =====
  // 服务基准
  const [serveModel, setServeModel] = useState('');
  const [serveUrl, setServeUrl] = useState('');
  const [servePrompts, setServePrompts] = useState('1000');
  const [serveLoading, setServeLoading] = useState(false);
  const [serveResult, setServeResult] = useState<Record<string, unknown> | null>(null);
  // 延迟基准
  const [latencyModel, setLatencyModel] = useState('');
  const [latencyUrl, setLatencyUrl] = useState('');
  const [latencyQps, setLatencyQps] = useState('1');
  const [latencyLoading, setLatencyLoading] = useState(false);
  const [latencyResult, setLatencyResult] = useState<Record<string, unknown> | null>(null);
  // 吞吐基准
  const [tputModel, setTputModel] = useState('');
  const [tputUrl, setTputUrl] = useState('');
  const [tputPrompts, setTputPrompts] = useState('1000');
  const [tputLoading, setTputLoading] = useState(false);
  const [tputResult, setTputResult] = useState<Record<string, unknown> | null>(null);

  // ===== Tab 4 - 端到端 =====
  const [e2eModel, setE2eModel] = useState('');
  const [e2eChecks, setE2eChecks] = useState('accuracy\nlatency\nthroughput');
  const [e2eLoading, setE2eLoading] = useState(false);
  const [e2eResult, setE2eResult] = useState<Record<string, unknown> | null>(null);

  // ===== Tab 5 - 模型库 =====
  const [modelsData, setModelsData] = useState<{ models: unknown[]; presets: Record<string, unknown> } | null>(null);
  const [modelsLoading, setModelsLoading] = useState(false);

  // 加载顶部状态
  const loadStatus = useCallback(async () => {
    setStatusLoading(true);
    try {
      const [s, e] = await Promise.all([
        validatorApi.status().catch(() => null),
        validatorApi.envCheck().catch(() => null),
      ]);
      setStatus(s);
      setEnvCheck(e);
    } finally {
      setStatusLoading(false);
    }
  }, []);

  // 加载快速参考
  const loadQuickRef = useCallback(async () => {
    try {
      const r = await validatorApi.quickReference();
      setQuickRef(r);
    } catch {
      // 静默失败
    }
  }, []);

  useEffect(() => {
    loadStatus();
    loadQuickRef();
  }, [loadStatus, loadQuickRef]);

  // ===== Tab 1 - 生成部署命令 =====
  async function handleDeploy() {
    setDeployLoading(true);
    setError('');
    try {
      const payload: Record<string, unknown> = {
        model: deployModel,
        tensor_parallel_size: parseInt(deployTp) || 1,
        port: parseInt(deployPort) || 8000,
      };
      if (deployQuant.trim()) payload.quantization = deployQuant.trim();
      const res = await validatorApi.deployCommand(payload);
      setDeployResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : '生成部署命令失败');
    } finally {
      setDeployLoading(false);
    }
  }

  // ===== Tab 2 - 运行精度验证 =====
  async function handleAccuracy() {
    setAccLoading(true);
    setError('');
    try {
      const payload: Record<string, unknown> = {
        model: accModel,
        dataset: accDataset,
        task: accTask,
        batch_size: parseInt(accBatch) || 1,
      };
      const res = await validatorApi.accuracy(payload);
      setAccResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : '精度验证失败');
    } finally {
      setAccLoading(false);
    }
  }

  // ===== Tab 3 - 性能基准 =====
  async function handleServe() {
    setServeLoading(true);
    setError('');
    try {
      const res = await validatorApi.benchmarkServe({
        model: serveModel,
        url: serveUrl,
        num_prompts: parseInt(servePrompts) || 1000,
      });
      setServeResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : '服务基准失败');
    } finally {
      setServeLoading(false);
    }
  }

  async function handleLatency() {
    setLatencyLoading(true);
    setError('');
    try {
      const res = await validatorApi.benchmarkLatency({
        model: latencyModel,
        url: latencyUrl,
        qps: parseFloat(latencyQps) || 1,
      });
      setLatencyResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : '延迟基准失败');
    } finally {
      setLatencyLoading(false);
    }
  }

  async function handleThroughput() {
    setTputLoading(true);
    setError('');
    try {
      const res = await validatorApi.benchmarkThroughput({
        model: tputModel,
        url: tputUrl,
        num_prompts: parseInt(tputPrompts) || 1000,
      });
      setTputResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : '吞吐基准失败');
    } finally {
      setTputLoading(false);
    }
  }

  // ===== Tab 4 - 端到端 =====
  async function handleE2E() {
    setE2eLoading(true);
    setError('');
    try {
      const checks = e2eChecks
        .split('\n')
        .map(s => s.trim())
        .filter(Boolean);
      const res = await validatorApi.run({
        model: e2eModel,
        checks,
      });
      setE2eResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : '端到端验证失败');
    } finally {
      setE2eLoading(false);
    }
  }

  // ===== Tab 5 - 加载模型库 =====
  async function loadModels() {
    setModelsLoading(true);
    setError('');
    try {
      const res = await validatorApi.models();
      setModelsData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载模型库失败');
    } finally {
      setModelsLoading(false);
    }
  }

  // 切换到模型库 Tab 时自动加载
  useEffect(() => {
    if (activeTab === 'models' && !modelsData && !modelsLoading) {
      loadModels();
    }
  }, [activeTab, modelsData, modelsLoading]);

  // 环境是否就绪
  const envReady = envCheck ? (envCheck.ready as boolean) ?? (envCheck.status === 'ok') : null;

  return (
    <div>
      <PageHeader
        title="模型验证"
        subtitle="部署 · 精度 · 性能 · 端到端"
        icon="fa-check-double"
        action={
          <Button variant="secondary" size="sm" onClick={loadStatus}>
            <i className="fas fa-redo mr-1.5" />
            刷新
          </Button>
        }
      />

      {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

      {/* 顶部状态卡片 */}
      <div className="mb-4 grid gap-4 lg:grid-cols-2">
        <Card>
          <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
            <i className="fas fa-signal text-copper" />
            验证状态
          </h3>
          {statusLoading ? <Loading /> : status ? (
            <pre className="max-h-60 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
              {JSON.stringify(status, null, 2)}
            </pre>
          ) : <EmptyState icon="fa-signal" title="无状态数据" />}
        </Card>

        <Card>
          <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
            <i className="fas fa-vial text-copper" />
            环境检查
          </h3>
          {statusLoading ? <Loading /> : envCheck ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <div className={`flex h-2.5 w-2.5 items-center justify-center rounded-full ${envReady ? 'bg-jade' : 'bg-vermillion'}`} />
                <span className={`text-sm ${envReady ? 'text-jade' : 'text-vermillion'}`}>
                  {envReady ? '环境就绪' : '环境异常'}
                </span>
              </div>
              <pre className="max-h-48 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                {JSON.stringify(envCheck, null, 2)}
              </pre>
            </div>
          ) : <EmptyState icon="fa-vial" title="无环境检查数据" />}
        </Card>
      </div>

      {/* Tab 切换按钮组 */}
      <div className="mb-4 flex flex-wrap gap-2">
        {TABS.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex cursor-pointer items-center gap-2 rounded-lg border px-4 py-2 text-sm transition-colors duration-200 ${
              activeTab === tab.key
                ? 'border-copper/40 bg-copper/10 text-copper'
                : 'border-copper/10 bg-ink-dark/40 text-ink-bg/60 hover:border-copper/30 hover:text-copper-light'
            }`}
          >
            <i className={`fas ${tab.icon}`} />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab 内容 */}
      {activeTab === 'deploy' && (
        <Card>
          <h3 className="mb-4 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
            <i className="fas fa-rocket text-copper" />
            生成部署命令
          </h3>
          <div className="space-y-3">
            <Input
              label="模型"
              placeholder="Qwen3.5-27B"
              value={deployModel}
              onChange={e => setDeployModel(e.target.value)}
            />
            <div className="grid grid-cols-2 gap-3">
              <Input
                label="张量并行"
                type="number"
                min={1}
                value={deployTp}
                onChange={e => setDeployTp(e.target.value)}
              />
              <Input
                label="端口"
                type="number"
                value={deployPort}
                onChange={e => setDeployPort(e.target.value)}
              />
            </div>
            <Input
              label="量化方法（可选）"
              placeholder="w8a8 / w8a16 / 留空"
              value={deployQuant}
              onChange={e => setDeployQuant(e.target.value)}
            />
            <Button onClick={handleDeploy} loading={deployLoading}>
              <i className="fas fa-code mr-1.5" />
              生成部署命令
            </Button>
          </div>

          {deployResult && (
            <div className="mt-4">
              <h4 className="mb-2 text-xs font-medium text-ink-bg/60">部署命令输出</h4>
              <pre className="max-h-96 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                {JSON.stringify(deployResult, null, 2)}
              </pre>
            </div>
          )}
        </Card>
      )}

      {activeTab === 'accuracy' && (
        <Card>
          <h3 className="mb-4 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
            <i className="fas fa-bullseye text-copper" />
            精度验证
          </h3>
          <div className="space-y-3">
            <Input
              label="模型"
              placeholder="Qwen3.5-27B"
              value={accModel}
              onChange={e => setAccModel(e.target.value)}
            />
            <Input
              label="数据集"
              placeholder="mmlu / cmmlu / ceval / gsm8k"
              value={accDataset}
              onChange={e => setAccDataset(e.target.value)}
            />
            <label className="block">
              <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">任务</span>
              <select
                value={accTask}
                onChange={e => setAccTask(e.target.value)}
                className="w-full rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none focus:ring-1 focus:ring-copper/30"
              >
                {ACCURACY_TASKS.map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </label>
            <Input
              label="批大小"
              type="number"
              min={1}
              value={accBatch}
              onChange={e => setAccBatch(e.target.value)}
            />
            <Button onClick={handleAccuracy} loading={accLoading}>
              <i className="fas fa-play mr-1.5" />
              运行精度验证
            </Button>
          </div>

          {accResult && (
            <div className="mt-4">
              <h4 className="mb-2 text-xs font-medium text-ink-bg/60">精度验证结果</h4>
              <pre className="max-h-96 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                {JSON.stringify(accResult, null, 2)}
              </pre>
            </div>
          )}
        </Card>
      )}

      {activeTab === 'benchmark' && (
        <div className="grid gap-4 lg:grid-cols-3">
          {/* 服务基准 */}
          <Card>
            <h3 className="mb-4 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
              <i className="fas fa-server text-copper" />
              服务基准
            </h3>
            <div className="space-y-3">
              <Input
                label="模型"
                placeholder="Qwen3.5-27B"
                value={serveModel}
                onChange={e => setServeModel(e.target.value)}
              />
              <Input
                label="URL"
                placeholder="http://localhost:8000/v1"
                value={serveUrl}
                onChange={e => setServeUrl(e.target.value)}
              />
              <Input
                label="提示数"
                type="number"
                min={1}
                value={servePrompts}
                onChange={e => setServePrompts(e.target.value)}
              />
              <Button onClick={handleServe} loading={serveLoading} size="sm">
                <i className="fas fa-play mr-1.5" />
                运行
              </Button>
            </div>
            {serveResult && (
              <pre className="mt-3 max-h-60 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                {JSON.stringify(serveResult, null, 2)}
              </pre>
            )}
          </Card>

          {/* 延迟基准 */}
          <Card>
            <h3 className="mb-4 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
              <i className="fas fa-stopwatch text-copper" />
              延迟基准
            </h3>
            <div className="space-y-3">
              <Input
                label="模型"
                placeholder="Qwen3.5-27B"
                value={latencyModel}
                onChange={e => setLatencyModel(e.target.value)}
              />
              <Input
                label="URL"
                placeholder="http://localhost:8000/v1"
                value={latencyUrl}
                onChange={e => setLatencyUrl(e.target.value)}
              />
              <Input
                label="QPS"
                type="number"
                step="0.1"
                min={0}
                value={latencyQps}
                onChange={e => setLatencyQps(e.target.value)}
              />
              <Button onClick={handleLatency} loading={latencyLoading} size="sm">
                <i className="fas fa-play mr-1.5" />
                运行
              </Button>
            </div>
            {latencyResult && (
              <pre className="mt-3 max-h-60 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                {JSON.stringify(latencyResult, null, 2)}
              </pre>
            )}
          </Card>

          {/* 吞吐基准 */}
          <Card>
            <h3 className="mb-4 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
              <i className="fas fa-tachometer-alt text-copper" />
              吞吐基准
            </h3>
            <div className="space-y-3">
              <Input
                label="模型"
                placeholder="Qwen3.5-27B"
                value={tputModel}
                onChange={e => setTputModel(e.target.value)}
              />
              <Input
                label="URL"
                placeholder="http://localhost:8000/v1"
                value={tputUrl}
                onChange={e => setTputUrl(e.target.value)}
              />
              <Input
                label="提示数"
                type="number"
                min={1}
                value={tputPrompts}
                onChange={e => setTputPrompts(e.target.value)}
              />
              <Button onClick={handleThroughput} loading={tputLoading} size="sm">
                <i className="fas fa-play mr-1.5" />
                运行
              </Button>
            </div>
            {tputResult && (
              <pre className="mt-3 max-h-60 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                {JSON.stringify(tputResult, null, 2)}
              </pre>
            )}
          </Card>
        </div>
      )}

      {activeTab === 'e2e' && (
        <Card>
          <h3 className="mb-4 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
            <i className="fas fa-check-double text-copper" />
            端到端验证
          </h3>
          <div className="space-y-3">
            <Input
              label="模型"
              placeholder="Qwen3.5-27B"
              value={e2eModel}
              onChange={e => setE2eModel(e.target.value)}
            />
            <Textarea
              label="验证项（每行一项）"
              rows={5}
              placeholder="accuracy&#10;latency&#10;throughput"
              value={e2eChecks}
              onChange={e => setE2eChecks(e.target.value)}
            />
            <Button onClick={handleE2E} loading={e2eLoading}>
              <i className="fas fa-play mr-1.5" />
              运行端到端验证
            </Button>
          </div>

          {e2eResult && (
            <div className="mt-4">
              <h4 className="mb-2 text-xs font-medium text-ink-bg/60">端到端验证结果</h4>
              <pre className="max-h-96 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                {JSON.stringify(e2eResult, null, 2)}
              </pre>
            </div>
          )}
        </Card>
      )}

      {activeTab === 'models' && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
              <i className="fas fa-list text-copper" />
              支持模型
            </h3>
            {modelsLoading ? <Loading /> : modelsData && modelsData.models && modelsData.models.length > 0 ? (
              <pre className="max-h-96 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                {JSON.stringify(modelsData.models, null, 2)}
              </pre>
            ) : <EmptyState icon="fa-database" title="暂无模型数据" hint="点击刷新重试" />}
          </Card>

          <Card>
            <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
              <i className="fas fa-sliders text-copper" />
              预设配置
            </h3>
            {modelsLoading ? <Loading /> : modelsData && modelsData.presets && Object.keys(modelsData.presets).length > 0 ? (
              <pre className="max-h-96 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                {JSON.stringify(modelsData.presets, null, 2)}
              </pre>
            ) : <EmptyState icon="fa-sliders" title="暂无预设配置" />}
          </Card>
        </div>
      )}

      {/* 底部快速参考 */}
      <Card className="mt-4">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
          <i className="fas fa-book text-copper" />
          快速参考
        </h3>
        {quickRef ? (
          <pre className="max-h-96 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
            {JSON.stringify(quickRef, null, 2)}
          </pre>
        ) : (
          <EmptyState icon="fa-book" title="暂无快速参考数据" />
        )}
      </Card>
    </div>
  );
}

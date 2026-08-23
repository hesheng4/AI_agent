// 推理工具链 — vLLM-Ascend 部署 · 量化 · 诊断 · AISBench
import { useState, useEffect, useCallback } from 'react';
import { PageHeader, Button, Card, Input, Textarea, Loading, EmptyState, ErrorBanner } from '../../components/ui';
import { toolchainApi } from '../../api';

// Tab 配置
const TABS = [
  { key: 'env', label: '环境检查', icon: 'fa-microchip' },
  { key: 'vllm', label: 'vLLM 部署', icon: 'fa-rocket' },
  { key: 'quant', label: '量化', icon: 'fa-compress-arrows-alt' },
  { key: 'diag', label: '诊断', icon: 'fa-stethoscope' },
  { key: 'bench', label: 'AISBench', icon: 'fa-tachometer-alt' },
] as const;

type TabKey = typeof TABS[number]['key'];

export default function Toolchain() {
  const [activeTab, setActiveTab] = useState<TabKey>('env');

  // ===== 通用状态 =====
  const [error, setError] = useState('');
  const [quickRef, setQuickRef] = useState<Record<string, unknown> | null>(null);
  const [quickRefLoading, setQuickRefLoading] = useState(false);

  // ===== Tab 1: 环境检查 =====
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [hardware, setHardware] = useState<Record<string, unknown> | null>(null);
  const [verifyEnv, setVerifyEnv] = useState<Record<string, unknown> | null>(null);
  const [envLoading, setEnvLoading] = useState(false);
  const [deviceIds, setDeviceIds] = useState('0,1,2,3');
  const [envSetupResult, setEnvSetupResult] = useState<Record<string, unknown> | null>(null);
  const [envSetupLoading, setEnvSetupLoading] = useState(false);

  // ===== Tab 2: vLLM 部署 =====
  const [installGuide, setInstallGuide] = useState<Record<string, unknown> | null>(null);
  const [installLoading, setInstallLoading] = useState(false);
  const [vllmModelPath, setVllmModelPath] = useState('');
  const [tensorParallel, setTensorParallel] = useState('1');
  const [vllmPort, setVllmPort] = useState('8000');
  const [maxModelLen, setMaxModelLen] = useState('');
  const [launchResult, setLaunchResult] = useState<{ command: string; config: Record<string, unknown>; notes: string[] } | null>(null);
  const [launchLoading, setLaunchLoading] = useState(false);

  // ===== Tab 3: 量化 =====
  const [quantModelPath, setQuantModelPath] = useState('');
  const [quantMethod, setQuantMethod] = useState<'w8a8' | 'w8a16' | 'w4a16'>('w8a8');
  const [calibDataset, setCalibDataset] = useState('');
  const [outputPath, setOutputPath] = useState('');
  const [quantResult, setQuantResult] = useState<Record<string, unknown> | null>(null);
  const [quantLoading, setQuantLoading] = useState(false);

  // ===== Tab 4: 诊断 =====
  const [errorOutput, setErrorOutput] = useState('');
  const [diagResult, setDiagResult] = useState<{ diagnoses: unknown[]; error_output_preview: string } | null>(null);
  const [diagLoading, setDiagLoading] = useState(false);

  // ===== Tab 5: AISBench =====
  const [benchModel, setBenchModel] = useState('');
  const [benchDataset, setBenchDataset] = useState('');
  const [batchSize, setBatchSize] = useState('1');
  const [benchResult, setBenchResult] = useState<Record<string, unknown> | null>(null);
  const [benchLoading, setBenchLoading] = useState(false);

  // ===== 加载快速参考（底部固定卡片） =====
  const loadQuickRef = useCallback(async () => {
    setQuickRefLoading(true);
    try {
      const ref = await toolchainApi.quickReference();
      setQuickRef(ref);
    } catch {
      // 静默失败，不打扰主流程
    } finally {
      setQuickRefLoading(false);
    }
  }, []);

  useEffect(() => { loadQuickRef(); }, [loadQuickRef]);

  // ===== Tab 1: 环境检查加载 =====
  const loadEnv = useCallback(async () => {
    setEnvLoading(true);
    setError('');
    try {
      const [s, h, v] = await Promise.all([
        toolchainApi.status().catch(e => { setError(e.message); return null; }),
        toolchainApi.hardwareCheck().catch(() => null),
        toolchainApi.verifyEnvironment().catch(() => null),
      ]);
      setStatus(s);
      setHardware(h);
      setVerifyEnv(v);
    } finally {
      setEnvLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'env') loadEnv();
  }, [activeTab, loadEnv]);

  // ===== Tab 2: vLLM 安装指南加载 =====
  const loadInstallGuide = useCallback(async () => {
    setInstallLoading(true);
    try {
      const guide = await toolchainApi.vllmInstallGuide();
      setInstallGuide(guide);
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载安装指南失败');
    } finally {
      setInstallLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'vllm' && !installGuide) loadInstallGuide();
  }, [activeTab, installGuide, loadInstallGuide]);

  // ===== 环境配置 =====
  async function handleEnvSetup() {
    setEnvSetupLoading(true);
    setError('');
    try {
      const res = await toolchainApi.envSetup(deviceIds);
      setEnvSetupResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : '环境配置失败');
    } finally {
      setEnvSetupLoading(false);
    }
  }

  // ===== 生成 vLLM 启动命令 =====
  async function handleVllmLaunch() {
    if (!vllmModelPath.trim()) {
      setError('请输入模型路径');
      return;
    }
    setLaunchLoading(true);
    setError('');
    try {
      const res = await toolchainApi.vllmLaunch({
        model_path: vllmModelPath,
        tensor_parallel_size: parseInt(tensorParallel) || 1,
        port: parseInt(vllmPort) || 8000,
        max_model_len: maxModelLen ? parseInt(maxModelLen) : undefined,
      });
      setLaunchResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : '生成启动命令失败');
    } finally {
      setLaunchLoading(false);
    }
  }

  // ===== 触发量化 =====
  async function handleQuantize() {
    if (!quantModelPath.trim() || !outputPath.trim()) {
      setError('模型路径和输出路径不能为空');
      return;
    }
    setQuantLoading(true);
    setError('');
    try {
      const res = await toolchainApi.quantize({
        model_path: quantModelPath,
        quant_method: quantMethod,
        calib_dataset: calibDataset,
        output_path: outputPath,
      });
      setQuantResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : '量化失败');
    } finally {
      setQuantLoading(false);
    }
  }

  // ===== 诊断 =====
  async function handleDiagnose() {
    setDiagLoading(true);
    setError('');
    try {
      const res = await toolchainApi.vllmDiagnose(errorOutput);
      setDiagResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : '诊断失败');
    } finally {
      setDiagLoading(false);
    }
  }

  // ===== AISBench =====
  async function handleAisbench() {
    setBenchLoading(true);
    setError('');
    try {
      const res = await toolchainApi.aisbench({
        model: benchModel,
        dataset: benchDataset,
        batch_size: parseInt(batchSize) || 1,
      });
      setBenchResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : '基准测试失败');
    } finally {
      setBenchLoading(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="推理工具链"
        subtitle="vLLM-Ascend 部署 · 量化 · 诊断 · AISBench"
        icon="fa-toolbox"
        action={
          <Button variant="secondary" size="sm" onClick={loadQuickRef} loading={quickRefLoading}>
            <i className="fas fa-redo mr-1.5" />
            刷新参考
          </Button>
        }
      />

      {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

      {/* Tab 切换按钮组 */}
      <div className="mb-6 flex flex-wrap gap-2 rounded-xl border border-copper/10 bg-ink-dark/40 p-1.5">
        {TABS.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200 ${
              activeTab === tab.key
                ? 'bg-copper/10 text-copper'
                : 'text-ink-bg/60 hover:text-copper-light hover:bg-copper/5'
            }`}
          >
            <i className={`fas ${tab.icon} text-xs`} />
            {tab.label}
          </button>
        ))}
      </div>

      {/* ===== Tab 1: 环境检查 ===== */}
      {activeTab === 'env' && (
        <div className="space-y-4">
          {envLoading ? <Loading text="加载环境状态" /> : (
            <>
              <div className="grid gap-4 lg:grid-cols-2">
                {/* 状态卡片 */}
                <Card>
                  <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
                    <i className="fas fa-info-circle text-copper" />
                    工具链状态
                  </h3>
                  {status ? (
                    <pre className="max-h-80 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                      {JSON.stringify(status, null, 2)}
                    </pre>
                  ) : (
                    <EmptyState icon="fa-info-circle" title="无状态数据" />
                  )}
                </Card>

                {/* 硬件检查 */}
                <Card>
                  <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
                    <i className="fas fa-server text-copper" />
                    硬件检查
                  </h3>
                  {hardware ? (
                    <pre className="max-h-80 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                      {JSON.stringify(hardware, null, 2)}
                    </pre>
                  ) : (
                    <EmptyState icon="fa-server" title="无硬件数据" />
                  )}
                </Card>
              </div>

              {/* 环境验证 */}
              <Card>
                <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
                  <i className="fas fa-check-double text-copper" />
                  环境验证
                </h3>
                {verifyEnv ? (
                  <pre className="max-h-80 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                    {JSON.stringify(verifyEnv, null, 2)}
                  </pre>
                ) : (
                  <EmptyState icon="fa-check-double" title="无验证数据" />
                )}
              </Card>

              {/* 环境配置 */}
              <Card>
                <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
                  <i className="fas fa-cogs text-copper" />
                  环境配置
                </h3>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                  <div className="flex-1">
                    <Input
                      label="设备 ID 列表（逗号分隔）"
                      icon="fa-microchip"
                      placeholder="0,1,2,3"
                      value={deviceIds}
                      onChange={e => setDeviceIds(e.target.value)}
                    />
                  </div>
                  <Button onClick={handleEnvSetup} loading={envSetupLoading}>
                    <i className="fas fa-play mr-1.5" />
                    执行环境配置
                  </Button>
                </div>
                {envSetupResult && (
                  <pre className="mt-3 max-h-80 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                    {JSON.stringify(envSetupResult, null, 2)}
                  </pre>
                )}
              </Card>
            </>
          )}
        </div>
      )}

      {/* ===== Tab 2: vLLM 部署 ===== */}
      {activeTab === 'vllm' && (
        <div className="space-y-4">
          {/* 安装指南 */}
          <Card>
            <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
              <i className="fas fa-book text-copper" />
              vLLM-Ascend 安装指南
            </h3>
            {installLoading ? <Loading text="加载安装指南" /> : installGuide ? (
              <pre className="max-h-96 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                {JSON.stringify(installGuide, null, 2)}
              </pre>
            ) : <EmptyState icon="fa-book" title="无安装指南数据" />}
          </Card>

          {/* 启动命令表单 */}
          <Card>
            <h3 className="mb-4 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
              <i className="fas fa-rocket text-copper" />
              生成启动命令
            </h3>
            <div className="space-y-3">
              <Input
                label="模型路径 (model_path)"
                icon="fa-folder"
                placeholder="/models/Qwen3-32B"
                value={vllmModelPath}
                onChange={e => setVllmModelPath(e.target.value)}
              />
              <div className="grid gap-3 sm:grid-cols-3">
                <Input
                  label="张量并行 (tensor_parallel_size)"
                  type="number"
                  min={1}
                  placeholder="1"
                  value={tensorParallel}
                  onChange={e => setTensorParallel(e.target.value)}
                />
                <Input
                  label="端口 (port)"
                  type="number"
                  placeholder="8000"
                  value={vllmPort}
                  onChange={e => setVllmPort(e.target.value)}
                />
                <Input
                  label="最大序列长度 (max_model_len)"
                  type="number"
                  placeholder="留空使用模型默认"
                  value={maxModelLen}
                  onChange={e => setMaxModelLen(e.target.value)}
                />
              </div>
              <Button onClick={handleVllmLaunch} loading={launchLoading}>
                <i className="fas fa-terminal mr-1.5" />
                生成启动命令
              </Button>
            </div>

            {launchResult && (
              <div className="mt-4 space-y-3">
                <div>
                  <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">启动命令</span>
                  <pre className="overflow-auto rounded-lg border border-copper/20 bg-ink-dark/60 p-3 text-xs text-copper-light">
                    {launchResult.command}
                  </pre>
                </div>
                {launchResult.notes && launchResult.notes.length > 0 && (
                  <div>
                    <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">注意事项</span>
                    <ul className="space-y-1 rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                      {launchResult.notes.map((note, i) => (
                        <li key={i} className="flex gap-2">
                          <i className="fas fa-circle-info mt-0.5 text-copper/60" />
                          <span>{String(note)}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                <div>
                  <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">完整配置</span>
                  <pre className="max-h-60 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                    {JSON.stringify(launchResult.config, null, 2)}
                  </pre>
                </div>
              </div>
            )}
          </Card>
        </div>
      )}

      {/* ===== Tab 3: 量化 ===== */}
      {activeTab === 'quant' && (
        <Card>
          <h3 className="mb-4 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
            <i className="fas fa-compress-arrows-alt text-copper" />
            模型量化
          </h3>
          <div className="space-y-3">
            <Input
              label="模型路径 (model_path)"
              icon="fa-folder"
              placeholder="/models/Qwen3-32B"
              value={quantModelPath}
              onChange={e => setQuantModelPath(e.target.value)}
            />
            <div>
              <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">量化方法 (quant_method)</span>
              <select
                value={quantMethod}
                onChange={e => setQuantMethod(e.target.value as 'w8a8' | 'w8a16' | 'w4a16')}
                className="w-full rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none focus:ring-1 focus:ring-copper/30"
              >
                <option value="w8a8">w8a8（权重 8bit · 激活 8bit）</option>
                <option value="w8a16">w8a16（权重 8bit · 激活 16bit）</option>
                <option value="w4a16">w4a16（权重 4bit · 激活 16bit）</option>
              </select>
            </div>
            <Input
              label="校准数据集 (calib_dataset)"
              icon="fa-database"
              placeholder="pileval / wikitext"
              value={calibDataset}
              onChange={e => setCalibDataset(e.target.value)}
            />
            <Input
              label="输出路径 (output_path)"
              icon="fa-folder-open"
              placeholder="/models/Qwen3-32B-w8a8"
              value={outputPath}
              onChange={e => setOutputPath(e.target.value)}
            />
            <Button onClick={handleQuantize} loading={quantLoading}>
              <i className="fas fa-bolt mr-1.5" />
              触发量化
            </Button>
          </div>

          {quantResult && (
            <div className="mt-4">
              <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">量化结果</span>
              <pre className="max-h-96 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                {JSON.stringify(quantResult, null, 2)}
              </pre>
            </div>
          )}
        </Card>
      )}

      {/* ===== Tab 4: 诊断 ===== */}
      {activeTab === 'diag' && (
        <Card>
          <h3 className="mb-4 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
            <i className="fas fa-stethoscope text-copper" />
            错误诊断
          </h3>
          <div className="space-y-3">
            <Textarea
              label="错误输出 (error_output)"
              rows={10}
              placeholder="粘贴 vLLM-Ascend 运行时的错误日志或异常输出..."
              value={errorOutput}
              onChange={e => setErrorOutput(e.target.value)}
            />
            <Button onClick={handleDiagnose} loading={diagLoading} disabled={!errorOutput.trim()}>
              <i className="fas fa-search mr-1.5" />
              诊断错误
            </Button>
          </div>

          {diagResult && (
            <div className="mt-4 space-y-3">
              {diagResult.error_output_preview && (
                <div>
                  <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">错误输出预览</span>
                  <pre className="max-h-40 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-vermillion/80">
                    {diagResult.error_output_preview}
                  </pre>
                </div>
              )}
              <div>
                <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">诊断结果</span>
                {diagResult.diagnoses && diagResult.diagnoses.length > 0 ? (
                  <pre className="max-h-96 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                    {JSON.stringify(diagResult.diagnoses, null, 2)}
                  </pre>
                ) : (
                  <EmptyState icon="fa-stethoscope" title="未识别到已知错误模式" hint="请检查错误输出是否完整" />
                )}
              </div>
            </div>
          )}
        </Card>
      )}

      {/* ===== Tab 5: AISBench ===== */}
      {activeTab === 'bench' && (
        <Card>
          <h3 className="mb-4 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
            <i className="fas fa-tachometer-alt text-copper" />
            AISBench 性能基准
          </h3>
          <div className="space-y-3">
            <Input
              label="模型 (model)"
              icon="fa-cube"
              placeholder="Qwen3-32B"
              value={benchModel}
              onChange={e => setBenchModel(e.target.value)}
            />
            <Input
              label="数据集 (dataset)"
              icon="fa-database"
              placeholder="mmlu / gsm8k / ceval"
              value={benchDataset}
              onChange={e => setBenchDataset(e.target.value)}
            />
            <Input
              label="批大小 (batch_size)"
              type="number"
              min={1}
              placeholder="1"
              value={batchSize}
              onChange={e => setBatchSize(e.target.value)}
            />
            <Button onClick={handleAisbench} loading={benchLoading}>
              <i className="fas fa-play mr-1.5" />
              运行基准测试
            </Button>
          </div>

          {benchResult && (
            <div className="mt-4">
              <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">基准结果</span>
              <pre className="max-h-96 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                {JSON.stringify(benchResult, null, 2)}
              </pre>
            </div>
          )}
        </Card>
      )}

      {/* ===== 底部固定：快速参考 ===== */}
      <Card className="mt-6">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
          <i className="fas fa-bookmark text-copper" />
          快速参考
        </h3>
        {quickRefLoading ? (
          <Loading text="加载快速参考" />
        ) : quickRef ? (
          <pre className="max-h-96 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
            {JSON.stringify(quickRef, null, 2)}
          </pre>
        ) : (
          <EmptyState icon="fa-bookmark" title="无快速参考数据" />
        )}
      </Card>
    </div>
  );
}

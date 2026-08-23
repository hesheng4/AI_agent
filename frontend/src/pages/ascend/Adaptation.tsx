// 模型适配 — adapt-agent 10 步向导式 UI
import { useState, useEffect, useCallback } from 'react';
import { PageHeader, Card, Button, Input, Loading, Badge, Textarea, ErrorBanner } from '../../components/ui';
import { adaptationApi } from '../../api';

// ===== 步骤定义 =====
const STEPS = [
  { key: '1', name: '收集上下文', icon: 'fa-clipboard-list' },
  { key: '2', name: '分析模型', icon: 'fa-microscope' },
  { key: '3', name: '算子兼容性门控', icon: 'fa-shield-alt' },
  { key: '4', name: '框架侧代码分析', icon: 'fa-code-branch' },
  { key: '5', name: '选择适配策略', icon: 'fa-route' },
  { key: '6', name: '实现最小代码改动', icon: 'fa-code' },
  { key: '7', name: '两阶段验证', icon: 'fa-vial' },
  { key: '8', name: '验证推理和功能', icon: 'fa-check-double' },
  { key: '9', name: '生成产物', icon: 'fa-box' },
  { key: '10', name: '交接产物', icon: 'fa-handshake' },
] as const;

type StepKey = (typeof STEPS)[number]['key'];
type StepStatus = 'completed' | 'running' | 'pending' | 'blocked';

interface StepResult {
  [key: string]: unknown;
}

export default function Adaptation() {
  // ===== 全局状态 =====
  const [_status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [quickRef, setQuickRef] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState('');

  // ===== 会话状态 =====
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<StepKey>('1');
  const [stepStatuses, setStepStatuses] = useState<Record<StepKey, StepStatus>>(() => {
    const m: Record<StepKey, StepStatus> = {} as Record<StepKey, StepStatus>;
    STEPS.forEach(s => { m[s.key] = 'pending'; });
    m['1'] = 'running';
    return m;
  });
  const [stepResults, setStepResults] = useState<Partial<Record<StepKey, StepResult>>>({});

  // ===== Step 1 表单 =====
  const [modelPath, setModelPath] = useState('');
  const [modelName, setModelName] = useState('');
  const [deliveryRepo, setDeliveryRepo] = useState('');
  const [features, setFeatures] = useState({
    ACLGraph: true,
    EP: false,
    FlashComm1: false,
    Multimodal: false,
    MTP: false,
  });

  // ===== Step 3 表单 =====
  const [modelCode, setModelCode] = useState('');

  // ===== Step 4 表单 =====
  const [vllmSourcePath, setVllmSourcePath] = useState('');

  // ===== Step 6 表单 =====
  const [implDetails, setImplDetails] = useState('');

  // ===== Step 7 表单 =====
  const [dummyConfig, setDummyConfig] = useState({ tp_size: '1', dtype: 'float16', max_model_len: '1024', port: '8000' });
  const [realConfig, setRealConfig] = useState({ tp_size: '1', dtype: 'float16', max_model_len: '2048', port: '8001' });

  // ===== Step 8 表单 =====
  const [verifyHost, setVerifyHost] = useState('localhost');
  const [verifyPort, setVerifyPort] = useState('8000');

  // ===== 加载初始数据 =====
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, q] = await Promise.all([
        adaptationApi.status().catch(() => null),
        adaptationApi.quickReference().catch(() => null),
      ]);
      setStatus(s);
      setQuickRef(q);

      // 恢复已有会话
      if (s && (s as Record<string, unknown>).session_id) {
        const sid = String((s as Record<string, unknown>).session_id);
        setSessionId(sid);
        const session = await adaptationApi.getSession(sid);
        if (session) {
          if (session.current_step) setCurrentStep(String(session.current_step) as StepKey);
          if (session.step_statuses) setStepStatuses(session.step_statuses as Record<StepKey, StepStatus>);
          if (session.step_results) setStepResults(session.step_results as Record<StepKey, StepResult>);
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // ===== 辅助函数 =====
  function advanceStep(completedKey: StepKey) {
    setStepStatuses(prev => ({ ...prev, [completedKey]: 'completed' }));
    const idx = STEPS.findIndex(s => s.key === completedKey);
    if (idx < STEPS.length - 1) {
      const nextKey = STEPS[idx + 1].key;
      setCurrentStep(nextKey);
      setStepStatuses(prev => ({ ...prev, [nextKey]: prev[nextKey] === 'completed' ? 'completed' : 'running' }));
    }
  }

  function setStepResult(key: StepKey, result: StepResult) {
    setStepResults(prev => ({ ...prev, [key]: result }));
  }

  async function callApi(action: string, fn: () => Promise<unknown>) {
    setActionLoading(action);
    setError('');
    try {
      const res = await fn();
      return res as Record<string, unknown>;
    } catch (e) {
      setError(e instanceof Error ? e.message : '操作失败');
      return null;
    } finally {
      setActionLoading('');
    }
  }

  // ===== 步骤状态图标 =====
  function statusIcon(s: StepStatus) {
    switch (s) {
      case 'completed': return <span className="text-jade">✅</span>;
      case 'running': return <span className="text-copper animate-pulse">🔄</span>;
      case 'blocked': return <span className="text-vermillion">❌</span>;
      default: return <span className="text-ink-bg/50">⏳</span>;
    }
  }

  // ===== Step 1: 创建会话 =====
  async function handleCreateSession() {
    if (!modelPath.trim() || !modelName.trim()) {
      setError('模型路径和模型名称不能为空');
      return;
    }
    const res = await callApi('create', () =>
      adaptationApi.createSession({
        model_path: modelPath.trim(),
        model_name: modelName.trim(),
        delivery_repo: deliveryRepo.trim(),
        features: Object.entries(features).filter(([, v]) => v).map(([k]) => k),
      })
    );
    if (res?.session_id) {
      setSessionId(String(res.session_id));
      setStepResult('1', res);
      advanceStep('1');
    } else if (res) {
      setError('创建会话失败：未返回 session_id');
    }
  }

  // ===== Step 2: 分析模型 =====
  async function handleStep2() {
    if (!sessionId) return;
    const res = await callApi('step2', () => adaptationApi.step2(sessionId, {}));
    if (res) {
      setStepResult('2', res);
      advanceStep('2');
    }
  }

  // ===== Step 3: 算子兼容性 =====
  async function handleStep3() {
    if (!sessionId) return;
    const res = await callApi('step3', () => adaptationApi.step3(sessionId, { model_code: modelCode }));
    if (res) {
      setStepResult('3', res);
      if (res.blocked) {
        setStepStatuses(prev => ({ ...prev, '3': 'blocked' }));
      } else {
        advanceStep('3');
      }
    }
  }

  // ===== Step 4: 框架侧代码分析 =====
  async function handleStep4() {
    if (!sessionId) return;
    const res = await callApi('step4', () => adaptationApi.step4(sessionId, { vllm_source_path: vllmSourcePath }));
    if (res) {
      setStepResult('4', res);
      advanceStep('4');
    }
  }

  // ===== Step 5: 选择适配策略 =====
  async function handleStep5() {
    if (!sessionId) return;
    const res = await callApi('step5', () => adaptationApi.step5(sessionId));
    if (res) {
      setStepResult('5', res);
      if (res.strategy === 'blocked') {
        setStepStatuses(prev => ({ ...prev, '5': 'blocked' }));
      } else {
        advanceStep('5');
      }
    }
  }

  // ===== Step 6: 实现代码改动 =====
  async function handleStep6() {
    if (!sessionId) return;
    const res = await callApi('step6', () => adaptationApi.step6(sessionId, { implementation_details: implDetails }));
    if (res) {
      setStepResult('6', res);
      advanceStep('6');
    }
  }

  // ===== Step 7: 两阶段验证 =====
  async function handleStep7Dummy() {
    if (!sessionId) return;
    const res = await callApi('step7-dummy', () => adaptationApi.step7Dummy(sessionId, dummyConfig));
    if (res) setStepResult('7', { ...stepResults['7'], dummy: res });
  }

  async function handleStep7Real() {
    if (!sessionId) return;
    const res = await callApi('step7-real', () => adaptationApi.step7Real(sessionId, realConfig));
    if (res) {
      setStepResult('7', { ...stepResults['7'], real: res });
      advanceStep('7');
    }
  }

  // ===== Step 8: 验证推理和功能 =====
  async function handleStep8() {
    if (!sessionId) return;
    const res = await callApi('step8', () => adaptationApi.step8(sessionId, { host: verifyHost, port: verifyPort }));
    if (res) {
      setStepResult('8', res);
      advanceStep('8');
    }
  }

  // ===== Step 9: 生成产物 =====
  async function handleStep9() {
    if (!sessionId) return;
    const res = await callApi('step9', () => adaptationApi.step9(sessionId));
    if (res) {
      setStepResult('9', res);
      advanceStep('9');
    }
  }

  // ===== Step 10: 交接产物 =====
  async function handleStep10() {
    if (!sessionId) return;
    const res = await callApi('step10', () => adaptationApi.step10(sessionId));
    if (res) {
      setStepResult('10', res);
      advanceStep('10');
    }
  }

  // ===== 渲染步骤内容 =====
  function renderStepContent() {
    switch (currentStep) {
      // ===== Step 1 =====
      case '1':
        return (
          <Card className="p-4">
            <h3 className="mb-4 text-sm font-medium text-ink-bg/80">Step 1 · 收集上下文</h3>
            <div className="space-y-3">
              <Input label="模型路径" placeholder="/data/models/Qwen3.5-27B" value={modelPath} onChange={e => setModelPath(e.target.value)} icon="fa-folder-open" />
              <Input label="模型名称" placeholder="Qwen3.5-27B" value={modelName} onChange={e => setModelName(e.target.value)} icon="fa-cube" />
              <Input label="交付仓库" placeholder="https://github.com/org/model-ascend" value={deliveryRepo} onChange={e => setDeliveryRepo(e.target.value)} icon="fa-code-branch" />
              <div>
                <span className="mb-2 block text-xs font-medium text-ink-bg/60">功能集</span>
                <div className="flex flex-wrap gap-3">
                  {Object.entries(features).map(([key, checked]) => (
                    <label key={key} className="flex cursor-pointer items-center gap-1.5 text-xs text-ink-bg/70">
                      <input type="checkbox" checked={checked} onChange={e => setFeatures(prev => ({ ...prev, [key]: e.target.checked }))} className="accent-copper" />
                      {key}
                    </label>
                  ))}
                </div>
              </div>
              <Button onClick={handleCreateSession} loading={actionLoading === 'create'} disabled={!modelPath || !modelName}>
                <i className="fas fa-plus mr-1.5" />
                创建会话
              </Button>
            </div>
          </Card>
        );

      // ===== Step 2 =====
      case '2':
        return (
          <Card className="p-4">
            <h3 className="mb-4 text-sm font-medium text-ink-bg/80">Step 2 · 分析模型</h3>
            <Button onClick={handleStep2} loading={actionLoading === 'step2'} disabled={!sessionId}>
              <i className="fas fa-microscope mr-1.5" />
              开始分析
            </Button>
            {stepResults['2'] && (
              <div className="mt-4 space-y-3">
                <div className="flex flex-wrap gap-2">
                  {(stepResults['2'].categories as string[] || []).map((cat, i) => (
                    <Badge key={i} variant="copper">{cat}</Badge>
                  ))}
                </div>
                <div className="grid gap-2 text-xs">
                  {stepResults['2'].architecture != null && (
                    <div className="flex items-center gap-2">
                      <span className="text-ink-bg/50">架构类型:</span>
                      <Badge variant="jade">{String(stepResults['2'].architecture)}</Badge>
                    </div>
                  )}
                  {stepResults['2'].attention_variant != null && (
                    <div className="flex items-center gap-2">
                      <span className="text-ink-bg/50">注意力变体:</span>
                      <Badge>{String(stepResults['2'].attention_variant)}</Badge>
                    </div>
                  )}
                  {stepResults['2'].quant_type != null && (
                    <div className="flex items-center gap-2">
                      <span className="text-ink-bg/50">量化类型:</span>
                      <Badge variant="indigo">{String(stepResults['2'].quant_type)}</Badge>
                    </div>
                  )}
                  {stepResults['2'].state_dict_key_prefix != null && (
                    <div className="flex items-center gap-2">
                      <span className="text-ink-bg/50">state-dict key prefix:</span>
                      <code className="rounded bg-ink px-1.5 py-0.5 text-copper-light">{String(stepResults['2'].state_dict_key_prefix)}</code>
                    </div>
                  )}
                </div>
              </div>
            )}
          </Card>
        );

      // ===== Step 3 =====
      case '3':
        return (
          <Card className="p-4">
            <h3 className="mb-4 text-sm font-medium text-ink-bg/80">Step 3 · 算子兼容性门控</h3>
            <div className="space-y-3">
              <Textarea
                label="模型代码"
                placeholder="粘贴模型源码（含 import 和自定义算子）..."
                rows={8}
                value={modelCode}
                onChange={e => setModelCode(e.target.value)}
              />
              <Button onClick={handleStep3} loading={actionLoading === 'step3'} disabled={!sessionId || !modelCode}>
                <i className="fas fa-shield-alt mr-1.5" />
                扫描算子
              </Button>
            </div>
            {stepResults['3'] && (
              <div className="mt-4 space-y-3">
                {/* 按分类展示算子 */}
                {stepResults['3'].torch_ops != null && (
                  <div className="flex items-center gap-2 text-xs">
                    <Badge variant="jade">Torch ✅</Badge>
                    <span className="text-ink-bg/60">{String(stepResults['3'].torch_ops)}</span>
                  </div>
                )}
                {stepResults['3'].triton_ops != null && (
                  <div className="flex items-center gap-2 text-xs">
                    <Badge variant="copper">Triton ⚠️</Badge>
                    <span className="text-ink-bg/60">{String(stepResults['3'].triton_ops)}</span>
                  </div>
                )}
                {stepResults['3'].cuda_with_fallback != null && (
                  <div className="flex items-center gap-2 text-xs">
                    <Badge variant="vermillion">CUDA with fallback ❌</Badge>
                    <span className="text-ink-bg/60">{String(stepResults['3'].cuda_with_fallback)}</span>
                  </div>
                )}
                {stepResults['3'].cuda_without_fallback != null && (
                  <div className="flex items-center gap-2 text-xs">
                    <Badge variant="vermillion">CUDA without fallback ❌ BLOCKED</Badge>
                    <span className="text-ink-bg/60">{String(stepResults['3'].cuda_without_fallback)}</span>
                  </div>
                )}
                {stepResults['3'].blocked != null && stepResults['3'].blocked && (
                  <div className="flex items-center gap-2 rounded-lg border border-vermillion/30 bg-vermillion/10 px-4 py-2.5 text-sm text-vermillion">
                    <i className="fas fa-exclamation-triangle" />
                    <span>存在无 fallback 的 CUDA 算子，需提交 GitHub Issue 请求支持</span>
                  </div>
                )}
              </div>
            )}
          </Card>
        );

      // ===== Step 4 =====
      case '4':
        return (
          <Card className="p-4">
            <h3 className="mb-4 text-sm font-medium text-ink-bg/80">Step 4 · 框架侧代码分析</h3>
            <div className="space-y-3">
              <Input label="vLLM 源码路径" placeholder="/path/to/vllm" value={vllmSourcePath} onChange={e => setVllmSourcePath(e.target.value)} icon="fa-folder-open" />
              <Button onClick={handleStep4} loading={actionLoading === 'step4'} disabled={!sessionId || !vllmSourcePath}>
                <i className="fas fa-code-branch mr-1.5" />
                分析框架
              </Button>
            </div>
            {stepResults['4'] && (
              <div className="mt-4 space-y-2 text-xs">
                <div className="flex items-center gap-2">
                  <span className="text-ink-bg/50">架构在 registry.py:</span>
                  {stepResults['4'].in_registry ? (
                    <Badge variant="jade">已注册</Badge>
                  ) : (
                    <Badge variant="vermillion">未注册</Badge>
                  )}
                </div>
                {stepResults['4'].vllm_ascend_patch_status != null && (
                  <div className="flex items-center gap-2">
                    <span className="text-ink-bg/50">vllm-ascend 补丁状态:</span>
                    <Badge variant="copper">{String(stepResults['4'].vllm_ascend_patch_status)}</Badge>
                  </div>
                )}
              </div>
            )}
          </Card>
        );

      // ===== Step 5 =====
      case '5':
        return (
          <Card className="p-4">
            <h3 className="mb-4 text-sm font-medium text-ink-bg/80">Step 5 · 选择适配策略</h3>
            <Button onClick={handleStep5} loading={actionLoading === 'step5'} disabled={!sessionId}>
              <i className="fas fa-route mr-1.5" />
              自动选择策略
            </Button>
            {stepResults['5'] && (
              <div className="mt-4 space-y-2 text-xs">
                <div className="flex items-center gap-2">
                  <span className="text-ink-bg/50">策略类型:</span>
                  <Badge variant={stepResults['5'].strategy === 'blocked' ? 'vermillion' : 'jade'}>
                    {String(stepResults['5'].strategy ?? '')}
                  </Badge>
                </div>
                {stepResults['5'].description != null && (
                  <p className="text-ink-bg/60">{String(stepResults['5'].description)}</p>
                )}
              </div>
            )}
          </Card>
        );

      // ===== Step 6 =====
      case '6':
        return (
          <Card className="p-4">
            <h3 className="mb-4 text-sm font-medium text-ink-bg/80">Step 6 · 实现最小代码改动</h3>
            <div className="space-y-3">
              <Textarea
                label="实现细节"
                placeholder="描述需要实现的改动..."
                rows={6}
                value={implDetails}
                onChange={e => setImplDetails(e.target.value)}
              />
              <Button onClick={handleStep6} loading={actionLoading === 'step6'} disabled={!sessionId || !implDetails}>
                <i className="fas fa-code mr-1.5" />
                生成代码
              </Button>
            </div>
            {stepResults['6']?.generated_code != null && (
              <div className="mt-4">
                <span className="mb-2 block text-xs font-medium text-ink-bg/60">生成代码</span>
                <pre className="bg-ink p-3 rounded text-sm overflow-auto max-h-96 text-ink-bg/80">
                  {String(stepResults['6'].generated_code)}
                </pre>
              </div>
            )}
          </Card>
        );

      // ===== Step 7 =====
      case '7':
        return (
          <Card className="p-4">
            <h3 className="mb-4 text-sm font-medium text-ink-bg/80">Step 7 · 两阶段验证</h3>
            <div className="grid gap-4 lg:grid-cols-2">
              {/* Dummy Fast Gate */}
              <Card className="p-4">
                <h4 className="mb-3 text-xs font-medium text-copper-light">Dummy Fast Gate</h4>
                <div className="space-y-2">
                  <div className="grid grid-cols-2 gap-2">
                    <Input label="TP size" type="number" value={dummyConfig.tp_size} onChange={e => setDummyConfig(prev => ({ ...prev, tp_size: e.target.value }))} />
                    <Input label="dtype" value={dummyConfig.dtype} onChange={e => setDummyConfig(prev => ({ ...prev, dtype: e.target.value }))} />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <Input label="max_model_len" type="number" value={dummyConfig.max_model_len} onChange={e => setDummyConfig(prev => ({ ...prev, max_model_len: e.target.value }))} />
                    <Input label="port" type="number" value={dummyConfig.port} onChange={e => setDummyConfig(prev => ({ ...prev, port: e.target.value }))} />
                  </div>
                  <Button variant="secondary" size="sm" onClick={handleStep7Dummy} loading={actionLoading === 'step7-dummy'} disabled={!sessionId}>
                    生成验证命令
                  </Button>
                  {Boolean(stepResults['7']?.dummy) && (stepResults['7']?.dummy as Record<string, unknown>)?.command != null && (
                    <pre className="bg-ink p-2 rounded text-xs overflow-auto max-h-48 text-ink-bg/80">
                      {String((stepResults['7']?.dummy as Record<string, unknown>)?.command)}
                    </pre>
                  )}
                </div>
              </Card>

              {/* Real-Weight Mandatory Gate */}
              <Card className="p-4">
                <h4 className="mb-3 text-xs font-medium text-copper-light">Real-Weight Mandatory Gate</h4>
                <div className="space-y-2">
                  <div className="grid grid-cols-2 gap-2">
                    <Input label="TP size" type="number" value={realConfig.tp_size} onChange={e => setRealConfig(prev => ({ ...prev, tp_size: e.target.value }))} />
                    <Input label="dtype" value={realConfig.dtype} onChange={e => setRealConfig(prev => ({ ...prev, dtype: e.target.value }))} />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <Input label="max_model_len" type="number" value={realConfig.max_model_len} onChange={e => setRealConfig(prev => ({ ...prev, max_model_len: e.target.value }))} />
                    <Input label="port" type="number" value={realConfig.port} onChange={e => setRealConfig(prev => ({ ...prev, port: e.target.value }))} />
                  </div>
                  <Button variant="secondary" size="sm" onClick={handleStep7Real} loading={actionLoading === 'step7-real'} disabled={!sessionId}>
                    生成验证命令
                  </Button>
                  {Boolean(stepResults['7']?.real) && (stepResults['7']?.real as Record<string, unknown>)?.command != null && (
                    <pre className="bg-ink p-2 rounded text-xs overflow-auto max-h-48 text-ink-bg/80">
                      {String((stepResults['7']?.real as Record<string, unknown>)?.command)}
                    </pre>
                  )}
                </div>
              </Card>
            </div>
          </Card>
        );

      // ===== Step 8 =====
      case '8':
        return (
          <Card className="p-4">
            <h3 className="mb-4 text-sm font-medium text-ink-bg/80">Step 8 · 验证推理和功能</h3>
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <Input label="Host" value={verifyHost} onChange={e => setVerifyHost(e.target.value)} icon="fa-server" />
                <Input label="Port" type="number" value={verifyPort} onChange={e => setVerifyPort(e.target.value)} icon="fa-hashtag" />
              </div>
              <Button onClick={handleStep8} loading={actionLoading === 'step8'} disabled={!sessionId}>
                <i className="fas fa-check-double mr-1.5" />
                生成测试命令
              </Button>
            </div>
            {stepResults['8'] && (
              <div className="mt-4 space-y-3">
                {stepResults['8'].curl_command != null && (
                  <div>
                    <span className="mb-1 block text-xs font-medium text-ink-bg/60">curl 测试命令</span>
                    <pre className="bg-ink p-3 rounded text-sm overflow-auto max-h-48 text-ink-bg/80">
                      {String(stepResults['8'].curl_command)}
                    </pre>
                  </div>
                )}
                {stepResults['8'].feature_matrix != null && (
                  <div>
                    <span className="mb-1 block text-xs font-medium text-ink-bg/60">功能状态矩阵</span>
                    <pre className="bg-ink p-3 rounded text-sm overflow-auto max-h-48 text-ink-bg/80">
                      {typeof stepResults['8'].feature_matrix === 'string'
                        ? stepResults['8'].feature_matrix
                        : JSON.stringify(stepResults['8'].feature_matrix, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </Card>
        );

      // ===== Step 9 =====
      case '9':
        return (
          <Card className="p-4">
            <h3 className="mb-4 text-sm font-medium text-ink-bg/80">Step 9 · 生成产物</h3>
            <Button onClick={handleStep9} loading={actionLoading === 'step9'} disabled={!sessionId}>
              <i className="fas fa-box mr-1.5" />
              生成产物
            </Button>
            {stepResults['9'] && (
              <div className="mt-4 space-y-2 text-xs">
                {stepResults['9'].yaml_path != null && (
                  <div className="flex items-center gap-2">
                    <span className="text-ink-bg/50">YAML 配置:</span>
                    <code className="rounded bg-ink px-1.5 py-0.5 text-copper-light">{String(stepResults['9'].yaml_path)}</code>
                  </div>
                )}
                {stepResults['9'].doc_path != null && (
                  <div className="flex items-center gap-2">
                    <span className="text-ink-bg/50">文档路径:</span>
                    <code className="rounded bg-ink px-1.5 py-0.5 text-copper-light">{String(stepResults['9'].doc_path)}</code>
                  </div>
                )}
                {stepResults['9'].commit_command != null && (
                  <div>
                    <span className="mb-1 block text-ink-bg/50">提交命令:</span>
                    <pre className="bg-ink p-2 rounded text-ink-bg/80">{String(stepResults['9'].commit_command)}</pre>
                  </div>
                )}
              </div>
            )}
          </Card>
        );

      // ===== Step 10 =====
      case '10':
        return (
          <Card className="p-4">
            <h3 className="mb-4 text-sm font-medium text-ink-bg/80">Step 10 · 交接产物</h3>
            <Button onClick={handleStep10} loading={actionLoading === 'step10'} disabled={!sessionId}>
              <i className="fas fa-handshake mr-1.5" />
              生成交接报告
            </Button>
            {stepResults['10'] && (
              <div className="mt-4 space-y-3">
                {stepResults['10'].analysis_report != null && (
                  <div>
                    <span className="mb-1 block text-xs font-medium text-ink-bg/60">完整分析报告</span>
                    <pre className="bg-ink p-3 rounded text-sm overflow-auto max-h-96 text-ink-bg/80">
                      {typeof stepResults['10'].analysis_report === 'string'
                        ? stepResults['10'].analysis_report
                        : JSON.stringify(stepResults['10'].analysis_report, null, 2)}
                    </pre>
                  </div>
                )}
                {stepResults['10'].runbook != null && (
                  <div>
                    <span className="mb-1 block text-xs font-medium text-ink-bg/60">Runbook</span>
                    <pre className="bg-ink p-3 rounded text-sm overflow-auto max-h-96 text-ink-bg/80">
                      {typeof stepResults['10'].runbook === 'string'
                        ? stepResults['10'].runbook
                        : JSON.stringify(stepResults['10'].runbook, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </Card>
        );

      default:
        return null;
    }
  }

  // ===== 主渲染 =====
  if (loading) return <Loading text="加载适配状态" />;

  return (
    <div>
      <PageHeader
        title="模型适配"
        subtitle="adapt-agent — 将模型适配到昇腾 NPU 运行"
        icon="fa-puzzle-piece"
        action={
          <Button variant="secondary" size="sm" onClick={load}>
            <i className="fas fa-redo mr-1.5" />
            刷新
          </Button>
        }
      />

      {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

      <div className="flex gap-6">
        {/* 左侧步骤进度条 */}
        <div className="w-64 shrink-0">
          <Card className="p-4">
            <h3 className="mb-3 text-xs font-medium text-ink-bg/60">适配步骤</h3>
            <div className="relative">
              {/* 竖线 */}
              <div className="absolute left-[11px] top-2 bottom-2 w-px bg-copper/20" />
              <div className="space-y-1">
                {STEPS.map((step) => {
                  const s = stepStatuses[step.key];
                  const isActive = currentStep === step.key;
                  const isCompleted = s === 'completed';
                  return (
                    <button
                      key={step.key}
                      onClick={() => { if (isCompleted || isActive) setCurrentStep(step.key); }}
                      disabled={!isCompleted && !isActive}
                      className={`relative flex w-full cursor-pointer items-center gap-2.5 rounded-lg px-2 py-2 text-left transition-all duration-200 ${
                        isActive
                          ? 'bg-copper/10 text-copper-light'
                          : isCompleted
                            ? 'text-ink-bg/70 hover:bg-ink-dark/40'
                            : 'text-ink-bg/50 cursor-not-allowed'
                      }`}
                    >
                      {/* 步骤号圆点 */}
                      <span className={`relative z-10 flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${
                        isActive
                          ? 'bg-copper text-ink-bg'
                          : isCompleted
                            ? 'bg-jade/20 text-jade'
                            : 'bg-ink-bg/10 text-ink-bg/50'
                      }`}>
                        {step.key}
                      </span>
                      <div className="flex min-w-0 flex-1 items-center gap-1.5">
                        <span className="truncate text-xs">{step.name}</span>
                        {statusIcon(s)}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </Card>
        </div>

        {/* 右侧当前步骤内容 */}
        <div className="flex-1 min-w-0">
          {renderStepContent()}
        </div>
      </div>

      {/* 底部快速参考 */}
      {quickRef && (
        <Card className="mt-6 p-4">
          <h3 className="mb-3 text-xs font-medium text-ink-bg/60">快速参考</h3>
          <pre className="bg-ink p-3 rounded text-sm overflow-auto max-h-64 text-ink-bg/70">
            {typeof quickRef === 'string' ? quickRef : JSON.stringify(quickRef, null, 2)}
          </pre>
        </Card>
      )}
    </div>
  );
}

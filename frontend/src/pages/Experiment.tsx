// 实验设计页 — 方案设计 + 功效分析
import { useState, type FormEvent } from 'react';
import { PageHeader, Button, Card, Textarea, Input, Loading, EmptyState, ErrorBanner } from '../components/ui';
import { experimentApi } from '../api';
import type { DesignResponse, PowerAnalysisResponse } from '../types';

type DesignType = 'between' | 'within' | 'mixed' | 'factorial' | 'repeated';

export default function Experiment() {
  const [tab, setTab] = useState<'design' | 'power'>('design');

  // 设计表单
  const [goal, setGoal] = useState('');
  const [variables, setVariables] = useState('');
  const [designType, setDesignType] = useState<DesignType>('between');
  const [designLoading, setDesignLoading] = useState(false);
  const [designError, setDesignError] = useState('');
  const [designResult, setDesignResult] = useState<DesignResponse | null>(null);

  // 功效分析表单
  const [effectSize, setEffectSize] = useState('0.5');
  const [alpha, setAlpha] = useState('0.05');
  const [power, setPower] = useState('0.8');
  const [powerLoading, setPowerLoading] = useState(false);
  const [powerError, setPowerError] = useState('');
  const [powerResult, setPowerResult] = useState<PowerAnalysisResponse | null>(null);

  async function handleDesign(e: FormEvent) {
    e.preventDefault();
    if (!goal.trim()) return;
    setDesignLoading(true);
    setDesignError('');
    setDesignResult(null);
    try {
      const vars = variables.split(/[,\n，]/).map(v => v.trim()).filter(Boolean);
      const res = await experimentApi.design({
        research_goal: goal.trim(),
        variables: vars,
        design_type: designType,
      });
      setDesignResult(res);
    } catch (err) {
      setDesignError(err instanceof Error ? err.message : '设计失败');
    } finally {
      setDesignLoading(false);
    }
  }

  async function handlePower(e: FormEvent) {
    e.preventDefault();
    setPowerLoading(true);
    setPowerError('');
    setPowerResult(null);
    try {
      const res = await experimentApi.powerAnalysis({
        effect_size: parseFloat(effectSize),
        alpha: parseFloat(alpha),
        power: parseFloat(power),
      });
      setPowerResult(res);
    } catch (err) {
      setPowerError(err instanceof Error ? err.message : '分析失败');
    } finally {
      setPowerLoading(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="实验设计"
        subtitle="方案设计 · 功效分析 · 样本量估算"
        icon="fa-flask"
      />

      {/* Tab 切换 */}
      <div className="mb-6 flex gap-1 border-b border-copper/10">
        {([
          { key: 'design', label: '方案设计', icon: 'fa-drafting-compass' },
          { key: 'power', label: '功效分析', icon: 'fa-calculator' },
        ] as const).map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`cursor-pointer border-b-2 px-4 py-2.5 text-sm transition-colors ${
              tab === t.key
                ? 'border-copper text-copper-light'
                : 'border-transparent text-ink-bg/50 hover:text-ink-bg'
            }`}
          >
            <i className={`fas ${t.icon} mr-1.5`} />
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'design' && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* 输入 */}
          <Card>
            <form onSubmit={handleDesign} className="space-y-4">
              <Textarea
                label="研究目标"
                rows={3}
                placeholder="如：比较三种药物对血压的降压效果"
                value={goal}
                onChange={e => setGoal(e.target.value)}
              />
              <Input
                label="变量（逗号或换行分隔）"
                placeholder="药物剂量, 血压, 心率"
                value={variables}
                onChange={e => setVariables(e.target.value)}
              />
              <div>
                <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">实验设计类型</span>
                <div className="flex flex-wrap gap-2">
                  {([
                    { v: 'between', label: '被试间' },
                    { v: 'within', label: '被试内' },
                    { v: 'mixed', label: '混合' },
                    { v: 'factorial', label: '析因' },
                    { v: 'repeated', label: '重复测量' },
                  ] as const).map(t => (
                    <button
                      key={t.v}
                      type="button"
                      onClick={() => setDesignType(t.v)}
                      className={`cursor-pointer rounded-lg border px-3 py-1.5 text-xs transition-colors ${
                        designType === t.v
                          ? 'border-copper bg-copper text-ink-bg'
                          : 'border-copper/20 text-ink-bg/50 hover:border-copper/40'
                      }`}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
              </div>
              <Button type="submit" loading={designLoading}>
                <i className="fas fa-magic mr-1.5" />
                生成方案
              </Button>
            </form>
          </Card>

          {/* 结果 */}
          <Card>
            {designError && <div className="mb-3"><ErrorBanner message={designError} /></div>}
            {designLoading ? (
              <Loading text="正在设计方案" />
            ) : designResult ? (
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <span className="rounded bg-copper/10 px-2 py-0.5 text-xs text-copper-light">
                    {designType}
                  </span>
                  <span className="text-xs text-ink-bg/60">实验方案已生成</span>
                </div>
                {designResult.optimized_plan && (
                  <div>
                    <h4 className="mb-2 text-xs font-medium text-ink-bg/60">优化方案</h4>
                    <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                      {designResult.optimized_plan}
                    </pre>
                  </div>
                )}
                {designResult.plan && Object.keys(designResult.plan).length > 0 && (
                  <div>
                    <h4 className="mb-2 text-xs font-medium text-ink-bg/60">方案详情</h4>
                    <pre className="max-h-64 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                      {JSON.stringify(designResult.plan, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            ) : (
              <EmptyState icon="fa-drafting-compass" title="填写研究目标生成方案" />
            )}
          </Card>
        </div>
      )}

      {tab === 'power' && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* 输入 */}
          <Card>
            <form onSubmit={handlePower} className="space-y-4">
              <Input
                label="效应量 (effect_size, 0.01-2.0)"
                type="number"
                step="0.01"
                min="0.01"
                max="2.0"
                value={effectSize}
                onChange={e => setEffectSize(e.target.value)}
              />
              <div className="grid grid-cols-2 gap-3">
                <Input
                  label="显著性水平 α"
                  type="number"
                  step="0.01"
                  min="0.001"
                  max="0.1"
                  value={alpha}
                  onChange={e => setAlpha(e.target.value)}
                />
                <Input
                  label="统计功效 power"
                  type="number"
                  step="0.01"
                  min="0.5"
                  max="0.99"
                  value={power}
                  onChange={e => setPower(e.target.value)}
                />
              </div>
              <div className="rounded-lg bg-copper/5 p-3 text-xs text-ink-bg/50">
                <p className="mb-1 font-medium text-copper-light">参数说明</p>
                <p>• 效应量 0.2=小, 0.5=中, 0.8=大</p>
                <p>• α 通常取 0.05，power 通常取 0.8</p>
                <p>• 系统将计算所需的最小样本量</p>
              </div>
              <Button type="submit" loading={powerLoading}>
                <i className="fas fa-calculator mr-1.5" />
                计算样本量
              </Button>
            </form>
          </Card>

          {/* 结果 */}
          <Card>
            {powerError && <div className="mb-3"><ErrorBanner message={powerError} /></div>}
            {powerLoading ? (
              <Loading text="正在计算" />
            ) : powerResult ? (
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <i className="fas fa-check-circle text-jade" />
                  <span className="text-sm text-ink-bg">分析完成</span>
                </div>
                <pre className="max-h-96 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                  {JSON.stringify(powerResult.result, null, 2)}
                </pre>
              </div>
            ) : (
              <EmptyState icon="fa-calculator" title="设置参数计算样本量" />
            )}
          </Card>
        </div>
      )}
    </div>
  );
}

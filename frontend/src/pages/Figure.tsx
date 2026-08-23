// 图表合同页 — Figure Contract + 样式 + QA
import { useState, type FormEvent } from 'react';
import { PageHeader, Button, Card, Textarea, Loading, EmptyState, ErrorBanner } from '../components/ui';
import { figureApi } from '../api';

type TabKey = 'contract' | 'style' | 'qa';

const ARCHETYPES = [
  { value: 'comparison', label: '对比', icon: 'fa-scale-balanced' },
  { value: 'distribution', label: '分布', icon: 'fa-chart-bar' },
  { value: 'correlation', label: '相关', icon: 'fa-link' },
  { value: 'time_series', label: '时序', icon: 'fa-chart-line' },
  { value: 'composition', label: '构成', icon: 'fa-chart-pie' },
  { value: 'spatial', label: '空间', icon: 'fa-map' },
  { value: 'network', label: '网络', icon: 'fa-project-diagram' },
];

export default function FigurePage() {
  const [tab, setTab] = useState<TabKey>('contract');
  const [conclusion, setConclusion] = useState('');
  const [evidenceChain, setEvidenceChain] = useState('');
  const [archetype, setArchetype] = useState<string>('comparison');
  const [journal, setJournal] = useState<string>('generic');
  const [contractData, setContractData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleContract(e: FormEvent) {
    e.preventDefault();
    if (!conclusion.trim()) { setError('请输入图表核心结论'); return; }
    setLoading(true); setError(''); setContractData(null);
    try {
      const res = await figureApi.createContract({
        conclusion: conclusion.trim(),
        evidence_chain: evidenceChain.split('\n').map(l => l.trim()).filter(Boolean),
        archetype: archetype as 'comparison' | 'distribution' | 'correlation' | 'time_series' | 'composition' | 'spatial' | 'network',
        journal: journal as 'nature' | 'nat-comms' | 'generic',
      });
      setContractData(res as unknown as Record<string, unknown>);
    } catch (err) { setError(err instanceof Error ? err.message : '创建失败'); }
    finally { setLoading(false); }
  }

  async function handleStyle() {
    setLoading(true); setError('');
    try {
      const res = await figureApi.applyStyle(journal);
      setContractData(res as unknown as Record<string, unknown>);
    } catch (err) { setError(err instanceof Error ? err.message : '应用样式失败'); }
    finally { setLoading(false); }
  }

  async function handleQA() {
    if (!contractData) { setError('请先创建 Figure Contract'); return; }
    setLoading(true); setError('');
    try {
      const res = await figureApi.qaCheck({ contract: contractData });
      setContractData(res as unknown as Record<string, unknown>);
    } catch (err) { setError(err instanceof Error ? err.message : 'QA 检查失败'); }
    finally { setLoading(false); }
  }

  return (
    <div>
      <PageHeader title="图表合同" subtitle="Figure Contract · 样式 · QA" icon="fa-chart-column" />

      <div className="mb-6 flex gap-6 border-b border-copper/10">
        {([
          { key: 'contract' as TabKey, label: '创建合同', icon: 'fa-file-contract' },
          { key: 'style' as TabKey, label: '应用样式', icon: 'fa-palette' },
          { key: 'qa' as TabKey, label: 'QA 检查', icon: 'fa-clipboard-check' },
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

      {tab === 'contract' && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <form onSubmit={handleContract} className="space-y-4">
              <Textarea label="图表核心结论" placeholder="例如：新方法在准确率上优于 baseline 15%"
                value={conclusion} onChange={e => setConclusion(e.target.value)} rows={4} />
              <Textarea label="证据链（每行一条）" placeholder="实验1: 准确率对比&#10;实验2: 消融实验"
                value={evidenceChain} onChange={e => setEvidenceChain(e.target.value)} rows={3} />
              <div>
                <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">图原型</span>
                <div className="flex flex-wrap gap-2">
                  {ARCHETYPES.map(a => (
                    <button key={a.value} type="button" onClick={() => setArchetype(a.value)}
                      className={`flex items-center gap-1 rounded-lg border px-3 py-1.5 text-xs transition-colors ${
                        archetype === a.value ? 'border-copper bg-copper text-ink-bg' : 'border-copper/20 text-ink-bg/50 hover:border-copper/40'
                      }`}>
                      <i className={`fas ${a.icon}`} />{a.label}
                    </button>
                  ))}
                </div>
              </div>
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">期刊</span>
                <select value={journal} onChange={e => setJournal(e.target.value)}
                  className="cursor-pointer rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none focus:ring-1 focus:ring-copper/30">
                  <option value="generic" className="bg-ink-dark">通用</option>
                  <option value="nature" className="bg-ink-dark">Nature</option>
                  <option value="nat-comms" className="bg-ink-dark">Nature Communications</option>
                </select>
              </label>
              <Button type="submit" loading={loading}><i className="fas fa-file-contract mr-1.5" />创建合同</Button>
            </form>
          </Card>
          <Card>
            <h3 className="mb-3 text-sm font-medium text-ink-bg">合同结果</h3>
            {loading ? <Loading text="生成中" /> : contractData ? (
              <pre className="max-h-96 overflow-auto rounded-lg bg-ink-dark/60 p-3 text-xs text-ink-bg/70">{JSON.stringify(contractData, null, 2)}</pre>
            ) : <EmptyState icon="fa-chart-column" title="创建 Figure Contract" />}
          </Card>
        </div>
      )}

      {tab === 'style' && (
        <Card>
          <div className="space-y-4">
            <p className="text-sm text-ink-bg/60">应用 {journal} 期刊级 matplotlib 样式到当前图表。</p>
            <Button onClick={handleStyle} loading={loading}><i className="fas fa-palette mr-1.5" />应用样式</Button>
            {contractData && <pre className="max-h-60 overflow-auto rounded-lg bg-ink-dark/60 p-3 text-xs text-ink-bg/70">{JSON.stringify(contractData, null, 2)}</pre>}
          </div>
        </Card>
      )}

      {tab === 'qa' && (
        <Card>
          <div className="space-y-4">
            <p className="text-sm text-ink-bg/60">对当前 Figure Contract 进行质量检查。</p>
            <Button onClick={handleQA} loading={loading} disabled={!contractData}><i className="fas fa-clipboard-check mr-1.5" />QA 检查</Button>
            {contractData && <pre className="max-h-60 overflow-auto rounded-lg bg-ink-dark/60 p-3 text-xs text-ink-bg/70">{JSON.stringify(contractData, null, 2)}</pre>}
          </div>
        </Card>
      )}
    </div>
  );
}

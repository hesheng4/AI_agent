// 数据可用性页 — 声明生成 · FAIR审计 · 仓库推荐
import { useState, type FormEvent } from 'react';
import { PageHeader, Button, Card, Textarea, Loading, EmptyState, ErrorBanner } from '../components/ui';
import { dataAvailabilityApi } from '../api';
import type { GenerateStatementResult, AuditStatementResult, SelectRepositoryResult } from '../types';

type TabKey = 'generate' | 'audit' | 'repository';

export default function DataAvailability() {
  const [tab, setTab] = useState<TabKey>('generate');
  const [dataDesc, setDataDesc] = useState('');
  const [repoType, setRepoType] = useState('');
  const [restrictions, setRestrictions] = useState('');
  const [journal, setJournal] = useState('nature');
  const [genResult, setGenResult] = useState<GenerateStatementResult | null>(null);
  const [statement, setStatement] = useState('');
  const [auditResult, setAuditResult] = useState<AuditStatementResult | null>(null);
  const [dataType, setDataType] = useState('');
  const [dataSize, setDataSize] = useState('');
  const [accessControl, setAccessControl] = useState('open');
  const [repoResult, setRepoResult] = useState<SelectRepositoryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleGenerate(e: FormEvent) {
    e.preventDefault();
    if (!dataDesc.trim()) { setError('请输入数据描述'); return; }
    setLoading(true); setError(''); setGenResult(null);
    try {
      const res = await dataAvailabilityApi.generateStatement({
        data_description: dataDesc.trim(),
        repository_type: repoType.trim() || undefined,
        restrictions: restrictions.trim() || undefined,
        journal,
      });
      setGenResult(res);
    } catch (err) { setError(err instanceof Error ? err.message : '生成失败'); }
    finally { setLoading(false); }
  }

  async function handleAudit(e: FormEvent) {
    e.preventDefault();
    if (!statement.trim()) { setError('请输入数据可用性声明'); return; }
    setLoading(true); setError(''); setAuditResult(null);
    try {
      const res = await dataAvailabilityApi.auditStatement({ statement: statement.trim() });
      setAuditResult(res);
    } catch (err) { setError(err instanceof Error ? err.message : '审计失败'); }
    finally { setLoading(false); }
  }

  async function handleRepository(e: FormEvent) {
    e.preventDefault();
    if (!dataType.trim()) { setError('请输入数据类型'); return; }
    setLoading(true); setError(''); setRepoResult(null);
    try {
      const res = await dataAvailabilityApi.selectRepository({
        data_type: dataType.trim(),
        data_size: dataSize.trim() || undefined,
        access_control: accessControl as 'open' | 'restricted',
      });
      setRepoResult(res);
    } catch (err) { setError(err instanceof Error ? err.message : '推荐失败'); }
    finally { setLoading(false); }
  }

  return (
    <div>
      <PageHeader title="数据可用性" subtitle="声明生成 · FAIR审计 · 仓库推荐" icon="fa-database" />

      <div className="mb-6 flex gap-6 border-b border-copper/10">
        {([
          { key: 'generate' as TabKey, label: '生成声明', icon: 'fa-file-alt' },
          { key: 'audit' as TabKey, label: 'FAIR 审计', icon: 'fa-clipboard-check' },
          { key: 'repository' as TabKey, label: '仓库推荐', icon: 'fa-warehouse' },
        ]).map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`flex cursor-pointer items-center gap-2 px-1 pb-3 text-sm transition-colors ${
              tab === t.key ? 'border-b-2 border-copper text-copper-light' : 'border-b-2 border-transparent text-ink-bg/50 hover:text-ink-bg'
            }`}>
            <i className={`fas ${t.icon} text-xs`} />
            {t.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4">
          <ErrorBanner message={error} />
        </div>
      )}

      {tab === 'generate' && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <form onSubmit={handleGenerate} className="space-y-4">
              <Textarea label="数据描述" placeholder="描述你的研究数据，例如：包含 1000 张医学影像的 CSV 文件，含标签和元数据..."
                value={dataDesc} onChange={e => setDataDesc(e.target.value)} rows={5} />
              <div className="grid grid-cols-2 gap-3">
                <Textarea label="仓库类型（可选）" placeholder="如：Zenodo, Figshare, Dryad..."
                  value={repoType} onChange={e => setRepoType(e.target.value)} rows={2} />
                <Textarea label="访问限制（可选）" placeholder="如：仅限学术用途，需申请..."
                  value={restrictions} onChange={e => setRestrictions(e.target.value)} rows={2} />
              </div>
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">期刊格式</span>
                <select value={journal} onChange={e => setJournal(e.target.value)}
                  className="cursor-pointer rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none focus:ring-1 focus:ring-copper/30">
                  <option value="nature" className="bg-ink-dark">Nature</option>
                  <option value="nat-comms" className="bg-ink-dark">Nature Communications</option>
                  <option value="science" className="bg-ink-dark">Science</option>
                  <option value="general" className="bg-ink-dark">通用</option>
                </select>
              </label>
              <Button type="submit" loading={loading}>
                <i className="fas fa-file-alt mr-1.5" />生成声明
              </Button>
            </form>
          </Card>
          <Card>
            <h3 className="mb-3 text-sm font-medium text-ink-bg">生成结果</h3>
            {loading ? (
              <Loading text="生成数据可用性声明" />
            ) : genResult ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <span className="rounded bg-copper/10 px-2 py-1 text-xs text-copper-light">{genResult.journal}</span>
                  {genResult.has_restrictions && <span className="rounded bg-vermillion/10 px-2 py-1 text-xs text-vermillion">有限制</span>}
                </div>
                <div className="rounded-lg bg-ink-dark/60 p-4 text-sm text-ink-bg/80 whitespace-pre-wrap">{genResult.statement}</div>
              </div>
            ) : (
              <EmptyState icon="fa-database" title="生成数据可用性声明" />
            )}
          </Card>
        </div>
      )}

      {tab === 'audit' && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <form onSubmit={handleAudit} className="space-y-4">
              <Textarea label="数据可用性声明" placeholder="粘贴已有的数据可用性声明..."
                value={statement} onChange={e => setStatement(e.target.value)} rows={8} />
              <Button type="submit" loading={loading}>
                <i className="fas fa-clipboard-check mr-1.5" />审计 FAIR 合规
              </Button>
            </form>
          </Card>
          <Card>
            <h3 className="mb-3 text-sm font-medium text-ink-bg">审计结果</h3>
            {loading ? (
              <Loading text="审计 FAIR 合规性" />
            ) : auditResult ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <span className={`rounded px-2 py-1 text-xs ${
                    auditResult.fair_compliance === 'compliant' ? 'bg-jade/10 text-jade' :
                    auditResult.fair_compliance === 'partial' ? 'bg-copper/10 text-copper-light' :
                    'bg-vermillion/10 text-vermillion'
                  }`}>FAIR: {auditResult.fair_compliance}</span>
                </div>
                <div className="rounded-lg bg-ink-dark/60 p-4 text-sm text-ink-bg/80 whitespace-pre-wrap">{auditResult.audit_result}</div>
              </div>
            ) : (
              <EmptyState icon="fa-clipboard-check" title="审计声明的 FAIR 合规性" />
            )}
          </Card>
        </div>
      )}

      {tab === 'repository' && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <form onSubmit={handleRepository} className="space-y-4">
              <Textarea label="数据类型" placeholder="如：基因组数据、医学影像、数值模拟结果..."
                value={dataType} onChange={e => setDataType(e.target.value)} rows={3} />
              <div className="grid grid-cols-2 gap-3">
                <Textarea label="数据大小（可选）" placeholder="如：50GB, 1TB..."
                  value={dataSize} onChange={e => setDataSize(e.target.value)} rows={2} />
                <label className="block">
                  <span className="mb-1.5 block text-xs font-medium text-ink-bg/60">访问控制</span>
                  <select value={accessControl} onChange={e => setAccessControl(e.target.value)}
                    className="cursor-pointer rounded-lg border border-copper/20 bg-ink-dark/40 px-3 py-2 text-sm text-ink-bg focus:border-copper focus:outline-none focus:ring-1 focus:ring-copper/30">
                    <option value="open" className="bg-ink-dark">公开 (Open)</option>
                    <option value="restricted" className="bg-ink-dark">受限 (Restricted)</option>
                  </select>
                </label>
              </div>
              <Button type="submit" loading={loading}>
                <i className="fas fa-warehouse mr-1.5" />推荐仓库
              </Button>
            </form>
          </Card>
          <Card>
            <h3 className="mb-3 text-sm font-medium text-ink-bg">推荐结果</h3>
            {loading ? (
              <Loading text="推荐数据仓库" />
            ) : repoResult ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <span className="rounded bg-copper/10 px-2 py-1 text-xs text-copper-light">{repoResult.data_type}</span>
                  <span className="rounded bg-jade/10 px-2 py-1 text-xs text-jade">{repoResult.access_control}</span>
                </div>
                <div className="rounded-lg bg-ink-dark/60 p-4 text-sm text-ink-bg/80 whitespace-pre-wrap">{repoResult.recommendation}</div>
              </div>
            ) : (
              <EmptyState icon="fa-warehouse" title="推荐数据仓库" />
            )}
          </Card>
        </div>
      )}
    </div>
  );
}

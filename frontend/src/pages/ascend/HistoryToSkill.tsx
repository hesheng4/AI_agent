// 历史转技能 — 从调试历史生成可复用技能
import { useState, useEffect, useCallback } from 'react';
import { PageHeader, Button, Card, Input, Textarea, Loading, EmptyState, ErrorBanner } from '../../components/ui';
import { historyToSkillApi } from '../../api';

export default function HistoryToSkill() {
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [quickRef, setQuickRef] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // 模型变体查询
  const [modelName, setModelName] = useState('');
  const [variants, setVariants] = useState<Record<string, unknown> | null>(null);

  // 根节点查询
  const [sources, setSources] = useState('');
  const [roots, setRoots] = useState<Record<string, unknown> | null>(null);

  // 历史搜索
  const [searchQuery, setSearchQuery] = useState('');
  const [searchSources, setSearchSources] = useState('');
  const [searchLimit, setSearchLimit] = useState('20');
  const [searchResults, setSearchResults] = useState<Record<string, unknown> | null>(null);

  // 技能生成
  const [genTitle, setGenTitle] = useState('');
  const [genDescription, setGenDescription] = useState('');
  const [genHistoryIds, setGenHistoryIds] = useState('');
  const [genOutputDir, setGenOutputDir] = useState('');
  const [genResult, setGenResult] = useState<Record<string, unknown> | null>(null);

  // 端到端运行
  const [runQuery, setRunQuery] = useState('');
  const [runOutputDir, setRunOutputDir] = useState('');
  const [runResult, setRunResult] = useState<Record<string, unknown> | null>(null);

  // 验证
  const [validateDir, setValidateDir] = useState('');
  const [validateResult, setValidateResult] = useState<Record<string, unknown> | null>(null);

  const [actionLoading, setActionLoading] = useState('');
  const [actionMsg, setActionMsg] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, q] = await Promise.all([
        historyToSkillApi.status(),
        historyToSkillApi.quickReference().catch(() => null),
      ]);
      setStatus(s);
      setQuickRef(q);
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // 查询模型变体
  async function handleVariants() {
    if (!modelName.trim()) {
      setActionMsg('请输入模型名称');
      return;
    }
    setActionLoading('variants');
    setError('');
    try {
      const res = await historyToSkillApi.variants(modelName.trim());
      setVariants(res);
      setActionMsg('');
    } catch (e) {
      setError(e instanceof Error ? e.message : '查询变体失败');
    } finally {
      setActionLoading('');
    }
  }

  // 查询根节点
  async function handleRoots() {
    setActionLoading('roots');
    setError('');
    try {
      const res = await historyToSkillApi.roots(sources.trim() || undefined);
      setRoots(res);
      setActionMsg('');
    } catch (e) {
      setError(e instanceof Error ? e.message : '查询根节点失败');
    } finally {
      setActionLoading('');
    }
  }

  // 搜索历史
  async function handleSearch() {
    setActionLoading('search');
    setError('');
    try {
      const res = await historyToSkillApi.search({
        query: searchQuery,
        sources: searchSources || undefined,
        limit: parseInt(searchLimit) || 20,
      });
      setSearchResults(res);
      setActionMsg('');
    } catch (e) {
      setError(e instanceof Error ? e.message : '搜索失败');
    } finally {
      setActionLoading('');
    }
  }

  // 生成技能
  async function handleGenerate() {
    if (!genTitle.trim()) {
      setActionMsg('请输入技能标题');
      return;
    }
    const historyIds = genHistoryIds
      .split(/[\n,]/g)
      .map(s => s.trim())
      .filter(Boolean);
    if (historyIds.length === 0) {
      setActionMsg('请至少输入一个历史 ID');
      return;
    }
    setActionLoading('generate');
    setError('');
    try {
      const res = await historyToSkillApi.generate({
        title: genTitle.trim(),
        description: genDescription.trim(),
        history_ids: historyIds,
        output_dir: genOutputDir.trim() || undefined,
      });
      setGenResult(res);
      setActionMsg('技能生成完成');
    } catch (e) {
      setError(e instanceof Error ? e.message : '生成失败');
    } finally {
      setActionLoading('');
    }
  }

  // 端到端运行
  async function handleRun() {
    setActionLoading('run');
    setError('');
    try {
      const res = await historyToSkillApi.run({
        query: runQuery,
        output_dir: runOutputDir || undefined,
      });
      setRunResult(res);
      setActionMsg('端到端流程完成');
    } catch (e) {
      setError(e instanceof Error ? e.message : '运行失败');
    } finally {
      setActionLoading('');
    }
  }

  // 验证技能
  async function handleValidate() {
    if (!validateDir.trim()) {
      setActionMsg('请输入技能目录路径');
      return;
    }
    setActionLoading('validate');
    setError('');
    try {
      const res = await historyToSkillApi.validate(validateDir.trim());
      setValidateResult(res);
      setActionMsg('');
    } catch (e) {
      setError(e instanceof Error ? e.message : '验证失败');
    } finally {
      setActionLoading('');
    }
  }

  return (
    <div>
      <PageHeader
        title="历史转技能"
        subtitle="从调试历史中提炼可复用技能"
        icon="fa-magic-wand-sparkles"
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
        <Loading text="加载历史转技能状态" />
      ) : (
        <div className="space-y-4">
          {/* 状态卡片 */}
          {status && (
            <Card>
              <h3 className="mb-3 text-sm font-medium text-ink-bg/80">服务状态</h3>
              <pre className="max-h-60 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                {JSON.stringify(status, null, 2)}
              </pre>
            </Card>
          )}

          {/* 历史查询区 */}
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
                <i className="fas fa-cubes text-copper" />
                模型变体查询
              </h3>
              <div className="space-y-3">
                <Input
                  label="模型名称"
                  placeholder="Qwen3.5-27B"
                  value={modelName}
                  onChange={e => setModelName(e.target.value)}
                />
                <Button size="sm" loading={actionLoading === 'variants'} onClick={handleVariants}>
                  <i className="fas fa-search mr-1.5" />
                  查询变体
                </Button>
                {variants && (
                  <pre className="max-h-60 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                    {JSON.stringify(variants, null, 2)}
                  </pre>
                )}
              </div>
            </Card>

            <Card>
              <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
                <i className="fas fa-sitemap text-copper" />
                根节点查询
              </h3>
              <div className="space-y-3">
                <Input
                  label="来源（可选，逗号分隔）"
                  placeholder="alignment,profiling"
                  value={sources}
                  onChange={e => setSources(e.target.value)}
                />
                <Button size="sm" loading={actionLoading === 'roots'} onClick={handleRoots}>
                  <i className="fas fa-sitemap mr-1.5" />
                  查询根节点
                </Button>
                {roots && (
                  <pre className="max-h-60 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                    {JSON.stringify(roots, null, 2)}
                  </pre>
                )}
              </div>
            </Card>
          </div>

          {/* 历史搜索 */}
          <Card>
            <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
              <i className="fas fa-search-plus text-copper" />
              历史搜索
            </h3>
            <div className="grid gap-3 lg:grid-cols-3">
              <Input
                label="查询关键词"
                placeholder="OOM, ACL, ..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
              />
              <Input
                label="来源过滤（可选）"
                placeholder="profiling"
                value={searchSources}
                onChange={e => setSearchSources(e.target.value)}
              />
              <Input
                label="数量上限"
                type="number"
                value={searchLimit}
                onChange={e => setSearchLimit(e.target.value)}
              />
            </div>
            <div className="mt-3">
              <Button size="sm" loading={actionLoading === 'search'} onClick={handleSearch}>
                <i className="fas fa-search mr-1.5" />
                搜索
              </Button>
            </div>
            {searchResults && (
              <pre className="mt-3 max-h-80 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                {JSON.stringify(searchResults, null, 2)}
              </pre>
            )}
          </Card>

          {/* 技能生成 */}
          <Card>
            <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
              <i className="fas fa-wand-magic-sparkles text-copper" />
              技能生成
            </h3>
            <div className="grid gap-3 lg:grid-cols-2">
              <Input
                label="技能标题"
                placeholder="OOM 自动诊断技能"
                value={genTitle}
                onChange={e => setGenTitle(e.target.value)}
              />
              <Input
                label="输出目录（可选）"
                placeholder="skills/oom-diagnosis"
                value={genOutputDir}
                onChange={e => setGenOutputDir(e.target.value)}
              />
            </div>
            <div className="mt-3">
              <Textarea
                label="技能描述"
                rows={2}
                placeholder="描述该技能的用途与触发场景..."
                value={genDescription}
                onChange={e => setGenDescription(e.target.value)}
              />
            </div>
            <div className="mt-3">
              <Textarea
                label="历史 ID 列表（逗号或换行分隔）"
                rows={3}
                placeholder="hist-001&#10;hist-002"
                value={genHistoryIds}
                onChange={e => setGenHistoryIds(e.target.value)}
              />
            </div>
            <div className="mt-3">
              <Button size="sm" loading={actionLoading === 'generate'} onClick={handleGenerate}>
                <i className="fas fa-wand-magic-sparkles mr-1.5" />
                生成技能
              </Button>
            </div>
            {genResult && (
              <pre className="mt-3 max-h-80 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                {JSON.stringify(genResult, null, 2)}
              </pre>
            )}
          </Card>

          {/* 端到端运行 */}
          <Card>
            <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
              <i className="fas fa-play-circle text-copper" />
              端到端运行（搜索 + 生成）
            </h3>
            <div className="grid gap-3 lg:grid-cols-2">
              <Input
                label="查询关键词"
                placeholder="ACL Graph 失败"
                value={runQuery}
                onChange={e => setRunQuery(e.target.value)}
              />
              <Input
                label="输出目录（可选）"
                placeholder="skills/auto-generated"
                value={runOutputDir}
                onChange={e => setRunOutputDir(e.target.value)}
              />
            </div>
            <div className="mt-3">
              <Button size="sm" loading={actionLoading === 'run'} onClick={handleRun}>
                <i className="fas fa-play mr-1.5" />
                一键运行
              </Button>
            </div>
            {runResult && (
              <pre className="mt-3 max-h-80 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                {JSON.stringify(runResult, null, 2)}
              </pre>
            )}
          </Card>

          {/* 技能验证 */}
          <Card>
            <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
              <i className="fas fa-check-circle text-copper" />
              技能验证
            </h3>
            <div className="grid gap-3 lg:grid-cols-2">
              <Input
                label="技能目录路径"
                placeholder="skills/oom-diagnosis"
                value={validateDir}
                onChange={e => setValidateDir(e.target.value)}
              />
              <div className="flex items-end">
                <Button size="sm" loading={actionLoading === 'validate'} onClick={handleValidate}>
                  <i className="fas fa-vial mr-1.5" />
                  验证
                </Button>
              </div>
            </div>
            {validateResult && (
              <pre className="mt-3 max-h-80 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                {JSON.stringify(validateResult, null, 2)}
              </pre>
            )}
          </Card>

          {/* 快速参考 */}
          {quickRef ? (
            <Card>
              <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
                <i className="fas fa-book text-copper" />
                快速参考
              </h3>
              <pre className="max-h-96 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                {JSON.stringify(quickRef, null, 2)}
              </pre>
            </Card>
          ) : !loading && <EmptyState icon="fa-book" title="暂无快速参考" />}
        </div>
      )}
    </div>
  );
}

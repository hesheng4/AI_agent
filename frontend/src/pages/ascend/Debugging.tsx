// 调试辅助 — 状态监控 + 快速诊断 + 会话管理 + 红旗检测 + 快速参考
import { useState, useEffect, useCallback } from 'react';
import { PageHeader, Button, Card, Input, Textarea, Loading, EmptyState, ErrorBanner } from '../../components/ui';
import { debuggingApi } from '../../api';

interface Session {
  id: string;
  title?: string;
  created_at?: string;
  [key: string]: unknown;
}

type DetailTab = 'info' | 'report' | 'flags';

export default function Debugging() {
  // 顶层状态
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionsTotal, setSessionsTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // 快速诊断
  const [errorText, setErrorText] = useState('');
  const [diagnoseResult, setDiagnoseResult] = useState<Record<string, unknown> | null>(null);
  const [diagnosing, setDiagnosing] = useState(false);

  // 创建会话
  const [newTitle, setNewTitle] = useState('');
  const [creating, setCreating] = useState(false);

  // 会话详情
  const [selectedId, setSelectedId] = useState<string>('');
  const [detailTab, setDetailTab] = useState<DetailTab>('info');
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // 快速参考
  const [quickRef, setQuickRef] = useState<Record<string, unknown> | null>(null);

  // 初始加载：状态 + 会话列表 + 快速参考
  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [s, sess, ref] = await Promise.all([
        debuggingApi.status().catch(() => null),
        debuggingApi.sessions().catch(() => ({ sessions: [], total: 0 })),
        debuggingApi.quickReference().catch(() => null),
      ]);
      setStatus(s);
      setSessions((sess?.sessions as Session[]) || []);
      setSessionsTotal(sess?.total ?? 0);
      setQuickRef(ref);
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // 选中会话或切换 Tab 时加载详情
  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    setDetailLoading(true);
    setDetail(null);
    const promise =
      detailTab === 'info'
        ? debuggingApi.getSession(selectedId)
        : detailTab === 'report'
          ? debuggingApi.report(selectedId)
          : debuggingApi.redFlags(selectedId);
    promise
      .then(setDetail)
      .catch(e => setError(e instanceof Error ? e.message : '加载详情失败'))
      .finally(() => setDetailLoading(false));
  }, [selectedId, detailTab]);

  // 快速诊断
  async function handleQuickDiagnose() {
    if (!errorText.trim()) {
      setError('请输入错误文本');
      return;
    }
    setDiagnosing(true);
    setError('');
    try {
      const res = await debuggingApi.quickDiagnose(errorText);
      setDiagnoseResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : '诊断失败');
    } finally {
      setDiagnosing(false);
    }
  }

  // 创建新会话
  async function handleCreateSession() {
    setCreating(true);
    setError('');
    try {
      const created = await debuggingApi.createSession(newTitle);
      setNewTitle('');
      // 刷新列表并选中新建会话
      const sess = await debuggingApi.sessions().catch(() => ({ sessions: [], total: 0 }));
      setSessions((sess?.sessions as Session[]) || []);
      setSessionsTotal(sess?.total ?? 0);
      const newId = (created?.id as string) || ((created?.session as Session)?.id as string) || '';
      if (newId) {
        setSelectedId(newId);
        setDetailTab('info');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '创建会话失败');
    } finally {
      setCreating(false);
    }
  }

  // 选中会话
  function handleSelectSession(id: string) {
    setSelectedId(id);
    setDetailTab('info');
  }

  // 直接查看某 Tab（用于会话列表上的快捷按钮）
  function handleViewTab(id: string, tab: DetailTab) {
    setSelectedId(id);
    setDetailTab(tab);
  }

  // 安全取值辅助
  const statusText = status ? (status.status as string) || (status.state as string) || '-' : '-';
  const activeSessions = (status?.active_sessions as number) ?? sessionsTotal;

  return (
    <div>
      <PageHeader
        title="调试辅助"
        subtitle="错误诊断 · 会话管理 · 红旗检测"
        icon="fa-bug"
        action={
          <Button variant="secondary" size="sm" onClick={load}>
            <i className="fas fa-redo mr-1.5" />
            刷新
          </Button>
        }
      />

      {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

      {/* 状态卡片 */}
      <Card className="mb-4">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
          <i className="fas fa-heartbeat text-copper" />
          调试状态
        </h3>
        {loading ? (
          <Loading text="加载调试状态" />
        ) : status ? (
          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between border-b border-copper/5 pb-1.5">
              <span className="text-ink-bg/60">服务状态</span>
              <span className="rounded bg-copper/10 px-2 py-0.5 text-copper-light">{statusText}</span>
            </div>
            <div className="flex items-center justify-between border-b border-copper/5 pb-1.5">
              <span className="text-ink-bg/60">活跃会话</span>
              <span className="text-ink-bg/80">{String(activeSessions)}</span>
            </div>
            <pre className="mt-2 max-h-48 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
              {JSON.stringify(status, null, 2)}
            </pre>
          </div>
        ) : (
          <EmptyState icon="fa-heartbeat" title="无状态数据" />
        )}
      </Card>

      {/* 快速诊断 */}
      <Card className="mb-4">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
          <i className="fas fa-stethoscope text-copper" />
          快速诊断
        </h3>
        <div className="space-y-3">
          <Textarea
            label="错误文本"
            rows={6}
            placeholder="粘贴 NPU/vLLM 错误日志..."
            value={errorText}
            onChange={e => setErrorText(e.target.value)}
          />
          <Button onClick={handleQuickDiagnose} loading={diagnosing} disabled={!errorText.trim()}>
            <i className="fas fa-bolt mr-1.5" />
            快速诊断
          </Button>
          {diagnoseResult ? (
            <pre className="max-h-96 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
              {JSON.stringify(diagnoseResult, null, 2)}
            </pre>
          ) : (
            <EmptyState icon="fa-file-medical" title="暂无诊断结果" hint="提交错误文本后将显示诊断信息" />
          )}
        </div>
      </Card>

      {/* 会话管理 + 详情 */}
      <div className="grid gap-4 lg:grid-cols-2">
        {/* 会话列表 */}
        <Card>
          <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
            <i className="fas fa-list text-copper" />
            会话列表
            <span className="ml-auto text-xs text-ink-bg/60">共 {sessionsTotal} 个</span>
          </h3>

          {/* 创建新会话 */}
          <div className="mb-4 flex gap-2">
            <Input
              placeholder="会话标题（可选）"
              value={newTitle}
              onChange={e => setNewTitle(e.target.value)}
            />
            <Button onClick={handleCreateSession} loading={creating}>
              <i className="fas fa-plus mr-1.5" />
              新建
            </Button>
          </div>

          {loading ? (
            <Loading text="加载会话列表" />
          ) : sessions.length > 0 ? (
            <div className="max-h-96 space-y-2 overflow-auto pr-1">
              {sessions.map(s => (
                <div
                  key={s.id}
                  className={`rounded-lg border p-3 transition-colors ${
                    selectedId === s.id
                      ? 'border-copper/60 bg-copper/5'
                      : 'border-copper/10 bg-ink-dark/40 hover:border-copper/30'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <button
                      className="flex-1 cursor-pointer text-left"
                      onClick={() => handleSelectSession(s.id)}
                    >
                      <div className="text-sm text-ink-bg/80">
                        {s.title || <span className="text-ink-bg/60">未命名会话</span>}
                      </div>
                      <div className="mt-0.5 text-[10px] text-ink-bg/60">
                        ID: {s.id}
                        {s.created_at && ` · ${s.created_at}`}
                      </div>
                    </button>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    <Button size="sm" variant="ghost" onClick={() => handleViewTab(s.id, 'info')}>
                      <i className="fas fa-info-circle mr-1" />
                      详情
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => handleViewTab(s.id, 'report')}>
                      <i className="fas fa-file-alt mr-1" />
                      报告
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => handleViewTab(s.id, 'flags')}>
                      <i className="fas fa-flag mr-1" />
                      红旗
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState icon="fa-folder-open" title="暂无会话" hint="点击上方「新建」按钮创建调试会话" />
          )}
        </Card>

        {/* 会话详情 */}
        <Card>
          <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink-bg/80">
            <i className="fas fa-search text-copper" />
            会话详情
          </h3>

          {!selectedId ? (
            <EmptyState icon="fa-hand-pointer" title="未选择会话" hint="从左侧列表选择一个会话查看详情" />
          ) : (
            <>
              {/* Tab 切换 */}
              <div className="mb-3 flex gap-1 border-b border-copper/10">
                {([
                  { key: 'info' as DetailTab, label: '基本信息', icon: 'fa-info-circle' },
                  { key: 'report' as DetailTab, label: '诊断报告', icon: 'fa-file-alt' },
                  { key: 'flags' as DetailTab, label: '红旗警告', icon: 'fa-flag' },
                ]).map(t => (
                  <button
                    key={t.key}
                    onClick={() => setDetailTab(t.key)}
                    className={`cursor-pointer border-b-2 px-3 py-2 text-xs transition-colors ${
                      detailTab === t.key
                        ? 'border-copper text-copper-light'
                        : 'border-transparent text-ink-bg/50 hover:text-ink-bg/80'
                    }`}
                  >
                    <i className={`fas ${t.icon} mr-1.5`} />
                    {t.label}
                  </button>
                ))}
              </div>

              {/* 详情内容 */}
              {detailLoading ? (
                <Loading text="加载详情" />
              ) : detail ? (
                <pre className="max-h-96 overflow-auto rounded-lg bg-ink-dark/40 p-3 text-xs text-ink-bg/70">
                  {JSON.stringify(detail, null, 2)}
                </pre>
              ) : (
                <EmptyState icon="fa-inbox" title="无数据" />
              )}
            </>
          )}
        </Card>
      </div>

      {/* 快速参考 */}
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
          <EmptyState icon="fa-book" title="暂无快速参考" />
        )}
      </Card>
    </div>
  );
}

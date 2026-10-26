// 分享与 fork 页 — 整库分享 / token 兑换 / fork 深拷贝
import { useCallback, useEffect, useState } from 'react';
import { PageHeader, Button, Card, Input, ErrorBanner } from '../components/ui';
import {
  sharesApi,
  type ShareCreateResult,
  type ShareItem,
  type SharedLibraryPreview,
} from '../api';

export default function SharesPage() {
  const [items, setItems] = useState<ShareItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [ttlDays, setTtlDays] = useState('7');

  // 兑换区
  const [token, setToken] = useState('');
  const [preview, setPreview] = useState<SharedLibraryPreview | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setItems(await sharesApi.list());
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载分享列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleCreate() {
    const days = ttlDays.trim() === '' ? null : Number(ttlDays);
    if (days !== null && (!Number.isFinite(days) || days < 1 || days > 365)) {
      setError('有效期须为 1-365 天，或留空表示永久');
      return;
    }
    setError(""); setSuccess("");
    try {
      const created: ShareCreateResult = await sharesApi.create({
        resource_type: 'library',
        ttl_days: days,
      });
      setSuccess(`分享已创建。明文 token 只显示这一次，请立即复制保存：\n${created.token}`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建分享失败');
    }
  }

  async function handleRevoke(id: string) {
    if (!window.confirm('确定撤销该分享？撤销后任何人都无法再访问。')) return;
    try {
      await sharesApi.revoke(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : '撤销失败');
    }
  }

  async function handlePreview() {
    setError(""); setSuccess("");
    if (!token.trim()) {
      setError('请输入分享 token');
      return;
    }
    try {
      setPreview(await sharesApi.preview(token.trim()));
    } catch (err) {
      setError(err instanceof Error ? err.message : '分享无效或已过期');
    }
  }

  async function handleFork() {
    setError(""); setSuccess("");
    try {
      const stats = await sharesApi.fork(token.trim());
      setSuccess(
        `fork 完成：文献 ${stats.papers_added}（跳过 ${stats.papers_skipped}），`
        + `分类 ${stats.categories_created}，标签 ${stats.tags_created}，`
        + `笔记 ${stats.notes_copied}，引用 ${stats.citations_copied}（跳过 ${stats.citations_skipped}）`,
      );
      setPreview(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'fork 失败');
    }
  }

  return (
    <div>
      <PageHeader title="分享与 Fork" subtitle="整库分享链接 · token 一次性展示 · 深拷贝导入" icon="fa-share-nodes" />

      {error && <ErrorBanner message={error} />}
      {success && (
        <Card className="mb-6 border-jade/30">
          <pre className="whitespace-pre-wrap break-all text-xs text-jade">{success}</pre>
        </Card>
      )}

      <div className="mb-6 grid gap-4 lg:grid-cols-2">
        <Card>
          <h3 className="mb-3 text-sm font-medium text-ink-bg">
            <i className="fas fa-paper-plane mr-1.5 text-copper-light" />创建我的文献库分享
          </h3>
          <div className="flex items-end gap-3">
            <div className="flex-1">
              <Input
                label="有效期（天，留空 = 永久）"
                icon="fa-clock"
                value={ttlDays}
                onChange={e => setTtlDays(e.target.value)}
                placeholder="7"
              />
            </div>
            <Button onClick={() => void handleCreate()} loading={loading}>
              <i className="fas fa-plus mr-1.5" />创建分享
            </Button>
          </div>
          <p className="mt-3 text-xs text-ink-bg/40">
            数据库只存 token 的 SHA-256 哈希，明文仅在创建后展示一次；接收方必须登录，可随时撤销。
          </p>
        </Card>

        <Card>
          <h3 className="mb-3 text-sm font-medium text-ink-bg">
            <i className="fas fa-right-to-bracket mr-1.5 text-copper-light" />兑换分享 token
          </h3>
          <div className="flex items-end gap-3">
            <div className="flex-1">
              <Input
                label="分享 token"
                icon="fa-key"
                value={token}
                onChange={e => setToken(e.target.value)}
                placeholder="粘贴他人分享的 token"
              />
            </div>
            <Button onClick={() => void handlePreview()} loading={loading}>
              <i className="fas fa-eye mr-1.5" />预览
            </Button>
          </div>
          {preview && (
            <div className="mt-3 rounded-md border border-copper/20 bg-copper/5 p-3 text-xs text-ink-bg/70">
              <div className="mb-1.5 font-medium text-copper-light">
                {preview.owner} 的文献库 · {preview.paper_count} 篇文献 · {preview.citation_count} 条引用
              </div>
              <div>分类：{preview.categories.join('、') || '—'}</div>
              <div>标签：{preview.tags.join('、') || '—'}</div>
              <Button className="mt-2" onClick={() => void handleFork()}>
                <i className="fas fa-clone mr-1.5" />Fork 到我的文献库
              </Button>
            </div>
          )}
        </Card>
      </div>

      <Card>
        <h3 className="mb-3 text-sm font-medium text-ink-bg">
          <i className="fas fa-list mr-1.5 text-copper-light" />我创建的分享
        </h3>
        {items.length === 0 ? (
          <p className="py-4 text-center text-xs text-ink-bg/40">暂无分享记录</p>
        ) : (
          <div className="divide-y divide-copper/10">
            {items.map(s => (
              <div key={s.id} className="flex items-center justify-between gap-3 py-2.5 text-xs">
                <div className="flex items-center gap-2">
                  <span className="rounded-full border border-copper/20 bg-copper/5 px-2 py-0.5 text-copper-light">
                    {s.resource_type}
                  </span>
                  <span className="text-ink-bg/50">
                    {s.expires_at ? `过期：${new Date(s.expires_at).toLocaleString()}` : '永久有效'}
                  </span>
                  {s.revoked && <span className="text-red-400">已撤销</span>}
                </div>
                {!s.revoked && (
                  <button
                    onClick={() => void handleRevoke(s.id)}
                    className="cursor-pointer rounded-md border border-red-500/20 px-2 py-1 text-red-400 hover:bg-red-500/10"
                  >
                    撤销
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

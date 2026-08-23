// 个人中心 — 账号设置 + API 用量卡片 + 自定义 API 密钥
import { useState, useEffect, type FormEvent } from 'react';
import { motion } from 'motion/react';
import { PageHeader, Button, Card, Input, Textarea, ErrorBanner, Badge } from '../components/ui';
import { useAuth } from '../auth';
import { authApi, billingApi } from '../api';
import type { UsageResponse } from '../types';

// 套餐对应的 API 调用上限（用于进度条计算）
const PLAN_LIMITS: Record<string, number> = {
  free: 1000,
  pro: 10000,
  team: 50000,
  enterprise: 200000,
};

export default function Profile() {
  const { user, setUser } = useAuth();

  // 账号资料表单
  const [username, setUsername] = useState('');
  const [bio, setBio] = useState('');
  const [institution, setInstitution] = useState('');

  // 自定义 API 配置
  const [apiKey, setApiKey] = useState('');
  const [apiBaseUrl, setApiBaseUrl] = useState('');
  const [apiModel, setApiModel] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);

  // 修改密码
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [pwdSaving, setPwdSaving] = useState(false);

  // API 连通测试
  const [testingApi, setTestingApi] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string; model?: string; response_preview?: string } | null>(null);

  // 用量数据
  const [usage, setUsage] = useState<UsageResponse | null>(null);

  // 状态
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savingApi, setSavingApi] = useState(false);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  // 初始化加载
  useEffect(() => {
    if (user) {
      setUsername(user.username || '');
      setBio(user.bio || '');
      setInstitution(user.institution || '');
      setApiBaseUrl(user.api_base_url || '');
      setApiModel(user.api_model || '');
      // api_key_configured 是布尔，不回填真实密钥（安全）
      setApiKey(user.api_key_configured ? '••••••••••••••••' : '');
    }
    billingApi
      .usage()
      .then(setUsage)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [user]);

  // 保存账号资料
  async function handleSaveProfile(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError('');
    setSuccessMsg('');
    try {
      const updated = await authApi.updateProfile({ username, bio, institution });
      setUser(updated);  // 同步本地用户状态
      setSuccessMsg('资料已保存');
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败');
    } finally {
      setSaving(false);
    }
  }

  // 保存自定义 API 配置
  async function handleSaveApi(e: FormEvent) {
    e.preventDefault();
    setSavingApi(true);
    setError('');
    setSuccessMsg('');
    try {
      // 若密钥仍是占位符，不发送（保留后端原值）；否则发送新密钥
      const apiKeyToSend = apiKey === '••••••••••••••••' ? undefined : apiKey.trim();
      await authApi.updateProfile({
        api_base_url: apiBaseUrl.trim() || null,
        api_model: apiModel.trim() || null,
        ...(apiKeyToSend ? { api_key: apiKeyToSend, api_key_configured: true } : {}),
      });
      setSuccessMsg('API 配置已保存');
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败');
    } finally {
      setSavingApi(false);
    }
  }

  // 修改密码
  async function handleChangePassword(e: FormEvent) {
    e.preventDefault();
    setPwdSaving(true);
    setError('');
    setSuccessMsg('');
    if (newPassword !== confirmPassword) {
      setError('两次输入的新密码不一致');
      setPwdSaving(false);
      return;
    }
    try {
      const res = await authApi.changePassword({
        old_password: oldPassword,
        new_password: newPassword,
      });
      setSuccessMsg(res.message || '密码已修改');
      setOldPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err) {
      setError(err instanceof Error ? err.message : '修改密码失败');
    } finally {
      setPwdSaving(false);
    }
  }

  // 测试自定义 API 连通性
  async function handleTestApi() {
    setTestingApi(true);
    setTestResult(null);
    setError('');
    try {
      const apiKeyToSend = apiKey === '••••••••••••••••' ? undefined : apiKey.trim();
      const res = await authApi.testApiConfig({
        api_key: apiKeyToSend,
        api_base_url: apiBaseUrl.trim() || undefined,
        api_model: apiModel.trim() || undefined,
      });
      setTestResult(res);
    } catch (err) {
      setTestResult({ success: false, message: err instanceof Error ? err.message : '连通测试失败' });
    } finally {
      setTestingApi(false);
    }
  }

  // 用量进度计算 — 防御除零
  const planLimit = usage ? PLAN_LIMITS[usage.plan.toLowerCase()] || 1000 : 1000;
  const apiPercent = planLimit > 0 ? Math.min(100, (usage?.api_calls_used || 0) / planLimit * 100) : 0;
  const tokenLimit = planLimit * 1000; // 粗略估算
  const tokenPercent = tokenLimit > 0 ? Math.min(100, (usage?.tokens_used || 0) / tokenLimit * 100) : 0;

  return (
    <div>
      <PageHeader
        title="个人中心"
        subtitle="账号设置 · API 用量 · 自定义模型配置"
        icon="fa-user-circle"
      />

      {error && <div className="mb-4"><ErrorBanner message={error} /></div>}
      {successMsg && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-jade/30 bg-jade/10 px-4 py-2.5 text-sm text-jade">
          <i className="fas fa-check-circle" />
          {successMsg}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center gap-3 py-12 text-ink-bg/50">
          <i className="fas fa-circle-notch animate-spin text-copper" />
          <span className="text-sm">加载中</span>
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-3">
          {/* ===== 左列：账号资料 + API 配置 ===== */}
          <div className="space-y-6 lg:col-span-2">
            {/* 账号资料 */}
            <Card>
              <div className="mb-4 flex items-center gap-2">
                <i className="fas fa-id-card text-copper" />
                <h3 className="font-serif text-base text-ink-bg">账号资料</h3>
              </div>
              <form onSubmit={handleSaveProfile} className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <Input label="邮箱" value={user?.email || ''} disabled />
                  <Input label="角色" value={user?.role || ''} disabled />
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Input
                    label="用户名"
                    value={username}
                    onChange={e => setUsername(e.target.value)}
                  />
                  <Input
                    label="所属机构"
                    value={institution}
                    onChange={e => setInstitution(e.target.value)}
                    placeholder="如：清华大学"
                  />
                </div>
                <Textarea
                  label="个人简介"
                  rows={3}
                  value={bio}
                  onChange={e => setBio(e.target.value)}
                  placeholder="介绍一下你的研究方向..."
                />
                <div className="flex justify-end">
                  <Button type="submit" loading={saving}>
                    <i className="fas fa-save mr-1.5" />
                    保存资料
                  </Button>
                </div>
              </form>
            </Card>

            {/* 自定义 API 配置 */}
            <Card>
              <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <i className="fas fa-key text-copper" />
                  <h3 className="font-serif text-base text-ink-bg">自定义 API 配置</h3>
                </div>
                {user?.api_key_configured && (
                  <Badge variant="jade">
                    <i className="fas fa-check-circle" />
                    已配置
                  </Badge>
                )}
              </div>
              <p className="mb-4 text-xs text-ink-bg/60">
                填入自己的 API 密钥后，平台将使用你的密钥调用模型，不消耗平台配额。
              </p>
              <form onSubmit={handleSaveApi} className="space-y-4">
                <div className="relative">
                  <Input
                    label="API Key"
                    type={showApiKey ? 'text' : 'password'}
                    value={apiKey}
                    onChange={e => setApiKey(e.target.value)}
                    placeholder="sk-..."
                    className="pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowApiKey(!showApiKey)}
                    className="absolute right-3 top-[34px] cursor-pointer text-ink-bg/60 transition-colors hover:text-copper-light"
                    aria-label={showApiKey ? '隐藏密钥' : '显示密钥'}
                  >
                    <i className={`fas ${showApiKey ? 'fa-eye-slash' : 'fa-eye'}`} />
                  </button>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Input
                    label="API Base URL"
                    value={apiBaseUrl}
                    onChange={e => setApiBaseUrl(e.target.value)}
                    placeholder="https://api.openai.com/v1"
                  />
                  <Input
                    label="模型名称"
                    value={apiModel}
                    onChange={e => setApiModel(e.target.value)}
                    placeholder="gpt-4o / qwen-max / ..."
                  />
                </div>
                <div className="flex justify-end">
                  <Button type="submit" loading={savingApi}>
                    <i className="fas fa-plug mr-1.5" />
                    保存 API 配置
                  </Button>
                </div>
              </form>

              {/* API 连通测试 */}
              <div className="mt-4 border-t border-copper/10 pt-4">
                <div className="mb-2 flex items-center gap-2">
                  <i className="fas fa-satellite-dish text-copper" />
                  <span className="text-xs font-medium text-ink-bg/70">连通性测试</span>
                </div>
                <p className="mb-3 text-xs text-ink-bg/60">
                  使用当前表单中的 API 配置发起一次最小请求，验证密钥与 Base URL 是否可用。
                </p>
                <div className="flex flex-wrap items-center gap-2">
                  <Button variant="secondary" size="sm" onClick={handleTestApi} loading={testingApi}>
                    <i className="fas fa-bolt mr-1" />
                    测试连通
                  </Button>
                  {testResult && (
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs ${
                        testResult.success
                          ? 'border border-jade/30 bg-jade/10 text-jade'
                          : 'border border-vermillion/30 bg-vermillion/10 text-vermillion'
                      }`}
                    >
                      <i className={`fas ${testResult.success ? 'fa-circle-check' : 'fa-circle-xmark'}`} />
                      {testResult.success
                        ? `连接成功${testResult.model ? ` · ${testResult.model}` : ''}`
                        : (testResult.message || '连接失败')}
                    </span>
                  )}
                </div>
              </div>
            </Card>

            {/* 修改密码 */}
            <Card>
              <div className="mb-4 flex items-center gap-2">
                <i className="fas fa-lock text-copper" />
                <h3 className="font-serif text-base text-ink-bg">修改密码</h3>
              </div>
              <form onSubmit={handleChangePassword} className="space-y-4">
                <Input
                  label="当前密码"
                  type="password"
                  value={oldPassword}
                  onChange={e => setOldPassword(e.target.value)}
                  placeholder="输入当前密码"
                />
                <div className="grid gap-4 sm:grid-cols-2">
                  <Input
                    label="新密码"
                    type="password"
                    value={newPassword}
                    onChange={e => setNewPassword(e.target.value)}
                    placeholder="至少 8 位，含大小写/数字/符号中的两类"
                  />
                  <Input
                    label="确认新密码"
                    type="password"
                    value={confirmPassword}
                    onChange={e => setConfirmPassword(e.target.value)}
                    placeholder="再次输入新密码"
                  />
                </div>
                <div className="flex justify-end">
                  <Button type="submit" loading={pwdSaving} disabled={!oldPassword || !newPassword || !confirmPassword}>
                    <i className="fas fa-key mr-1.5" />
                    更新密码
                  </Button>
                </div>
              </form>
            </Card>
          </div>

          {/* ===== 右列：用量数据卡片 ===== */}
          <div className="space-y-6">
            {/* 当前套餐 */}
            <Card>
              <div className="mb-3 flex items-center justify-between">
                <span className="text-xs text-ink-bg/60">当前套餐</span>
                <Badge variant="copper">{usage?.plan || 'Free'}</Badge>
              </div>
              <div className="flex items-end gap-2">
                <span className="font-serif text-3xl text-tech-gradient">
                  {usage?.plan || 'Free'}
                </span>
                <span className="mb-1 text-xs text-ink-bg/60">Plan</span>
              </div>
              <p className="mt-2 text-xs text-ink-bg/60">
                {user?.api_key_configured
                  ? '已配置自定义 API，调用不消耗配额'
                  : '使用平台密钥，消耗套餐配额'}
              </p>
            </Card>

            {/* API 调用用量 */}
            <Card>
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <i className="fas fa-bolt text-copper" />
                  <span className="text-xs text-ink-bg/60">API 调用</span>
                </div>
                <span className="text-xs text-ink-bg/60">
                  {usage?.api_calls_used || 0} / {planLimit}
                </span>
              </div>
              {/* 进度条 */}
              <div className="h-2 overflow-hidden rounded-full bg-ink-bg/5">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${apiPercent}%` }}
                  transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                  className={`h-full rounded-full ${apiPercent > 80 ? 'bg-vermillion' : 'bg-gradient-to-r from-copper to-copper-light'}`}
                />
              </div>
              <p className="mt-2 text-[10px] text-ink-bg/50">
                {apiPercent.toFixed(1)}% 已使用
                {apiPercent > 80 && <span className="ml-1 text-vermillion">· 即将达上限</span>}
              </p>
            </Card>

            {/* Token 用量 */}
            <Card>
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <i className="fas fa-coins text-copper" />
                  <span className="text-xs text-ink-bg/60">Token 用量</span>
                </div>
                <span className="text-xs text-ink-bg/60">
                  {(usage?.tokens_used || 0).toLocaleString()}
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-ink-bg/5">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${tokenPercent}%` }}
                  transition={{ duration: 0.8, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
                  className="h-full rounded-full bg-gradient-to-r from-indigo to-copper-light"
                />
              </div>
              <p className="mt-2 text-[10px] text-ink-bg/50">
                {tokenPercent.toFixed(1)}% 已使用
              </p>
            </Card>

            {/* 账户信息 */}
            <Card>
              <div className="mb-3 flex items-center gap-2">
                <i className="fas fa-info-circle text-copper" />
                <span className="text-xs text-ink-bg/60">账户信息</span>
              </div>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-ink-bg/60">注册时间</span>
                  <span className="text-ink-bg/70">
                    {user?.created_at ? new Date(user.created_at).toLocaleDateString('zh-CN') : '-'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ink-bg/60">账户 ID</span>
                  <span className="font-mono text-ink-bg/70">{user?.id?.slice(0, 8)}...</span>
                </div>
              </div>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}

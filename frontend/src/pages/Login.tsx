// 登录/注册页 — SaaS Dashboard 风格：左侧品牌展示 + 右侧表单
import { useState, useEffect, lazy, Suspense, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'motion/react';
import DecryptedText from '../components/DecryptedText';
import { Input, ErrorBanner } from '../components/ui';
import { useAuth } from '../auth';

// P1-O4: Aurora WebGL 重组件懒加载，减少登录页首屏 JS
const Aurora = lazy(() => import('../components/Aurora'));
import { authApi } from '../api';

const AURORA_STOPS = ['#9A7E45', '#C9A961', '#E0C896'];

const BRAND_FEATURES = [
  { icon: 'fa-search', title: '智能文献检索', desc: '多源聚合 · AI 摘要' },
  { icon: 'fa-project-diagram', title: '引用图谱分析', desc: '网络洞察 · 影响力识别' },
  { icon: 'fa-microchip', title: '昇腾 NPU 工作台', desc: '本地推理 · 数据可控' },
  { icon: 'fa-pen-fancy', title: '论文写作工坊', desc: '大纲 · 润色 · 规范检查' },
];

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [mode, setMode] = useState<'login' | 'register' | 'forgot'>('login');
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const [resetToken, setResetToken] = useState('');
  const [resetNewPassword, setResetNewPassword] = useState('');
  const [resetStep, setResetStep] = useState<'request' | 'confirm'>('request');
  const [resetSuccess, setResetSuccess] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (mode === 'register') {
        if (!email.includes('@')) {
          setError('请输入有效的邮箱地址');
          setLoading(false);
          return;
        }
        if (username.trim().length < 3) {
          setError('用户名至少 3 个字符');
          setLoading(false);
          return;
        }
        if (password.length < 8) {
          setError('密码至少 8 个字符');
          setLoading(false);
          return;
        }
        await authApi.register({ email, username: username.trim(), password });
      }
      await login(email, password);
      navigate('/app');
    } catch (err) {
      setError(err instanceof Error ? err.message : '操作失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleForgotPassword(e: FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (!email.includes('@')) {
        setError('请输入有效的邮箱地址');
        setLoading(false);
        return;
      }
      const res = await authApi.forgotPassword(email);
      if (res.token) {
        setResetToken(res.token);
        setResetStep('confirm');
      } else {
        setError('如果该邮箱已注册，重置令牌已生成。当前环境未返回令牌，请联系管理员。');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '请求失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleResetPassword(e: FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (resetNewPassword.length < 8) {
        setError('新密码至少 8 个字符');
        setLoading(false);
        return;
      }
      await authApi.resetPassword(resetToken, resetNewPassword);
      setResetSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : '重置失败');
    } finally {
      setLoading(false);
    }
  }

  function switchMode(newMode: 'login' | 'register' | 'forgot') {
    setMode(newMode);
    setError('');
    setResetStep('request');
    setResetToken('');
    setResetNewPassword('');
    setResetSuccess(false);
  }

  useEffect(() => {
    if (resetSuccess) {
      const timer = setTimeout(() => switchMode('login'), 3000);
      return () => clearTimeout(timer);
    }
  }, [resetSuccess]);

  return (
    <div className="relative flex min-h-screen overflow-hidden bg-bg">
      {/* ===== 左侧：品牌展示 ===== */}
      <div className="relative hidden w-1/2 overflow-hidden lg:block">
        <div className="absolute inset-0 z-0 opacity-50">
          <Suspense fallback={null}>
            <Aurora colorStops={AURORA_STOPS} amplitude={1.0} blend={0.5} speed={0.6} />
          </Suspense>
        </div>

        <div className="relative z-10 flex h-full flex-col justify-between p-12 xl:p-16">
          {/* 顶部 Logo */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
            className="flex items-center gap-3"
          >
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/10 backdrop-blur-md">
              <i className="fas fa-atom text-xl text-primary" />
            </div>
            <div>
              <div className="text-lg font-semibold text-white">墨观</div>
              <div className="text-[10px] tracking-wider text-white/60">学术天文台</div>
            </div>
          </motion.div>

          {/* 中部标语 */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className="max-w-md"
          >
            <h1 className="mb-4 text-4xl font-bold leading-tight text-white xl:text-5xl">
              <DecryptedText
                text="探索学术宇宙"
                animateOn="view"
                speed={50}
                maxIterations={10}
                sequential
                revealDirection="center"
                className="text-white"
                encryptedClassName="text-white/40"
              />
            </h1>
            <p className="text-sm leading-relaxed text-white/70 xl:text-base">
              从文献发现到论文发表的全链路科研协作平台，集成昇腾 NPU 本地推理能力，让研究效率提升 10 倍。
            </p>
          </motion.div>

          {/* 底部特性列表 */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.8, delay: 0.6 }}
            className="grid max-w-md grid-cols-2 gap-4"
          >
            {BRAND_FEATURES.map((feature, i) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.7 + i * 0.1 }}
                className="rounded-lg border border-white/10 bg-white/5 p-3 backdrop-blur-md"
              >
                <i className={`fas ${feature.icon} mb-2 text-sm text-primary`} />
                <div className="text-xs font-medium text-white/90">{feature.title}</div>
                <div className="mt-0.5 text-[10px] text-white/50">{feature.desc}</div>
              </motion.div>
            ))}
          </motion.div>
        </div>

        <div className="pointer-events-none absolute right-0 top-0 z-[5] h-full w-24 bg-gradient-to-l from-bg/80 to-transparent" />
      </div>

      {/* ===== 右侧：表单区 ===== */}
      <div className="relative flex w-full items-center justify-center px-4 py-12 lg:w-1/2">
        <div className="absolute inset-0 z-0 opacity-30 lg:hidden">
          <Suspense fallback={null}>
            <Aurora colorStops={AURORA_STOPS} amplitude={0.8} blend={0.5} speed={0.5} />
          </Suspense>
        </div>

        <button
          onClick={() => navigate('/')}
          className="absolute left-6 top-6 z-20 flex cursor-pointer items-center gap-1.5 rounded-md px-2 py-1 text-xs text-txt-muted transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
        >
          <i className="fas fa-arrow-left" />
          返回首页
        </button>

        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="glass-panel relative z-10 w-full max-w-md rounded-2xl p-8"
        >
          {/* 标题 */}
          <div className="mb-8 text-center">
            <div className="mb-3 inline-flex h-14 w-14 items-center justify-center rounded-full bg-primary/10">
              <i className="fas fa-atom text-2xl text-primary" />
            </div>
            <h1 className="text-2xl font-semibold text-txt">
              {mode === 'login' ? '欢迎回来' : mode === 'register' ? '创建账户' : '重置密码'}
            </h1>
            <p className="mt-1 text-xs text-txt-muted">
              {mode === 'login' ? '登录您的账户，继续科研之旅' : mode === 'register' ? '注册新账户，开启科研之旅' : '输入邮箱获取重置令牌'}
            </p>
          </div>

          {/* 错误提示 */}
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="mb-4 overflow-hidden"
              >
                <ErrorBanner message={error} />
              </motion.div>
            )}
          </AnimatePresence>

          {/* 表单 */}
          {mode === 'forgot' ? (
            resetSuccess ? (
              <div className="space-y-4 text-center">
                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-success-bg">
                  <i className="fas fa-check text-2xl text-success" />
                </div>
                <p className="text-sm font-medium text-txt">密码重置成功！</p>
                <p className="text-xs text-txt-muted">3 秒后自动跳转登录页，或点击下方按钮</p>
                <button
                  type="button"
                  onClick={() => switchMode('login')}
                  className="mt-2 cursor-pointer rounded px-2 py-1 text-sm font-medium text-primary transition-colors hover:text-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-ring"
                >
                  <i className="fas fa-arrow-left mr-1.5" />
                  立即登录
                </button>
              </div>
            ) : resetStep === 'request' ? (
              <form onSubmit={handleForgotPassword} className="space-y-4">
                <Input
                  label="注册邮箱"
                  icon="fa-envelope"
                  type="email"
                  required
                  placeholder="you@example.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                />
                <button
                  type="submit"
                  disabled={loading}
                  className="btn-primary btn-lg w-full"
                >
                  {loading ? (
                    <i className="fas fa-circle-notch animate-spin" />
                  ) : (
                    <i className="fas fa-paper-plane" />
                  )}
                  获取重置令牌
                </button>
              </form>
            ) : (
              <form onSubmit={handleResetPassword} className="space-y-4">
                <div className="rounded-lg border border-primary-border bg-primary-muted p-3">
                  <p className="mb-1 text-xs font-medium text-primary">重置令牌</p>
                  <p className="break-all font-mono text-[11px] text-txt">{resetToken}</p>
                  <p className="mt-1 text-[10px] text-txt-muted">令牌 30 分钟内有效</p>
                </div>
                <Input
                  label="新密码"
                  icon="fa-lock"
                  type="password"
                  required
                  placeholder="至少 8 个字符"
                  value={resetNewPassword}
                  onChange={e => setResetNewPassword(e.target.value)}
                />
                <button
                  type="submit"
                  disabled={loading}
                  className="btn-primary btn-lg w-full"
                >
                  {loading ? (
                    <i className="fas fa-circle-notch animate-spin" />
                  ) : (
                    <i className="fas fa-key" />
                  )}
                  重置密码
                </button>
              </form>
            )
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <Input
                label="邮箱"
                icon="fa-envelope"
                type="email"
                required
                placeholder="you@example.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
              />

              <AnimatePresence>
                {mode === 'register' && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="overflow-hidden"
                  >
                    <Input
                      label="用户名"
                      icon="fa-user"
                      required
                      placeholder="您的昵称"
                      value={username}
                      onChange={e => setUsername(e.target.value)}
                    />
                  </motion.div>
                )}
              </AnimatePresence>

              <Input
                label="密码"
                icon="fa-lock"
                type="password"
                required
                placeholder="••••••••"
                value={password}
                onChange={e => setPassword(e.target.value)}
              />

              <button
                type="submit"
                disabled={loading}
                className="btn-primary btn-lg w-full"
              >
                {loading ? (
                  <i className="fas fa-circle-notch animate-spin" />
                ) : (
                  <i className={`fas ${mode === 'login' ? 'fa-sign-in-alt' : 'fa-user-plus'}`} />
                )}
                {mode === 'login' ? '登录' : '注册'}
              </button>
            </form>
          )}

          {/* 切换模式 */}
          <div className="mt-6 text-center text-xs text-txt-muted">
            {mode === 'login' && (
              <>
                还没有账户？
                <button
                  type="button"
                  onClick={() => switchMode('register')}
                  className="ml-1 cursor-pointer rounded px-1 font-medium text-primary transition-colors hover:text-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-ring"
                >
                  立即注册
                </button>
              </>
            )}
            {mode === 'register' && (
              <>
                已有账户？
                <button
                  type="button"
                  onClick={() => switchMode('login')}
                  className="ml-1 cursor-pointer rounded px-1 font-medium text-primary transition-colors hover:text-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-ring"
                >
                  去登录
                </button>
              </>
            )}
            {mode === 'forgot' && !resetSuccess && (
              <button
                type="button"
                onClick={() => switchMode('login')}
                className="cursor-pointer rounded px-1 font-medium text-primary transition-colors hover:text-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-ring"
              >
                <i className="fas fa-arrow-left mr-1.5" />
                返回登录
              </button>
            )}
          </div>

          {mode === 'login' && (
            <div className="mt-3 text-center">
              <button
                type="button"
                onClick={() => switchMode('forgot')}
                className="cursor-pointer rounded px-1 text-xs text-txt-muted transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-ring"
              >
                忘记密码？
              </button>
            </div>
          )}

          {/* 分隔线 */}
          <div className="my-6 flex items-center gap-3">
            <div className="h-px flex-1 bg-border" />
            <span className="text-[10px] text-txt-light">安全登录</span>
            <div className="h-px flex-1 bg-border" />
          </div>

          {/* 安全提示 */}
          <div className="flex items-center justify-center gap-2 text-[10px] text-txt-light">
            <i className="fas fa-shield-alt" />
            <span>JWT 加密 · 数据本地存储 · 隐私可控</span>
          </div>
        </motion.div>
      </div>
    </div>
  );
}

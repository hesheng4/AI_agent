// 主布局 — 学术天文台 · 暖金精密：顶部导航栏 + 命令面板 + 暖金统一配色
// 重构：移除全高侧栏，改为顶部品牌+导航+搜索+用户的一体化顶栏；
//       配色从蓝色 primary 切换为暖金系（与 Hero 一致），深墨底+暖金强调。
import { type ReactNode, useState, useEffect } from 'react';
import { NavLink, useNavigate, useLocation, Outlet } from 'react-router-dom';
import { motion, AnimatePresence } from 'motion/react';
import { useAuth } from '../auth';
import CommandPalette from './CommandPalette';

interface NavItem {
  to: string;
  icon: string;
  label: string;
}

interface NavGroup {
  id: string;
  title: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    id: 'research',
    title: '科研工作台',
    items: [
      { to: '/app/coordinator', icon: 'fa-route', label: '智能路由' },
      { to: '/app/literature', icon: 'fa-search', label: '文献检索' },
      { to: '/app/reader', icon: 'fa-book-open', label: '论文精读' },
      { to: '/app/library', icon: 'fa-bookmark', label: '文献库' },
      { to: '/app/network', icon: 'fa-project-diagram', label: '引用网络' },
      { to: '/app/citation', icon: 'fa-quote-right', label: '引用管理' },
      { to: '/app/data', icon: 'fa-chart-line', label: '数据分析' },
      { to: '/app/writing', icon: 'fa-pen-fancy', label: '论文写作' },
      { to: '/app/reviewer', icon: 'fa-user-check', label: '模拟审稿' },
      { to: '/app/response', icon: 'fa-reply', label: '审稿回复' },
      { to: '/app/review-loop', icon: 'fa-rotate', label: '审稿迭代' },
      { to: '/app/experiment', icon: 'fa-flask', label: '实验设计' },
      { to: '/app/figure', icon: 'fa-chart-column', label: '图表合同' },
      { to: '/app/cover', icon: 'fa-envelope', label: 'Cover Letter' },
      { to: '/app/methods', icon: 'fa-microscope', label: '方法论' },
      { to: '/app/stats', icon: 'fa-chart-pie', label: '统计审计' },
      { to: '/app/polishing', icon: 'fa-feather-pointed', label: '专业润色' },
      { to: '/app/paper2ppt', icon: 'fa-file-powerpoint', label: '论文转PPT' },
      { to: '/app/paper-to-patent', icon: 'fa-award', label: '论文转专利' },
      { to: '/app/submission-package', icon: 'fa-box', label: '投稿打包' },
      { to: '/app/data-availability', icon: 'fa-database', label: '数据可用性' },
      { to: '/app/artifacts', icon: 'fa-box-archive', label: '结果存档' },
      { to: '/app/shares', icon: 'fa-share-nodes', label: '分享与Fork' },
      { to: '/app/export', icon: 'fa-download', label: '数据导出' },
    ],
  },
  {
    id: 'ascend',
    title: '昇腾工作台',
    items: [
      { to: '/app/ascend', icon: 'fa-microchip', label: '环境概览' },
      { to: '/app/adaptation', icon: 'fa-puzzle-piece', label: '模型适配' },
      { to: '/app/alignment', icon: 'fa-balance-scale', label: '精度对齐' },
      { to: '/app/profiling', icon: 'fa-stopwatch', label: '性能采集' },
      { to: '/app/perf-tuning', icon: 'fa-gauge-high', label: '性能调优' },
      { to: '/app/toolchain', icon: 'fa-toolbox', label: '推理工具链' },
      { to: '/app/validator', icon: 'fa-check-double', label: '模型验证' },
      { to: '/app/debugging', icon: 'fa-bug', label: '调试辅助' },
      { to: '/app/history-to-skill', icon: 'fa-magic-wand-sparkles', label: '历史转技能' },
    ],
  },
];

const ROUTE_TITLES: Record<string, { title: string; group: string }> = {
  '/app/profile': { title: '个人中心', group: '账户' },
  '/app/audit': { title: '审计控制台', group: '系统' },
};
NAV_GROUPS.forEach(group => {
  group.items.forEach(item => {
    ROUTE_TITLES[item.to] = { title: item.label, group: group.title };
  });
});

// 暖金天文台品牌徽标（替换原蓝色）
function BrandLogo({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="brand-grad-gold" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#E0C896" />
          <stop offset="50%" stopColor="#C9A961" />
          <stop offset="100%" stopColor="#9A7E45" />
        </linearGradient>
      </defs>
      {/* 双椭圆轨道 — 天文台主题 */}
      <ellipse cx="50" cy="50" rx="36" ry="14" fill="none" stroke="url(#brand-grad-gold)" strokeWidth="2.5" transform="rotate(-25 50 50)" />
      <ellipse cx="50" cy="50" rx="36" ry="14" fill="none" stroke="url(#brand-grad-gold)" strokeWidth="2.5" strokeOpacity="0.45" transform="rotate(25 50 50)" />
      {/* 中心核 */}
      <circle cx="50" cy="50" r="7" fill="url(#brand-grad-gold)" />
      <circle cx="50" cy="50" r="3" fill="#F2E2C2" />
    </svg>
  );
}

export default function Layout({ children }: { children?: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [activeGroup, setActiveGroup] = useState<string>('research');
  const [navPanelOpen, setNavPanelOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [cmdOpen, setCmdOpen] = useState(false);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setCmdOpen(prev => !prev);
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // 路由变化时关闭所有浮层 + 同步当前分组（含审计台独立路由）
  useEffect(() => {
    setNavPanelOpen(false);
    setMenuOpen(false);
    const match = NAV_GROUPS.find(g => g.items.some(i => i.to === location.pathname));
    if (match) setActiveGroup(match.id);
    // /app/audit 不属于任何分组，保持当前 activeGroup 不变（面包屑由 ROUTE_TITLES 兜底）
  }, [location.pathname]);

  function handleLogout() {
    logout();
    navigate('/login');
  }

  const currentRoute = ROUTE_TITLES[location.pathname] || { title: '工作台', group: '' };
  const currentGroup = NAV_GROUPS.find(g => g.id === activeGroup) || NAV_GROUPS[0];

  return (
    <div className="relative min-h-screen bg-[#16110D] text-[#E8E4DC]">
      <CommandPalette open={cmdOpen} onClose={() => setCmdOpen(false)} />
      <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:z-[100] focus:rounded-lg focus:bg-[#C9A961] focus:px-4 focus:py-2 focus:text-[#16110D] focus:outline-none">跳到主内容</a>

      {/* 暖金颗粒肌理底色 */}
      <div className="pointer-events-none fixed inset-0 z-0 opacity-[0.025]" style={{
        backgroundImage: `radial-gradient(1px 1px at 15% 25%, rgba(201,169,97,0.5), transparent), radial-gradient(1px 1px at 70% 60%, rgba(224,200,150,0.4), transparent), radial-gradient(1px 1px at 40% 85%, rgba(201,169,97,0.35), transparent), radial-gradient(1.5px 1.5px at 85% 15%, rgba(224,200,150,0.5), transparent)`,
      }} />

      {/* ===== 顶部一体化导航栏 ===== */}
      <header className="sticky top-0 z-40 border-b border-[rgba(201,169,97,0.18)] bg-[rgba(22,17,13,0.85)] backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-[1600px] items-center justify-between gap-4 px-4 md:px-8">
          {/* 左：品牌 + 分组切换 */}
          <div className="flex items-center gap-6">
            <NavLink to="/app/coordinator" className="flex items-center gap-2.5 transition-opacity hover:opacity-90">
              <BrandLogo size={30} />
              <div className="hidden sm:block">
                <div className="font-serif text-sm font-semibold tracking-wide text-[#E0C896]">墨观</div>
                <div className="font-mono text-[9px] tracking-[0.2em] text-[rgba(201,169,97,0.72)] uppercase">学术天文台</div>
              </div>
            </NavLink>

            {/* 分组切换标签 */}
            <div className="hidden items-center gap-1 md:flex">
              {NAV_GROUPS.map(g => (
                <button
                  key={g.id}
                  onClick={() => { setActiveGroup(g.id); setNavPanelOpen(true); }}
                  onMouseEnter={() => { setActiveGroup(g.id); setNavPanelOpen(true); }}
                  className={`rounded-md px-3 py-1.5 font-mono text-xs tracking-wider uppercase transition-all ${
                    activeGroup === g.id && navPanelOpen
                      ? 'bg-black text-[#E0C896]'
                      : 'text-[rgba(232,228,220,0.55)] hover:bg-black/60 hover:text-[#E0C896]'
                  }`}
                >
                  {g.title}
                </button>
              ))}
              {/* 审计控制台快捷入口 */}
              <NavLink
                to="/app/audit"
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 font-mono text-xs tracking-wider uppercase transition-all ${
                    isActive
                      ? 'bg-black text-[#E0C896]'
                      : 'text-[rgba(232,228,220,0.55)] hover:bg-black/60 hover:text-[#E0C896]'
                  }`
                }
              >
                审计台
              </NavLink>
            </div>
          </div>

          {/* 右：搜索 + 用户 */}
          <div className="flex items-center gap-3">
            {/* 命令面板触发 */}
            <button
              onClick={() => setCmdOpen(true)}
              className="flex cursor-pointer items-center gap-2 rounded-lg border border-[rgba(201,169,97,0.25)] bg-black px-3 py-1.5 text-xs text-[#E0C896] transition-all hover:border-[rgba(201,169,97,0.5)] hover:bg-black/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(201,169,97,0.4)]"
            >
              <i className="fas fa-search" />
              <span className="hidden sm:inline">搜索</span>
              <kbd className="hidden rounded border border-[rgba(201,169,97,0.2)] bg-[rgba(201,169,97,0.05)] px-1 py-0.5 font-mono text-[9px] text-[rgba(201,169,97,0.72)] sm:inline">
                ⌘K
              </kbd>
            </button>

            {/* 当前页面面包屑（中屏以上） */}
            <div className="hidden items-center gap-2 text-xs lg:flex">
              <span className="font-mono text-[10px] tracking-wider text-[rgba(201,169,97,0.72)] uppercase">{currentRoute.group}</span>
              <i className="fas fa-chevron-right text-[8px] text-[rgba(201,169,97,0.55)]" />
              <span className="font-medium text-[#E0C896]">{currentRoute.title}</span>
            </div>

            {/* 用户下拉 */}
            <div className="relative">
              <button
                onClick={() => setMenuOpen(!menuOpen)}
                className="flex cursor-pointer items-center gap-2 rounded-lg border border-[rgba(201,169,97,0.25)] bg-black px-2 py-1.5 transition-colors hover:border-[rgba(201,169,97,0.5)] hover:bg-black/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(201,169,97,0.4)]"
              >
                <div className="flex h-8 w-8 items-center justify-center rounded-full border border-[rgba(201,169,97,0.35)] bg-black text-sm font-medium text-[#E0C896]">
                  {user?.avatar ? (
                    <img src={user.avatar} alt="" className="h-full w-full rounded-full" />
                  ) : (
                    user?.username?.[0]?.toUpperCase() || 'U'
                  )}
                </div>
                <span className="hidden text-sm text-[#E8E4DC] sm:inline">{user?.username}</span>
                <i className={`fas fa-chevron-down text-[10px] text-[rgba(201,169,97,0.72)] transition-transform duration-200 ${menuOpen ? 'rotate-180' : ''}`} />
              </button>

              <AnimatePresence>
                {menuOpen && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
                    <motion.div
                      initial={{ opacity: 0, y: -10, scale: 0.95 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: -10, scale: 0.95 }}
                      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                      className="absolute right-0 top-full z-50 mt-1 w-64 overflow-hidden rounded-xl border border-[rgba(201,169,97,0.22)] bg-[rgba(22,17,13,0.95)] shadow-2xl shadow-black/40 backdrop-blur-xl"
                    >
                      <div className="border-b border-[rgba(201,169,97,0.15)] px-4 py-3">
                        <div className="font-serif text-sm text-[#E0C896]">{user?.username}</div>
                        <div className="truncate font-mono text-xs text-[rgba(232,228,220,0.62)]">{user?.email}</div>
                      </div>

                      <div className="py-1">
                        <button
                          onClick={() => navigate('/app/profile')}
                          className="flex w-full cursor-pointer items-center gap-3 px-4 py-2 text-sm text-[rgba(232,228,220,0.6)] transition-colors hover:bg-[rgba(201,169,97,0.08)] hover:text-[#E0C896]"
                        >
                          <i className="fas fa-user-cog w-4 text-center text-[rgba(201,169,97,0.72)]" />
                          个人中心
                        </button>
                        <button
                          onClick={() => navigate('/app/profile')}
                          className="flex w-full cursor-pointer items-center gap-3 px-4 py-2 text-sm text-[rgba(232,228,220,0.6)] transition-colors hover:bg-[rgba(201,169,97,0.08)] hover:text-[#E0C896]"
                        >
                          <i className="fas fa-key w-4 text-center text-[rgba(201,169,97,0.72)]" />
                          API 密钥
                        </button>
                      </div>

                      <div className="border-t border-[rgba(201,169,97,0.15)]">
                        <button
                          onClick={handleLogout}
                          className="flex w-full cursor-pointer items-center gap-3 px-4 py-2.5 text-sm text-[#F87171] transition-colors hover:bg-[rgba(248,113,113,0.08)]"
                        >
                          <i className="fas fa-sign-out-alt w-4 text-center" />
                          退出登录
                        </button>
                      </div>
                    </motion.div>
                  </>
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>

        {/* ===== 浮动导航面板（悬停展开当前分组全链接） ===== */}
        <AnimatePresence>
          {navPanelOpen && (
            <>
              {/* 点击遮罩区关闭面板（不可用 onMouseEnter — 鼠标从顶栏移向面板途中会误触关闭） */}
              <div
                className="fixed inset-0 z-30"
                onClick={() => setNavPanelOpen(false)}
              />
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                onMouseLeave={() => setNavPanelOpen(false)}
                className="absolute left-0 right-0 top-16 z-40 border-b border-[rgba(201,169,97,0.18)] bg-[rgba(22,17,13,0.97)] backdrop-blur-xl"
              >
                <div className="mx-auto max-w-[1600px] px-4 py-6 md:px-8">
                  <div className="mb-4 flex items-center gap-3">
                    <span className="font-mono text-[10px] tracking-[0.25em] text-[rgba(201,169,97,0.72)] uppercase">{currentGroup.title}</span>
                    <span className="h-px flex-1 bg-gradient-to-r from-[rgba(201,169,97,0.25)] to-transparent" />
                    <span className="font-mono text-[10px] text-[rgba(232,228,220,0.62)]">{currentGroup.items.length} 模块</span>
                  </div>
                  {/* 网格导航 — 暖金卡片 */}
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
                    {currentGroup.items.map(item => (
                      <NavLink
                        key={item.to}
                        to={item.to}
                        className={({ isActive }) =>
                          `group flex items-center gap-3 rounded-lg border px-3 py-2.5 transition-all ${
                            isActive
                              ? 'border-[rgba(201,169,97,0.5)] bg-black'
                              : 'border-[rgba(201,169,97,0.15)] bg-black/70 hover:border-[rgba(201,169,97,0.35)] hover:bg-black'
                          }`
                        }
                      >
                        <i className={`fas ${item.icon} w-4 text-center text-[13px] text-[#C9A961] transition-transform duration-200 group-hover:scale-110`} />
                        <span className="truncate text-sm text-[#E8E4DC]">{item.label}</span>
                      </NavLink>
                    ))}
                  </div>
                </div>
              </motion.div>
            </>
          )}
        </AnimatePresence>
      </header>

      {/* ===== 主内容区 ===== */}
      <main id="main-content" className="relative z-10 mx-auto max-w-[1600px] p-4 md:p-8">
        {children || <Outlet />}
      </main>

      {/* ===== 页脚状态条 ===== */}
      <footer className="relative z-10 border-t border-[rgba(201,169,97,0.12)] bg-[rgba(22,17,13,0.6)] py-3">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between px-4 font-mono text-[10px] text-[rgba(232,228,220,0.62)] md:px-8">
          <span><i className="fas fa-atom mr-1.5 text-[rgba(201,169,97,0.72)]" />墨观 · 学术天文台 · 高等教育科研效率提升系统</span>
          <span>© 2026 Moguan Observatory · Built with Ascend NPU</span>
        </div>
      </footer>
    </div>
  );
}


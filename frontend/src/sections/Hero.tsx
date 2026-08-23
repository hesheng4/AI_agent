import { motion } from 'motion/react';
import { lazy, Suspense } from 'react';
import DecryptedText from '../components/DecryptedText';
import BlurText from '../components/BlurText';
import Dock, { type DockItemData } from '../components/Dock';
import CountUp from '../components/CountUp';

// P1-O4: Aurora WebGL 重组件懒加载，仅 Hero 渲染时才下载
const Aurora = lazy(() => import('../components/Aurora'));

// 暖金极光色标 — 深金 → 暖金 → 浅金，柔和天文台氛围
const AURORA_STOPS = ['#9A7E45', '#C9A961', '#E0C896'];

const NAV_ITEMS: DockItemData[] = [
  {
    icon: <i className="fas fa-book-open text-lg text-[#E0C896]" />,
    label: '文献检索',
    onClick: () => {},
  },
  {
    icon: <i className="fas fa-flask text-lg text-[#E0C896]" />,
    label: '实验设计',
    onClick: () => {},
  },
  {
    icon: <i className="fas fa-chart-line text-lg text-[#E0C896]" />,
    label: '数据分析',
    onClick: () => {},
  },
  {
    icon: <i className="fas fa-pen-fancy text-lg text-[#E0C896]" />,
    label: '论文写作',
    onClick: () => {},
  },
  {
    icon: <i className="fas fa-quote-right text-lg text-[#E0C896]" />,
    label: '引用管理',
    onClick: () => {},
  },
];

// 特性卡片数据
const FEATURES = [
  {
    icon: 'fa-search',
    title: '智能文献检索',
    desc: '多源聚合 Semantic Scholar / arXiv / Crossref，AI 辅助筛选与摘要',
    accent: 'gold',
  },
  {
    icon: 'fa-project-diagram',
    title: '引用图谱分析',
    desc: '构建引用网络，识别 influential papers 与 co-citation 簇',
    accent: 'gold',
  },
  {
    icon: 'fa-flask',
    title: '实验设计辅助',
    desc: 'AI 生成实验方案，统计功效分析，自动样本量估算',
    accent: 'gold',
  },
  {
    icon: 'fa-chart-line',
    title: '数据可视化',
    desc: '上传数据自动分析，生成出版级图表与统计报告',
    accent: 'gold',
  },
  {
    icon: 'fa-pen-fancy',
    title: '论文写作工坊',
    desc: '大纲生成、段落润色、学术规范检查，一站式写作',
    accent: 'gold',
  },
  {
    icon: 'fa-microchip',
    title: '昇腾 NPU 工作台',
    desc: '精度对齐、性能采集、模型量化、调试辅助全流程',
    accent: 'gold',
  },
] as const;

const STATS = [
  { value: 5, suffix: '+', label: '智能 Agent', icon: 'fa-robot' },
  { value: 136, suffix: '+', label: '引用网络分析', icon: 'fa-project-diagram' },
  { value: 8, suffix: '', label: '昇腾模块', icon: 'fa-microchip' },
  { value: 6, suffix: '', label: '导出格式', icon: 'fa-file-export' },
];

export default function Hero() {
  return (
    <div className="relative min-h-screen bg-[#16110D]">
      {/* ===== Hero 主视觉 ===== */}
      <section
        className="wg-grain relative flex min-h-screen flex-col items-center justify-center overflow-hidden pb-52 pt-20"
        style={{
          // 柔和径向渐变 — 中心浅暖棕向四周过渡深炭黑，杜绝纯黑
          background:
            'radial-gradient(ellipse 85% 75% at 50% 42%, #2C2218 0%, #241C14 32%, #1C1610 62%, #16110D 100%)',
        }}
      >
        {/* Aurora 极光背景 — 暖金低透明，柔和不压抑 */}
        <div className="absolute inset-0 z-0 opacity-30">
          <Suspense fallback={null}>
            <Aurora colorStops={AURORA_STOPS} amplitude={1.0} blend={0.4} speed={0.6} />
          </Suspense>
        </div>

        {/* 星点装饰 — 暖金天文台主题 */}
        <div
          className="absolute inset-0 z-0 opacity-40"
          style={{
            backgroundImage: `radial-gradient(1px 1px at 8% 18%, rgba(201,169,97,0.5), transparent),
              radial-gradient(1px 1px at 25% 62%, rgba(201,169,97,0.35), transparent),
              radial-gradient(1px 1px at 50% 12%, rgba(201,169,97,0.3), transparent),
              radial-gradient(1px 1px at 72% 78%, rgba(201,169,97,0.4), transparent),
              radial-gradient(1px 1px at 88% 35%, rgba(224,200,150,0.25), transparent),
              radial-gradient(1px 1px at 42% 88%, rgba(201,169,97,0.35), transparent),
              radial-gradient(1px 1px at 95% 8%, rgba(201,169,97,0.3), transparent),
              radial-gradient(1px 1px at 18% 48%, rgba(201,169,97,0.4), transparent),
              radial-gradient(1.5px 1.5px at 35% 30%, rgba(224,200,150,0.6), transparent),
              radial-gradient(1px 1px at 62% 55%, rgba(201,169,97,0.3), transparent)`,
          }}
        />

        {/* 浮动暖金光球 — 增加深度 */}
        <div
          className="absolute left-[8%] top-[12%] z-0 h-72 w-72 rounded-full opacity-15 animate-float-orb"
          style={{ background: 'radial-gradient(circle, rgba(201,169,97,0.35), transparent 70%)' }}
        />
        <div
          className="absolute bottom-[8%] right-[6%] z-0 h-96 w-96 rounded-full opacity-10 animate-float-orb"
          style={{
            background: 'radial-gradient(circle, rgba(224,200,150,0.3), transparent 70%)',
            animationDelay: '4s',
          }}
        />

        {/* 主内容区 */}
        <div className="relative z-10 flex flex-col items-center px-6 text-center">
          {/* 顶部徽章 — 缩小弱化，细浅金半透圆角边框 */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
            className="mb-8 flex items-center gap-2.5 rounded-full border border-[rgba(201,169,97,0.22)] bg-[rgba(24,18,12,0.4)] px-4 py-1.5 backdrop-blur-md"
          >
            <i className="fas fa-atom text-[10px] text-[#C9A961]" />
            <span className="font-mono text-[10px] tracking-[0.22em] text-[rgba(224,200,150,0.6)] uppercase">
              高等教育科研效率提升系统
            </span>
          </motion.div>

          {/* 主标题 — 字号放大、字间距拉开、加粗，视觉核心 */}
          <h1 className="mb-6 font-serif text-6xl font-bold tracking-[0.18em] text-[#E0C896] sm:text-7xl md:text-8xl">
            <DecryptedText
              text="墨观"
              animateOn="view"
              speed={60}
              maxIterations={12}
              sequential
              revealDirection="center"
              className="wg-gradient"
              encryptedClassName="text-[rgba(201,169,97,0.35)]"
            />
            <span className="mx-4 text-[rgba(201,169,97,0.4)]">·</span>
            <DecryptedText
              text="学术天文台"
              animateOn="view"
              speed={50}
              maxIterations={12}
              sequential
              revealDirection="center"
              className="wg-gradient"
              encryptedClassName="text-[rgba(201,169,97,0.35)]"
            />
          </h1>

          {/* 副标题 — 降低亮度、字号缩小，与主标题拉开层级 */}
          <div className="mb-10 max-w-2xl">
            <BlurText
              text="文献检索 · 笔记收藏 · 引用图谱 · 实验设计 · 数据分析 · 论文写作 — 一站式科研协作平台"
              animateBy="words"
              direction="bottom"
              delay={80}
              stepDuration={0.4}
              className="justify-center text-sm text-[rgba(232,228,220,0.42)] sm:text-base"
            />
          </div>

          {/* CTA 按钮 — 统一磨砂玻璃质感 + 渐变高光边框 */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 1.2, ease: [0.16, 1, 0.3, 1] }}
            className="mb-12 flex flex-col items-center gap-4 sm:flex-row"
          >
            <a href="/login" className="wg-btn px-7 py-3.5 text-sm font-medium">
              <span className="flex items-center gap-2 font-sans">
                <i className="fas fa-rocket text-sm" />
                开始探索
              </span>
            </a>

            <a
              href="#features"
              className="wg-btn px-7 py-3.5 text-sm font-medium"
            >
              <span className="flex items-center gap-2 font-sans">
                <i className="fas fa-circle-info text-sm" />
                了解更多
              </span>
            </a>
          </motion.div>

          {/* 数据统计 — 独立小型卡片，均分两列，放大数字，悬浮阴影 */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 1, delay: 1.8 }}
            className="grid w-full max-w-xl grid-cols-2 gap-4 sm:gap-5"
          >
            {STATS.map((stat, i) => (
              <motion.div
                key={stat.label}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 2 + i * 0.1 }}
                className="flex flex-col items-center rounded-xl border border-[rgba(201,169,97,0.18)] bg-[rgba(30,23,16,0.55)] px-4 py-4 shadow-lg shadow-black/20 backdrop-blur-md transition-colors duration-300 hover:border-[rgba(224,200,150,0.35)]"
              >
                <i className={`fas ${stat.icon} mb-2 text-base text-[#C9A961]`} />
                <div className="font-serif text-3xl wg-gradient sm:text-4xl">
                  <CountUp to={stat.value} suffix={stat.suffix} duration={2} />
                </div>
                <div className="mt-1.5 font-mono text-[11px] tracking-wider text-[rgba(224,200,150,0.5)] uppercase">
                  {stat.label}
                </div>
              </motion.div>
            ))}
          </motion.div>
        </div>

        {/* Dock 导航 — 底部放大栏（暖金主题，容器半透深色底色） */}
        <div className="absolute bottom-0 left-0 z-20 h-[140px] w-full">
          <Dock
            items={NAV_ITEMS}
            magnification={64}
            baseItemSize={44}
            distance={180}
            panelHeight={56}
          />
        </div>

        {/* 底部渐变遮罩 — 让 Dock 融入背景 */}
        <div className="pointer-events-none absolute bottom-0 left-0 z-10 h-32 w-full bg-gradient-to-t from-[#16110D] to-transparent" />
      </section>

      {/* ===== Features 特性区 ===== */}
      <section id="features" className="relative overflow-hidden px-6 py-24 sm:py-32" style={{ background: '#16110D' }}>
        {/* 背景装饰 — 暖金 */}
        <div
          className="pointer-events-none absolute inset-0 opacity-30"
          style={{
            background:
              'radial-gradient(ellipse at 20% 0%, rgba(201,169,97,0.08), transparent 50%), radial-gradient(ellipse at 80% 100%, rgba(154,126,69,0.06), transparent 50%)',
          }}
        />

        <div className="relative mx-auto max-w-6xl">
          {/* 区块标题 */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-100px' }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
            className="mb-16 text-center"
          >
            <span className="mb-4 inline-flex items-center gap-2 rounded-full border border-[rgba(201,169,97,0.22)] bg-[rgba(201,169,97,0.05)] px-4 py-1.5 font-mono text-xs tracking-wider text-[rgba(224,200,150,0.7)] uppercase">
              <i className="fas fa-star" />
              核心能力
            </span>
            <h2 className="font-serif text-3xl text-[#E8E4DC] sm:text-4xl md:text-5xl">
              从<span className="wg-gradient"> 文献发现 </span>
              到<span className="wg-gradient"> 论文发表 </span>
              的全链路
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-sm text-[rgba(232,228,220,0.45)] sm:text-base">
              六大智能模块覆盖科研全生命周期，配合昇腾 NPU 本地推理，让研究效率提升 10 倍
            </p>
          </motion.div>

          {/* 特性网格 */}
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((feature, i) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-50px' }}
                transition={{ duration: 0.6, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] }}
                className="group relative overflow-hidden rounded-xl border border-[rgba(201,169,97,0.12)] bg-[rgba(26,20,14,0.55)] p-6 backdrop-blur-md transition-all duration-300 hover:border-[rgba(224,200,150,0.3)] hover:bg-[rgba(30,23,16,0.7)]"
              >
                {/* 悬停光晕 */}
                <div className="pointer-events-none absolute -right-12 -top-12 h-32 w-32 rounded-full bg-[rgba(201,169,97,0.08)] opacity-0 blur-2xl transition-opacity duration-500 group-hover:opacity-100" />

                {/* 图标 */}
                <div className="relative mb-4 flex h-12 w-12 items-center justify-center rounded-lg border border-[rgba(201,169,97,0.22)] bg-[rgba(201,169,97,0.06)] text-[#C9A961]">
                  <i className={`fas ${feature.icon} text-lg`} />
                </div>

                {/* 标题与描述 */}
                <h3 className="relative mb-2 font-serif text-lg text-[#E8E4DC]">{feature.title}</h3>
                <p className="relative text-sm leading-relaxed text-[rgba(232,228,220,0.5)]">{feature.desc}</p>

                {/* 底部装饰线 */}
                <div className="relative mt-4 h-px w-full bg-gradient-to-r from-[rgba(201,169,97,0.22)] via-[rgba(201,169,97,0.05)] to-transparent" />
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ===== Workflow 工作流区 ===== */}
      <section className="relative overflow-hidden px-6 py-24 sm:py-32" style={{ background: '#16110D' }}>
        <div className="relative mx-auto max-w-5xl">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-100px' }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
            className="mb-16 text-center"
          >
            <span className="mb-4 inline-flex items-center gap-2 rounded-full border border-[rgba(201,169,97,0.22)] bg-[rgba(201,169,97,0.05)] px-4 py-1.5 font-mono text-xs tracking-wider text-[rgba(224,200,150,0.7)] uppercase">
              <i className="fas fa-route" />
              科研工作流
            </span>
            <h2 className="font-serif text-3xl text-[#E8E4DC] sm:text-4xl md:text-5xl">
              五步完成一次<span className="wg-gradient">完整研究</span>
            </h2>
          </motion.div>

          <div className="grid gap-6 md:grid-cols-5">
            {[
              { step: '01', icon: 'fa-search', title: '检索', desc: '多源文献聚合' },
              { step: '02', icon: 'fa-bookmark', title: '收藏', desc: '分类标签管理' },
              { step: '03', icon: 'fa-project-diagram', title: '分析', desc: '引用图谱洞察' },
              { step: '04', icon: 'fa-flask', title: '实验', desc: '设计验证假设' },
              { step: '05', icon: 'fa-pen-fancy', title: '写作', desc: '论文成稿发表' },
            ].map((item, i) => (
              <motion.div
                key={item.step}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-50px' }}
                transition={{ duration: 0.6, delay: i * 0.1, ease: [0.16, 1, 0.3, 1] }}
                className="relative text-center"
              >
                {/* 连接线（除最后一个） */}
                {i < 4 && (
                  <div className="absolute left-[60%] top-8 hidden h-px w-[80%] bg-gradient-to-r from-[rgba(201,169,97,0.3)] to-transparent md:block" />
                )}

                <div className="relative mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full border border-[rgba(201,169,97,0.3)] bg-[rgba(26,20,14,0.6)] backdrop-blur-md">
                  <i className={`fas ${item.icon} text-xl text-[#E0C896]`} />
                  <span className="absolute -right-2 -top-2 flex h-6 w-6 items-center justify-center rounded-full bg-[#C9A961] text-[10px] font-bold text-[#16110D]">
                    {item.step}
                  </span>
                </div>
                <h3 className="font-serif text-base text-[#E8E4DC]">{item.title}</h3>
                <p className="mt-1 text-xs text-[rgba(232,228,220,0.4)]">{item.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ===== CTA 行动召唤 ===== */}
      <section className="relative overflow-hidden px-6 py-24 sm:py-32" style={{ background: '#16110D' }}>
        <div className="relative mx-auto max-w-3xl">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true, margin: '-100px' }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
            className="relative overflow-hidden rounded-2xl border border-[rgba(201,169,97,0.22)] bg-gradient-to-br from-[rgba(26,20,14,0.8)] to-[rgba(20,15,10,0.8)] p-12 text-center backdrop-blur-md"
          >
            {/* 背景光晕 */}
            <div className="pointer-events-none absolute inset-0 opacity-30">
              <div className="absolute left-1/2 top-0 h-40 w-40 -translate-x-1/2 rounded-full bg-[rgba(201,169,97,0.2)] blur-3xl" />
            </div>

            <div className="relative">
              <h2 className="mb-4 font-serif text-3xl text-[#E8E4DC] sm:text-4xl">
                准备好开启<span className="wg-gradient">科研新范式</span>了吗？
              </h2>
              <p className="mx-auto mb-8 max-w-xl text-sm text-[rgba(232,228,220,0.5)] sm:text-base">
                免费注册即可体验全部功能，昇腾 NPU 本地推理，数据安全可控
              </p>
              <a href="/login" className="wg-btn px-7 py-3.5 text-sm font-medium">
                <span className="flex items-center gap-2 font-sans">
                  <i className="fas fa-rocket text-sm" />
                  立即开始
                </span>
              </a>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ===== Footer 页脚 ===== */}
      <footer className="border-t border-[rgba(201,169,97,0.1)] px-6 py-12" style={{ background: '#16110D' }}>
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 sm:flex-row">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[rgba(201,169,97,0.1)]">
              <i className="fas fa-atom text-sm text-[#C9A961]" />
            </div>
            <div>
              <div className="font-serif text-sm wg-gradient">墨观 · 学术天文台</div>
              <div className="text-[10px] text-[rgba(232,228,220,0.3)]">高等教育科研效率提升系统</div>
            </div>
          </div>
          <div className="font-mono text-xs text-[rgba(232,228,220,0.3)]">
            © 2026 Moguan Observatory · Built with Ascend NPU
          </div>
        </div>
      </footer>
    </div>
  );
}

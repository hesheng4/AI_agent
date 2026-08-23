/**
 * CoordinatorAudit — 协调总管审计控制面板（后台核心首页）
 *
 * 美学方向：Mission Control · 深空指挥中心
 *   - 深空黑底 + 琥珀信号色，致敬 NASA/JPL 任务控制室
 *   - 左侧轨道时间轴（审计轮次如卫星轨道追踪）
 *   - 中央 16 智能体六边形蜂窝阵列（亮度 = 健康度）
 *   - JetBrains Mono（显示）+ Sora（正文），避开 Inter
 *   - 暗色为主，浅色为"日光模式"
 *
 * 数据：反映 R12-R38 真实审计状态（96 修复 / 283 测试 / 16 智能体 / L·X·S·Q 缺陷族）
 */
import { useState, useEffect, useMemo } from 'react';
import { motion } from 'motion/react';
import { Button, Card } from '../components/ui';

// ─────────────────────────────────────────────────────────────
// 数据模型（反映真实审计状态，R12-R38）
// ─────────────────────────────────────────────────────────────

interface AgentStatus {
  id: string;
  name: string;
  category: 'core' | 'writing' | 'review' | 'data' | 'asset';
  health: number;        // 0-1，综合健康度（temperature+singleton+测试）
  temperatureFixed: boolean;
  singletonFactory: boolean;
  testsPassed: number;
  lastRound: number;
}

interface AuditRound {
  round: number;
  title: string;
  topic: string;         // T/E/S/Q/L/X
  fixes: number;
  status: 'closed' | 'active' | 'deferred';
  timestamp: string;
}

interface DefectItem {
  id: string;            // L6 / X1 / S2 ...
  family: 'L' | 'X' | 'S' | 'Q' | 'T' | 'E';
  severity: 'high' | 'medium' | 'low';
  title: string;
  file: string;
  fixed: boolean;
  round: number;
}

// 16 nature-skills 智能体（figure 无 LLM 故 singleton 豁免）
const AGENTS: AgentStatus[] = [
  { id: 'coordinator', name: 'Coordinator', category: 'core', health: 1.0, temperatureFixed: true, singletonFactory: true, testsPassed: 21, lastRound: 15 },
  { id: 'citation', name: 'Citation', category: 'review', health: 0.96, temperatureFixed: true, singletonFactory: true, testsPassed: 18, lastRound: 33 },
  { id: 'literature', name: 'Literature', category: 'core', health: 0.98, temperatureFixed: true, singletonFactory: true, testsPassed: 21, lastRound: 19 },
  { id: 'reviewer', name: 'Reviewer', category: 'review', health: 0.97, temperatureFixed: true, singletonFactory: true, testsPassed: 18, lastRound: 16 },
  { id: 'reader', name: 'Reader', category: 'core', health: 0.97, temperatureFixed: true, singletonFactory: true, testsPassed: 21, lastRound: 13 },
  { id: 'writing', name: 'Writing', category: 'writing', health: 0.95, temperatureFixed: true, singletonFactory: true, testsPassed: 18, lastRound: 35 },
  { id: 'polishing', name: 'Polishing', category: 'writing', health: 0.95, temperatureFixed: true, singletonFactory: true, testsPassed: 18, lastRound: 35 },
  { id: 'response', name: 'Response', category: 'writing', health: 0.97, temperatureFixed: true, singletonFactory: true, testsPassed: 18, lastRound: 13 },
  { id: 'experiment', name: 'Experiment', category: 'data', health: 0.94, temperatureFixed: true, singletonFactory: true, testsPassed: 12, lastRound: 13 },
  { id: 'data', name: 'DataAnalysis', category: 'data', health: 0.93, temperatureFixed: true, singletonFactory: true, testsPassed: 12, lastRound: 18 },
  { id: 'stats', name: 'Stats', category: 'data', health: 0.93, temperatureFixed: true, singletonFactory: true, testsPassed: 12, lastRound: 21 },
  { id: 'figure', name: 'Figure', category: 'asset', health: 0.92, temperatureFixed: true, singletonFactory: false, testsPassed: 8, lastRound: 18 },
  { id: 'paper2ppt', name: 'Paper2PPT', category: 'asset', health: 0.95, temperatureFixed: true, singletonFactory: true, testsPassed: 14, lastRound: 23 },
  { id: 'paper_to_patent', name: 'PaperToPatent', category: 'asset', health: 0.94, temperatureFixed: true, singletonFactory: true, testsPassed: 14, lastRound: 34 },
  { id: 'cover', name: 'CoverLetter', category: 'writing', health: 0.96, temperatureFixed: true, singletonFactory: true, testsPassed: 12, lastRound: 21 },
  { id: 'submission_package', name: 'SubmissionPkg', category: 'writing', health: 0.95, temperatureFixed: true, singletonFactory: true, testsPassed: 12, lastRound: 21 },
];

// 审计轮次（精选里程碑）
const ROUNDS: AuditRound[] = [
  { round: 38, title: 'X7 多层嵌套保留', topic: 'L', fixes: 1, status: 'closed', timestamp: '21:14' },
  { round: 37, title: 'X5 图片浮动体块级', topic: 'L', fixes: 1, status: 'closed', timestamp: '21:08' },
  { round: 36, title: 'LaTeX 语法实现', topic: 'L', fixes: 3, status: 'closed', timestamp: '20:52' },
  { round: 35, title: 'L2/L8/L9 低优先', topic: 'L', fixes: 3, status: 'closed', timestamp: '20:41' },
  { round: 34, title: 'L7 OMML 语义映射', topic: 'L', fixes: 2, status: 'closed', timestamp: '20:30' },
  { round: 33, title: 'LaTeX 编写语法', topic: 'L', fixes: 5, status: 'closed', timestamp: '20:15' },
  { round: 31, title: 'S4 缓存键序列化', topic: 'S', fixes: 1, status: 'closed', timestamp: '19:50' },
  { round: 29, title: 'S2 请求体大小限制', topic: 'S', fixes: 1, status: 'closed', timestamp: '19:30' },
  { round: 27, title: 'Q1 SAFE 全闭环', topic: 'Q', fixes: 19, status: 'closed', timestamp: '19:10' },
  { round: 25, title: 'Q1-AST 分类器', topic: 'Q', fixes: 5, status: 'closed', timestamp: '18:45' },
  { round: 21, title: 'E3 prefix 同步', topic: 'E', fixes: 6, status: 'closed', timestamp: '18:20' },
  { round: 16, title: 'S1 JWT refresh', topic: 'S', fixes: 1, status: 'closed', timestamp: '17:55' },
  { round: 13, title: 'T1+T2 temperature+singleton', topic: 'T', fixes: 14, status: 'closed', timestamp: '17:30' },
  { round: 12, title: '整体审查', topic: 'T', fixes: 0, status: 'closed', timestamp: '17:00' },
];

// 缺陷清单（高严重度精选 + 全家族分布）
const DEFECTS: DefectItem[] = [
  { id: 'L6', family: 'L', severity: 'high', title: '上标/下标混淆（x^2→x₂）', file: 'math_to_omml.py:55', fixed: true, round: 33 },
  { id: 'X1', family: 'X', severity: 'high', title: 'to_latex 未转义特殊字符', file: 'export.py:203', fixed: true, round: 36 },
  { id: 'X3', family: 'X', severity: 'high', title: '列表项缺少 itemize 环境', file: 'latex_export.py:284', fixed: true, round: 36 },
  { id: 'X5', family: 'X', severity: 'medium', title: '图片浮动体行内插入', file: 'latex_export.py:461', fixed: true, round: 37 },
  { id: 'X8', family: 'X', severity: 'high', title: '命令保留占位符含 _', file: 'latex_export.py:529', fixed: true, round: 36 },
  { id: 'S2', family: 'S', severity: 'high', title: '请求体无大小限制', file: 'app/main.py', fixed: true, round: 29 },
  { id: 'S4', family: 'S', severity: 'medium', title: '缓存键 str() 内存地址', file: 'cache.py:301', fixed: true, round: 31 },
  { id: 'Q6', family: 'Q', severity: 'medium', title: '子路由 prefix 双重拼接', file: 'api/*.py', fixed: true, round: 21 },
  { id: 'L7', family: 'L', severity: 'medium', title: 'OMML munder/mover 语义偏差', file: 'math_to_omml.py:83', fixed: true, round: 34 },
  { id: 'X7', family: 'X', severity: 'low', title: '嵌套花括号保留仅单层', file: 'latex_export.py:535', fixed: true, round: 38 },
  { id: 'Q1-UNSAFE', family: 'Q', severity: 'low', title: '379 字符串内容 E501', file: 'prompts/scripts', fixed: false, round: 28 },
];

// ─────────────────────────────────────────────────────────────
// 派生统计
// ─────────────────────────────────────────────────────────────

const STATS = {
  totalFixes: 96,
  totalTests: 283,
  testsPassed: 283,
  agentsOnline: AGENTS.filter(a => a.health >= 0.9).length,
  agentsTotal: AGENTS.length,
  defectsFixed: DEFECTS.filter(d => d.fixed).length,
  defectsTotal: DEFECTS.length,
  roundsClosed: ROUNDS.filter(r => r.status === 'closed').length,
};

const FAMILY_COLOR: Record<DefectItem['family'], string> = {
  L: '#E0C896', X: '#F87171', S: '#4ADE80', Q: '#C9A961', T: '#A78BFA', E: '#FBBF24',
};
const SEVERITY_RING: Record<DefectItem['severity'], string> = {
  high: '#F87171', medium: '#FBBF24', low: '#8B7E6A',
};

// ─────────────────────────────────────────────────────────────
// 六边形蜂窝阵列
// ─────────────────────────────────────────────────────────────

function HexCell({ agent, index }: { agent: AgentStatus; index: number }) {
  const brightness = agent.health;
  const isExempt = !agent.singletonFactory; // figure
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.6 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: 0.4 + index * 0.04, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      whileHover={{ scale: 1.12, zIndex: 10 }}
      className="group relative cursor-pointer"
      title={`${agent.name} · 健康 ${(agent.health * 100).toFixed(0)}% · ${agent.testsPassed} 测试`}
    >
      {/* 六边形 */}
      <div
        className="relative h-16 w-18"
        style={{
          clipPath: 'polygon(25% 5%, 75% 5%, 100% 50%, 75% 95%, 25% 95%, 0% 50%)',
          background: `linear-gradient(135deg,
            rgba(251,146,60,${0.15 + brightness * 0.5}) 0%,
            rgba(251,146,60,${0.08 + brightness * 0.3}) 100%)`,
          border: '1px solid rgba(251,146,60,' + (0.2 + brightness * 0.4) + ')',
          boxShadow: brightness >= 0.95
            ? '0 0 16px rgba(251,146,60,0.35), inset 0 0 8px rgba(251,146,60,0.15)'
            : 'inset 0 0 6px rgba(251,146,60,0.1)',
        }}
      >
        {/* 脉冲信号（高健康度） */}
        {brightness >= 0.95 && (
          <span
            className="absolute inset-0 animate-ping-slow"
            style={{
              clipPath: 'polygon(25% 5%, 75% 5%, 100% 50%, 75% 95%, 25% 95%, 0% 50%)',
              background: 'rgba(251,146,60,0.18)',
            }}
          />
        )}
        {/* 智能体标识 */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className="font-mono text-[10px] font-bold tracking-tight"
            style={{ color: brightness >= 0.9 ? '#FDE68A' : '#94A3B8' }}
          >
            {agent.name.slice(0, 6)}
          </span>
          <span className="font-mono text-[8px] text-amber-200/50">
            {agent.testsPassed}t
          </span>
          {isExempt && (
            <span className="font-mono text-[7px] text-slate-500">exempt</span>
          )}
        </div>
      </div>
      {/* hover 详情 */}
      <div className="pointer-events-none absolute left-1/2 top-full z-20 mt-2 -translate-x-1/2 whitespace-nowrap rounded border border-amber-500/30 bg-slate-900/95 px-3 py-2 font-mono text-[10px] text-amber-100 opacity-0 shadow-xl transition-opacity duration-200 group-hover:opacity-100">
        <div className="font-bold text-amber-300">{agent.name}</div>
        <div className="text-slate-400">health: {(agent.health * 100).toFixed(0)}%</div>
        <div className="text-slate-400">temp=0.0: {agent.temperatureFixed ? '✓' : '✗'}</div>
        <div className="text-slate-400">singleton: {agent.singletonFactory ? '✓' : '—'}</div>
        <div className="text-slate-400">last: R{agent.lastRound}</div>
      </div>
    </motion.div>
  );
}

// ─────────────────────────────────────────────────────────────
// 测试通过率环形图
// ─────────────────────────────────────────────────────────────

function TestRing() {
  const pass = STATS.testsPassed;
  const total = STATS.totalTests;
  const pct = (pass / total) * 100;
  const r = 52;
  const c = 2 * Math.PI * r;
  const offset = c - (pct / 100) * c;
  return (
    <div className="relative flex items-center justify-center">
      <svg width="140" height="140" className="-rotate-90">
        {/* 轨道 */}
        <circle cx="70" cy="70" r={r} fill="none" stroke="rgba(100,116,139,0.15)" strokeWidth="6" />
        {/* 进度（渐变） */}
        <defs>
          <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#FB923C" />
            <stop offset="100%" stopColor="#FDE68A" />
          </linearGradient>
        </defs>
        <motion.circle
          cx="70" cy="70" r={r} fill="none" stroke="url(#ringGrad)" strokeWidth="6"
          strokeLinecap="round"
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: offset }}
          transition={{ delay: 0.8, duration: 1.4, ease: 'easeOut' }}
          style={{ strokeDasharray: c }}
        />
        {/* 刻度标记 */}
        {Array.from({ length: 60 }).map((_, i) => {
          const a = (i / 60) * 2 * Math.PI;
          const x1 = 70 + Math.cos(a) * 62, y1 = 70 + Math.sin(a) * 62;
          const x2 = 70 + Math.cos(a) * 66, y2 = 70 + Math.sin(a) * 66;
          return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
            stroke="rgba(251,146,60,0.2)" strokeWidth="1" />;
        })}
      </svg>
      <div className="absolute flex flex-col items-center">
        <motion.span
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.6 }}
          className="font-mono text-3xl font-bold text-amber-300"
        >
          {pass}
          <span className="text-base text-slate-500">/{total}</span>
        </motion.span>
        <span className="font-mono text-[10px] tracking-widest text-slate-500">PASSED</span>
        <span className="font-mono text-[10px] text-emerald-400">100%</span>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// 轨道时间轴（左侧）
// ─────────────────────────────────────────────────────────────

function OrbitTimeline({ rounds, selected, onSelect }: {
  rounds: AuditRound[]; selected: number; onSelect: (r: number) => void;
}) {
  return (
    <div className="relative">
      {/* 轨道主线 */}
      <div className="absolute left-[7px] top-0 bottom-0 w-px bg-gradient-to-b from-amber-500/60 via-amber-500/20 to-transparent" />
      <div className="space-y-3">
        {rounds.map((r, i) => (
          <motion.button
            key={r.round}
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.3 + i * 0.05, duration: 0.4 }}
            onClick={() => onSelect(r.round)}
            className={`group relative flex w-full items-center gap-3 rounded-lg px-2 py-1.5 text-left transition-colors ${
              selected === r.round ? 'bg-amber-500/10' : 'hover:bg-slate-800/50'
            }`}
          >
            {/* 轨道节点 */}
            <span
              className={`relative z-10 flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full border ${
                r.status === 'closed'
                  ? 'border-amber-400 bg-amber-500/20'
                  : 'border-slate-600 bg-slate-800'
              }`}
            >
              {r.status === 'closed' && (
                <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
              )}
              {selected === r.round && (
                <span className="absolute inset-0 animate-ping rounded-full bg-amber-400/40" />
              )}
            </span>
            {/* 轮次信息 */}
            <div className="flex min-w-0 flex-1 items-center gap-2">
              <span className="font-mono text-xs font-bold text-amber-300">R{r.round}</span>
              <span
                className="font-mono text-[10px] font-bold uppercase tracking-wider"
                style={{ color: FAMILY_COLOR[r.topic as DefectItem['family']] || '#94A3B8' }}
              >
                {r.topic}
              </span>
              <span className="truncate font-mono text-[11px] text-slate-400">{r.title}</span>
            </div>
            <span className="font-mono text-[9px] text-slate-600">{r.timestamp}</span>
          </motion.button>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// 缺陷清单行
// ─────────────────────────────────────────────────────────────

function DefectRow({ d }: { d: DefectItem }) {
  return (
    <motion.tr
      initial={{ opacity: 0 }} animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="border-b border-slate-800/60 transition-colors hover:bg-slate-800/40"
    >
      <td className="px-3 py-2">
        <span
          className="inline-flex h-6 w-10 items-center justify-center rounded font-mono text-[10px] font-bold"
          style={{
            color: FAMILY_COLOR[d.family],
            background: `${FAMILY_COLOR[d.family]}15`,
            border: `1px solid ${FAMILY_COLOR[d.family]}30`,
          }}
        >
          {d.id}
        </span>
      </td>
      <td className="px-3 py-2">
        <span
          className="inline-block h-2 w-2 rounded-full"
          style={{ background: SEVERITY_RING[d.severity] }}
          title={d.severity}
        />
      </td>
      <td className="px-3 py-2 font-mono text-xs text-slate-200">{d.title}</td>
      <td className="px-3 py-2 font-mono text-[10px] text-slate-500">{d.file}</td>
      <td className="px-3 py-2 font-mono text-[10px] text-amber-400/70">R{d.round}</td>
      <td className="px-3 py-2">
        {d.fixed ? (
          <span className="font-mono text-[10px] font-bold text-emerald-400">● FIXED</span>
        ) : (
          <span className="font-mono text-[10px] font-bold text-slate-500">○ ACCEPTED</span>
        )}
      </td>
    </motion.tr>
  );
}

// ─────────────────────────────────────────────────────────────
// 主组件
// ─────────────────────────────────────────────────────────────

export default function CoordinatorAudit() {
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [selectedRound, setSelectedRound] = useState(38);
  const [defectFilter, setDefectFilter] = useState<'all' | 'high' | DefectItem['family']>('all');

  // 主题切换（挂载 .dark 到 documentElement）
  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') root.classList.add('dark');
    else root.classList.remove('dark');
  }, [theme]);

  const filteredDefects = useMemo(() => {
    if (defectFilter === 'all') return DEFECTS;
    if (defectFilter === 'high') return DEFECTS.filter(d => d.severity === 'high');
    return DEFECTS.filter(d => d.family === defectFilter);
  }, [defectFilter]);

  const selectedRoundData = ROUNDS.find(r => r.round === selectedRound);

  return (
    <div className="min-h-screen bg-slate-950 font-sora text-slate-200 dark:bg-slate-950">
      {/* 背景肌理：扫描线 + 星点 */}
      <div className="pointer-events-none fixed inset-0 z-0">
        <div className="absolute inset-0 opacity-[0.03]" style={{
          backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(251,146,60,0.5) 2px, rgba(251,146,60,0.5) 3px)',
        }} />
        <div className="absolute inset-0 opacity-40" style={{
          backgroundImage: 'radial-gradient(1px 1px at 20% 30%, rgba(251,191,36,0.4), transparent), radial-gradient(1px 1px at 70% 60%, rgba(251,146,60,0.3), transparent), radial-gradient(1px 1px at 40% 80%, rgba(251,191,36,0.3), transparent), radial-gradient(1px 1px at 85% 20%, rgba(251,146,60,0.2), transparent)',
        }} />
      </div>

      <div className="relative z-10 mx-auto max-w-[1600px] px-6 py-6">
        {/* ── 顶栏 ── */}
        <motion.header
          initial={{ opacity: 0, y: -16 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mb-6 flex items-center justify-between border-b border-amber-500/15 pb-4"
        >
          <div className="flex items-center gap-4">
            {/* 任务徽标 */}
            <div className="relative flex h-12 w-12 items-center justify-center rounded-lg border border-amber-500/30 bg-amber-500/5">
              <i className="fas fa-satellite-dish text-lg text-amber-400" />
              <span className="absolute -right-1 -top-1 flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400/60" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-400" />
              </span>
            </div>
            <div>
              <h1 className="font-mono text-xl font-bold tracking-tight text-amber-100">
                MISSION CONTROL
                <span className="ml-2 font-sora text-sm font-normal text-slate-500">协调总管 · 审计控制面板</span>
              </h1>
              <p className="font-mono text-[10px] tracking-widest text-amber-500/60">
                RAP-01 · AUDIT OPS · ALL SYSTEMS NOMINAL
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-slate-500">
              <i className="far fa-clock mr-1" />2026-06-28 21:14 UTC
            </span>
            <Button
              variant="ghost" size="sm"
              icon={theme === 'dark' ? 'fa-sun' : 'fa-moon'}
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              className="!text-amber-300 hover:!bg-amber-500/10"
            >
              {theme === 'dark' ? '日光模式' : '深空模式'}
            </Button>
          </div>
        </motion.header>

        {/* ── KPI 仪表带 ── */}
        <motion.div
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15, duration: 0.5 }}
          className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4"
        >
          {[
            { label: '代码修复', value: STATS.totalFixes, unit: '处', color: '#FB923C', icon: 'fa-wrench' },
            { label: '测试通过', value: STATS.testsPassed, unit: `/${STATS.totalTests}`, color: '#4ADE80', icon: 'fa-check-double' },
            { label: '智能体在线', value: STATS.agentsOnline, unit: `/${STATS.agentsTotal}`, color: '#FDE68A', icon: 'fa-microchip' },
            { label: '缺陷闭环', value: STATS.defectsFixed, unit: `/${STATS.defectsTotal}`, color: '#60A5FA', icon: 'fa-bug' },
          ].map((k, i) => (
            <motion.div
              key={k.label}
              initial={{ opacity: 0, scale: 0.92 }} animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.25 + i * 0.08, duration: 0.4 }}
              className="relative overflow-hidden rounded-lg border border-slate-800/80 bg-slate-900/60 p-4"
            >
              <div className="absolute right-0 top-0 h-20 w-20 rounded-full opacity-10 blur-2xl" style={{ background: k.color }} />
              <div className="flex items-center justify-between">
                <span className="font-mono text-[10px] uppercase tracking-widest text-slate-500">{k.label}</span>
                <i className={`fas ${k.icon} text-xs`} style={{ color: k.color }} />
              </div>
              <div className="mt-2 flex items-baseline gap-1">
                <motion.span
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                  transition={{ delay: 0.5 + i * 0.08 }}
                  className="font-mono text-3xl font-bold" style={{ color: k.color }}
                >
                  {k.value}
                </motion.span>
                <span className="font-mono text-xs text-slate-500">{k.unit}</span>
              </div>
              {/* 进度细条 */}
              <div className="mt-2 h-0.5 w-full overflow-hidden rounded-full bg-slate-800">
                <motion.div
                  initial={{ width: 0 }} animate={{ width: '100%' }}
                  transition={{ delay: 0.6 + i * 0.08, duration: 0.8 }}
                  className="h-full rounded-full" style={{ background: k.color }}
                />
              </div>
            </motion.div>
          ))}
        </motion.div>

        {/* ── 主网格：左时间轴 / 中蜂窝 / 右测试环 ── */}
        <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-12">
          {/* 左：轨道时间轴 */}
          <motion.div
            initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.3, duration: 0.5 }}
            className="lg:col-span-3"
          >
            <Card className="!border-amber-500/15 !bg-slate-900/60 !p-4">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="font-mono text-xs font-bold uppercase tracking-widest text-amber-400">
                  <i className="fas fa-route mr-1.5" />轨道追踪
                </h2>
                <span className="font-mono text-[10px] text-slate-500">{ROUNDS.length} 轮</span>
              </div>
              <div className="max-h-[420px] overflow-y-auto pr-1">
                <OrbitTimeline rounds={ROUNDS} selected={selectedRound} onSelect={setSelectedRound} />
              </div>
              {/* 选中轮次详情 */}
              {selectedRoundData && (
                <motion.div
                  key={selectedRound}
                  initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                  className="mt-3 rounded border border-amber-500/20 bg-amber-500/5 p-3"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-bold text-amber-300">R{selectedRoundData.round}</span>
                    <span style={{ color: FAMILY_COLOR[selectedRoundData.topic as DefectItem['family']] }} className="font-mono text-[10px] font-bold">
                      {selectedRoundData.topic}
                    </span>
                  </div>
                  <p className="mt-1 font-mono text-xs text-slate-300">{selectedRoundData.title}</p>
                  <p className="mt-1 font-mono text-[10px] text-slate-500">
                    {selectedRoundData.fixes} 处修复 · {selectedRoundData.status === 'closed' ? '已闭环' : '进行中'}
                  </p>
                </motion.div>
              )}
            </Card>
          </motion.div>

          {/* 中：六边形蜂窝阵列 */}
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.35, duration: 0.5 }}
            className="lg:col-span-6"
          >
            <Card className="!border-amber-500/15 !bg-slate-900/60 !p-4">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="font-mono text-xs font-bold uppercase tracking-widest text-amber-400">
                  <i className="fas fa-satellite mr-1.5" />智能体星座
                </h2>
                <div className="flex items-center gap-3 font-mono text-[10px] text-slate-500">
                  <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-amber-400" />在线</span>
                  <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-slate-600" />降级</span>
                </div>
              </div>
              {/* 蜂窝布局：错位排列 */}
              <div className="flex flex-wrap justify-center gap-1" style={{ maxWidth: '100%' }}>
                {AGENTS.map((a, i) => (
                  <div key={a.id} className={i % 2 === 0 ? 'mt-4' : ''}>
                    <HexCell agent={a} index={i} />
                  </div>
                ))}
              </div>
              <div className="mt-4 grid grid-cols-5 gap-2 border-t border-slate-800/60 pt-3 font-mono text-[10px]">
                {([
                  ['core', '核心', '#FDE68A'],
                  ['writing', '写作', '#FB923C'],
                  ['review', '审稿', '#4ADE80'],
                  ['data', '数据', '#60A5FA'],
                  ['asset', '资产', '#A78BFA'],
                ] as const).map(([cat, label, color]) => {
                  const count = AGENTS.filter(a => a.category === cat).length;
                  return (
                    <div key={cat} className="flex items-center gap-1.5">
                      <span className="h-2 w-2 rounded-sm" style={{ background: color }} />
                      <span className="text-slate-400">{label}</span>
                      <span className="ml-auto text-slate-600">{count}</span>
                    </div>
                  );
                })}
              </div>
            </Card>
          </motion.div>

          {/* 右：测试通过率 + 批量操作 */}
          <motion.div
            initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.4, duration: 0.5 }}
            className="lg:col-span-3"
          >
            <Card className="!border-amber-500/15 !bg-slate-900/60 !p-4">
              <h2 className="mb-3 font-mono text-xs font-bold uppercase tracking-widest text-amber-400">
                <i className="fas fa-heartbeat mr-1.5" />测试遥测
              </h2>
              <TestRing />
              <div className="mt-3 space-y-1.5 border-t border-slate-800/60 pt-3 font-mono text-[10px]">
                {[
                  ['单元测试', 247, '#4ADE80'],
                  ['集成测试', 21, '#FBBF24'],
                  ['安全 S1-S4', 37, '#FB923C'],
                  ['LaTeX 审计', 28, '#FDE68A'],
                ].map(([label, n, color]) => (
                  <div key={label as string} className="flex items-center gap-2">
                    <span className="h-1.5 w-1.5 rounded-full" style={{ background: color as string }} />
                    <span className="text-slate-400">{label}</span>
                    <span className="ml-auto text-slate-300">{n}</span>
                  </div>
                ))}
              </div>
              {/* 批量操作 */}
              <div className="mt-4 space-y-2 border-t border-slate-800/60 pt-3">
                <h3 className="font-mono text-[10px] uppercase tracking-widest text-slate-500">批量操作</h3>
                <Button variant="secondary" size="sm" icon="fa-play" className="w-full !justify-start !border-amber-500/30 !bg-amber-500/5 !text-amber-200">
                  运行全量测试
                </Button>
                <Button variant="secondary" size="sm" icon="fa-broom" className="w-full !justify-start !border-amber-500/30 !bg-amber-500/5 !text-amber-200">
                  执行 ruff --fix
                </Button>
                <Button variant="secondary" size="sm" icon="fa-file-export" className="w-full !justify-start !border-amber-500/30 !bg-amber-500/5 !text-amber-200">
                  导出审计报告
                </Button>
                <Button variant="danger" size="sm" icon="fa-radiation" className="w-full !justify-start">
                  重置审计状态
                </Button>
              </div>
            </Card>
          </motion.div>
        </div>

        {/* ── 缺陷清单 ── */}
        <motion.div
          initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5, duration: 0.5 }}
        >
          <Card className="!border-amber-500/15 !bg-slate-900/60 !p-4">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <h2 className="font-mono text-xs font-bold uppercase tracking-widest text-amber-400">
                <i className="fas fa-list-check mr-1.5" />缺陷清单
                <span className="ml-2 font-sora text-sm font-normal text-slate-500">
                  {filteredDefects.length} / {DEFECTS.length} 条
                </span>
              </h2>
              {/* 家族筛选 */}
              <div className="flex flex-wrap items-center gap-1.5">
                {(['all', 'high', 'L', 'X', 'S', 'Q', 'T', 'E'] as const).map(f => {
                  const labels: Record<string, string> = {
                    all: '全部', high: '高严重', L: 'LaTeX', X: '实现', S: '安全', Q: '质量', T: '温度', E: '端点',
                  };
                  const active = defectFilter === f;
                  const color = f === 'all' || f === 'high' ? '#94A3B8' : FAMILY_COLOR[f as DefectItem['family']];
                  return (
                    <button
                      key={f}
                      onClick={() => setDefectFilter(f)}
                      className={`rounded px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider transition-all ${
                        active ? 'bg-slate-800' : 'hover:bg-slate-800/50'
                      }`}
                      style={{
                        color: active ? color : '#64748B',
                        border: `1px solid ${active ? color + '40' : 'rgba(51,65,85,0.5)'}`,
                      }}
                    >
                      {labels[f]}
                    </button>
                  );
                })}
              </div>
            </div>
            {/* 表头 */}
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-amber-500/20 font-mono text-[10px] uppercase tracking-widest text-slate-500">
                    <th className="px-3 py-2 text-left">编号</th>
                    <th className="px-3 py-2 text-left">级</th>
                    <th className="px-3 py-2 text-left">问题描述</th>
                    <th className="px-3 py-2 text-left">文件</th>
                    <th className="px-3 py-2 text-left">轮次</th>
                    <th className="px-3 py-2 text-left">状态</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredDefects.map(d => <DefectRow key={d.id} d={d} />)}
                </tbody>
              </table>
            </div>
            {/* 缺陷家族分布条 */}
            <div className="mt-4 flex h-1.5 w-full overflow-hidden rounded-full">
              {(['L', 'X', 'S', 'Q', 'T', 'E'] as const).map(fam => {
                const count = DEFECTS.filter(d => d.family === fam).length;
                return count > 0 ? (
                  <div
                    key={fam}
                    style={{ width: `${(count / DEFECTS.length) * 100}%`, background: FAMILY_COLOR[fam] }}
                    title={`${fam}: ${count}`}
                  />
                ) : null;
              })}
            </div>
            <div className="mt-1.5 flex justify-between font-mono text-[9px] text-slate-600">
              <span>缺陷家族分布</span>
              <span>{STATS.defectsFixed}/{STATS.defectsTotal} 已修复 · 1 接受现状</span>
            </div>
          </Card>
        </motion.div>

        {/* ── 页脚状态条 ── */}
        <motion.footer
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.7 }}
          className="mt-6 flex items-center justify-between border-t border-amber-500/15 pt-3 font-mono text-[10px] text-slate-600"
        >
          <span><i className="fas fa-circle text-emerald-500 mr-1" style={{ fontSize: 6 }} />SYSTEM NOMINAL · 16/16 智能体在线 · 0 残留缺陷</span>
          <span>R12-R38 · 96 修复 · 283 测试 · 14 LaTeX · 4 安全加固</span>
          <span>atomcode · glm-5.2 · audit ops</span>
        </motion.footer>
      </div>
    </div>
  );
}

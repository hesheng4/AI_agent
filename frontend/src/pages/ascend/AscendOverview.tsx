// 昇腾工作台总览 — 7 大功能模块卡片启动器，点击跳转对应子页
import { useNavigate } from 'react-router-dom';
import { motion } from 'motion/react';
import { PageHeader } from '../../components/ui';

interface AscendModule {
  to: string;
  icon: string;
  title: string;
  desc: string;
  tag: string;
}

// 8 个昇腾模块 — 与侧边栏一致（环境概览即本页，不再自引用）
const MODULES: AscendModule[] = [
  {
    to: '/app/adaptation',
    icon: 'fa-puzzle-piece',
    title: '模型适配',
    desc: '10 步 Playbook 将新模型适配到昇腾 NPU，算子兼容性门控与两阶段验证',
    tag: '基础',
  },
  {
    to: '/app/alignment',
    icon: 'fa-balance-scale',
    title: '精度对齐',
    desc: 'GPU 与 NPU 推理结果对比，余弦相似度与 KL 散度监测',
    tag: '验证',
  },
  {
    to: '/app/profiling',
    icon: 'fa-stopwatch',
    title: '性能采集',
    desc: 'msprofleprof 采集、ACL Graph 抓取、任务运行监控',
    tag: '分析',
  },
  {
    to: '/app/perf-tuning',
    icon: 'fa-gauge-high',
    title: '性能调优',
    desc: 'TCMalloc、NUMA 绑定、推荐配置与启动命令生成',
    tag: '优化',
  },
  {
    to: '/app/toolchain',
    icon: 'fa-toolbox',
    title: '推理工具链',
    desc: 'vLLM-Ascend 部署、模型量化、错误诊断与 AISBench 基准',
    tag: '部署',
  },
  {
    to: '/app/validator',
    icon: 'fa-check-double',
    title: '模型验证',
    desc: '部署命令、精度验证、性能基准与端到端测试',
    tag: '验证',
  },
  {
    to: '/app/debugging',
    icon: 'fa-bug',
    title: '调试辅助',
    desc: '错误快速诊断、调试会话管理与红旗检测',
    tag: '调试',
  },
  {
    to: '/app/history-to-skill',
    icon: 'fa-magic-wand-sparkles',
    title: '历史转技能',
    desc: '从调试历史提炼可复用技能，端到端搜索与生成',
    tag: 'AI',
  },
];

// 标签颜色映射
const TAG_COLORS: Record<string, string> = {
  基础: 'bg-copper/10 text-copper-light border-copper/20',
  验证: 'bg-jade/10 text-jade border-jade/20',
  分析: 'bg-indigo/10 text-indigo border-indigo/20',
  优化: 'bg-copper/10 text-copper-light border-copper/20',
  部署: 'bg-indigo/10 text-indigo border-indigo/20',
  调试: 'bg-vermillion/10 text-vermillion border-vermillion/20',
  AI: 'bg-jade/10 text-jade border-jade/20',
};

export default function AscendOverview() {
  const navigate = useNavigate();

  return (
    <div>
      <PageHeader
        title="昇腾工作台"
        subtitle="华为昇腾 NPU 全流程适配 · 8 大功能模块"
        icon="fa-microchip"
      />

      {/* 顶部说明条 */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="mb-6 flex items-center gap-3 rounded-xl border border-copper/10 bg-copper/[0.03] px-5 py-3"
      >
        <i className="fas fa-info-circle text-copper" />
        <p className="text-sm text-ink-bg/60">
          点击下方功能卡片进入对应模块。所有模块支持本地 NPU 推理，数据安全可控。
        </p>
      </motion.div>

      {/* 功能卡片网格 */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {MODULES.map((mod, i) => (
          <motion.button
            key={mod.to}
            onClick={() => navigate(mod.to)}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: i * 0.05, ease: [0.16, 1, 0.3, 1] }}
            whileHover={{ y: -4 }}
            className="group relative flex cursor-pointer flex-col items-start overflow-hidden rounded-xl border border-copper/10 bg-ink-dark/60 p-5 text-left backdrop-blur-md transition-colors duration-200 hover:border-copper/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-copper/40"
          >
            {/* 悬停光晕 */}
            <div className="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-copper/5 opacity-0 blur-2xl transition-opacity duration-500 group-hover:opacity-100" />

            {/* 图标 + 标签 */}
            <div className="relative mb-4 flex w-full items-center justify-between">
              <div className="flex h-11 w-11 items-center justify-center rounded-lg border border-copper/20 bg-copper/5 text-copper-light transition-transform duration-200 group-hover:scale-110">
                <i className={`fas ${mod.icon} text-lg`} />
              </div>
              <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${TAG_COLORS[mod.tag]}`}>
                {mod.tag}
              </span>
            </div>

            {/* 标题 */}
            <h3 className="relative mb-1.5 font-serif text-base text-ink-bg transition-colors group-hover:text-copper-light">
              {mod.title}
            </h3>

            {/* 描述 */}
            <p className="relative flex-1 text-xs leading-relaxed text-ink-bg/50">{mod.desc}</p>

            {/* 底部进入提示 */}
            <div className="relative mt-4 flex items-center gap-1.5 text-xs text-copper-light/60 transition-colors group-hover:text-copper-light">
              <span>进入模块</span>
              <i className="fas fa-arrow-right text-[10px] transition-transform duration-200 group-hover:translate-x-1" />
            </div>
          </motion.button>
        ))}
      </div>
    </div>
  );
}

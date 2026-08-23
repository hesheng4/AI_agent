// 全局命令面板 — Ctrl+K 触发，搜索页面+功能+文献
import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'motion/react';

function useFocusTrap(containerRef: React.RefObject<HTMLElement | null>, active: boolean) {
  useEffect(() => {
    if (!active || !containerRef.current) return;
    const el = containerRef.current;
    const focusable = el.querySelectorAll<HTMLElement>('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    function handler(e: KeyboardEvent) {
      if (e.key !== 'Tab') return;
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
    el.addEventListener('keydown', handler);
    return () => el.removeEventListener('keydown', handler);
  }, [active]);
}

interface CommandItem {
  id: string;
  label: string;
  icon: string;
  category: string;
  action: () => void;
}

const STATIC_COMMANDS: Omit<CommandItem, 'action'>[] = [
  { id: 'literature', label: '文献检索', icon: 'fa-search', category: '科研' },
  { id: 'reader', label: '论文精读', icon: 'fa-book-open', category: '科研' },
  { id: 'library', label: '文献库', icon: 'fa-bookmark', category: '科研' },
  { id: 'network', label: '引用网络', icon: 'fa-project-diagram', category: '科研' },
  { id: 'citation', label: '引用管理', icon: 'fa-quote-right', category: '科研' },
  { id: 'data', label: '数据分析', icon: 'fa-chart-line', category: '科研' },
  { id: 'writing', label: '论文写作', icon: 'fa-pen-fancy', category: '科研' },
  { id: 'reviewer', label: '模拟审稿', icon: 'fa-user-check', category: '科研' },
  { id: 'response', label: '审稿回复', icon: 'fa-reply', category: '科研' },
  { id: 'review-loop', label: '审稿迭代', icon: 'fa-rotate', category: '科研' },
  { id: 'experiment', label: '实验设计', icon: 'fa-flask', category: '科研' },
  { id: 'export', label: '数据导出', icon: 'fa-download', category: '科研' },
  { id: 'coordinator', label: '智能路由', icon: 'fa-route', category: '系统' },
  { id: 'profile', label: '个人中心', icon: 'fa-user-circle', category: '系统' },
  { id: 'ascend', label: '昇腾环境概览', icon: 'fa-microchip', category: '昇腾' },
  { id: 'adaptation', label: '模型适配', icon: 'fa-puzzle-piece', category: '昇腾' },
  { id: 'alignment', label: '精度对齐', icon: 'fa-balance-scale', category: '昇腾' },
  { id: 'profiling', label: '性能采集', icon: 'fa-stopwatch', category: '昇腾' },
  { id: 'perf-tuning', label: '性能调优', icon: 'fa-gauge-high', category: '昇腾' },
  { id: 'toolchain', label: '推理工具链', icon: 'fa-toolbox', category: '昇腾' },
  { id: 'validator', label: '模型验证', icon: 'fa-check-double', category: '昇腾' },
  { id: 'debugging', label: '调试辅助', icon: 'fa-bug', category: '昇腾' },
  { id: 'history-to-skill', label: '历史转技能', icon: 'fa-magic-wand-sparkles', category: '昇腾' },
  { id: 'figure', label: '图表合同', icon: 'fa-chart-column', category: '科研' },
  { id: 'cover', label: 'Cover Letter', icon: 'fa-envelope', category: '科研' },
  { id: 'methods', label: '方法论', icon: 'fa-microscope', category: '科研' },
  { id: 'stats', label: '统计审计', icon: 'fa-chart-pie', category: '科研' },
  { id: 'polishing', label: '专业润色', icon: 'fa-feather-pointed', category: '科研' },
  { id: 'paper2ppt', label: '论文转PPT', icon: 'fa-file-powerpoint', category: '科研' },
  { id: 'paper-to-patent', label: '论文转专利', icon: 'fa-award', category: '科研' },
  { id: 'submission-package', label: '投稿打包', icon: 'fa-box', category: '科研' },
  { id: 'data-availability', label: '数据可用性', icon: 'fa-database', category: '科研' },
];

export default function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [selectedIdx, setSelectedIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  useFocusTrap(panelRef, open);

  const commands: CommandItem[] = STATIC_COMMANDS.map(c => ({
    ...c,
    action: () => {
      navigate(`/app/${c.id}`);
      onClose();
    },
  }));

  const filtered = query.trim()
    ? commands.filter(c =>
        c.label.toLowerCase().includes(query.toLowerCase()) ||
        c.category.toLowerCase().includes(query.toLowerCase())
      )
    : commands;

  useEffect(() => {
    if (open) {
      setQuery('');
      setSelectedIdx(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  useEffect(() => {
    setSelectedIdx(0);
  }, [query]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIdx(prev => (prev + 1) % filtered.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIdx(prev => (prev - 1 + filtered.length) % filtered.length);
    } else if (e.key === 'Enter' && filtered[selectedIdx]) {
      e.preventDefault();
      filtered[selectedIdx].action();
    } else if (e.key === 'Escape') {
      onClose();
    }
  }, [filtered, selectedIdx, onClose]);

  if (!open) return null;

  const grouped = filtered.reduce<Record<string, CommandItem[]>>((acc, cmd) => {
    (acc[cmd.category] = acc[cmd.category] || []).push(cmd);
    return acc;
  }, {});

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            transition={{ duration: 0.15, ease: [0.16, 1, 0.3, 1] }}
            ref={panelRef}
            className="fixed left-1/2 top-[20%] z-50 w-full max-w-lg -translate-x-1/2 overflow-hidden rounded-xl border border-copper/20 bg-[#1A1F2A] shadow-2xl shadow-black/50"
          >
            {/* 搜索输入 */}
            <div className="flex items-center gap-3 border-b border-copper/10 px-4 py-3">
              <i className="fas fa-search text-sm text-ink-bg/50" />
              <input
                ref={inputRef}
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="搜索页面、功能..."
                className="flex-1 bg-transparent text-sm text-ink-bg placeholder:text-ink-bg/50 focus:outline-none"
              />
              <kbd className="rounded border border-copper/20 bg-ink-dark/40 px-1.5 py-0.5 text-[10px] text-ink-bg/60">
                ESC
              </kbd>
            </div>

            {/* 结果列表 */}
            <div className="max-h-80 overflow-y-auto p-2">
              {filtered.length === 0 ? (
                <div className="py-8 text-center text-sm text-ink-bg/60">
                  未找到匹配项
                </div>
              ) : (
                Object.entries(grouped).map(([category, items]) => (
                  <div key={category} className="mb-2">
                    <div className="px-2 py-1 text-[10px] font-medium text-ink-bg/50 uppercase tracking-wider">
                      {category}
                    </div>
                    {items.map(item => {
                      const idx = filtered.indexOf(item);
                      return (
                        <button
                          key={item.id}
                          onClick={item.action}
                          onMouseEnter={() => setSelectedIdx(idx)}
                          className={`flex w-full cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                            idx === selectedIdx
                              ? 'bg-copper/10 text-copper-light'
                              : 'text-ink-bg/60 hover:bg-copper/5 hover:text-ink-bg'
                          }`}
                        >
                          <i className={`fas ${item.icon} w-4 text-center text-xs`} />
                          <span>{item.label}</span>
                          {idx === selectedIdx && (
                            <i className="fas fa-arrow-right ml-auto text-[10px] text-ink-bg/50" />
                          )}
                        </button>
                      );
                    })}
                  </div>
                ))
              )}
            </div>

            {/* 底部提示 */}
            <div className="flex items-center justify-between border-t border-copper/10 px-4 py-2 text-[10px] text-ink-bg/50">
              <span>
                <kbd className="mr-1 rounded border border-copper/20 bg-ink-dark/40 px-1 py-0.5">↑↓</kbd>
                导航
                <kbd className="mx-1 rounded border border-copper/20 bg-ink-dark/40 px-1 py-0.5">Enter</kbd>
                选择
              </span>
              <span>Ctrl+K 打开</span>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

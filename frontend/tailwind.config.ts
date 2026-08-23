import type { Config } from 'tailwindcss';

// 墨观 · 学术天文台 Design System — SaaS Dashboard 风格
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // SaaS Dashboard 语义色板
        primary: {
          DEFAULT: '#2563EB',
          hover: '#1D4ED8',
          active: '#1E40AF',
          light: '#3B82F6',
          ring: '#93C5FD',
          fg: '#FFFFFF',
          muted: '#EFF6FF',
          border: '#BFDBFE',
        },
        cta: {
          DEFAULT: '#F97316',
          hover: '#EA580C',
          active: '#C2410C',
          light: '#FB923C',
          ring: '#FDBA74',
          fg: '#FFFFFF',
        },
        // 层级背景
        bg: {
          DEFAULT: '#F8FAFC',
          surface: '#FFFFFF',
          muted: '#F1F5F9',
          subtle: '#E2E8F0',
        },
        // 文字层级
        txt: {
          DEFAULT: '#1E293B',
          muted: '#64748B',
          light: '#94A3B8',
          inverse: '#F8FAFC',
        },
        // 边框
        border: {
          DEFAULT: '#E2E8F0',
          light: '#F1F5F9',
          strong: '#CBD5E1',
        },
        // 语义状态色
        danger: {
          DEFAULT: '#DC2626',
          hover: '#B91C1C',
          bg: '#FEF2F2',
          fg: '#DC2626',
        },
        success: {
          DEFAULT: '#16A34A',
          bg: '#F0FDF4',
          fg: '#16A34A',
        },
        warning: {
          DEFAULT: '#D97706',
          bg: '#FFFBEB',
          fg: '#D97706',
        },
        // 深色模式覆盖
        dark: {
          bg: '#020617',
          surface: '#0F172A',
          elevated: '#1E293B',
          txt: '#F8FAFC',
          muted: '#CBD5E1',
          border: '#334155',
          primary: '#60A5FA',
          cta: '#FB923C',
        },
        // 兼容旧 token（渐进迁移）
        ink: {
          bg: '#F8FAFC',
          'bg-deep': '#F1F5F9',
          dark: '#020617',
          body: '#1E293B',
          muted: '#64748B',
        },
        copper: {
          DEFAULT: '#2563EB',
          light: '#3B82F6',
          deep: '#1D4ED8',
          glow: 'rgba(37, 99, 235, 0.12)',
        },
        tech: {
          DEFAULT: '#2563EB',
          light: '#3B82F6',
          deep: '#1D4ED8',
          glow: 'rgba(37, 99, 235, 0.12)',
        },
        jade: '#16A34A',
        vermillion: '#DC2626',
        indigo: '#4F46E5',
      },
      fontFamily: {
        serif: ['"Noto Serif SC"', 'Georgia', '"Songti SC"', 'serif'],
        sans: ['"DM Sans"', '"PingFang SC"', '"Microsoft YaHei"', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'Menlo', 'monospace'],
      },
      boxShadow: {
        'card': '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
        'card-hover': '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
        'elevated': '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
        'float': '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)',
      },
      animation: {
        'star-movement-bottom': 'star-movement-bottom linear infinite alternate',
        'star-movement-top': 'star-movement-top linear infinite alternate',
        'float-orb': 'floatOrb 14s ease-in-out infinite',
      },
      keyframes: {
        'star-movement-bottom': {
          '0%': { transform: 'translate(0%, 0%)', opacity: '1' },
          '100%': { transform: 'translate(-100%, 0%)', opacity: '0' },
        },
        'star-movement-top': {
          '0%': { transform: 'translate(0%, 0%)', opacity: '1' },
          '100%': { transform: 'translate(100%, 0%)', opacity: '0' },
        },
        floatOrb: {
          '0%, 100%': { transform: 'translate(0, 0) scale(1)' },
          '50%': { transform: 'translate(30px, -20px) scale(1.05)' },
        },
      },
    },
  },
  plugins: [],
} satisfies Config;

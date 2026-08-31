/** @type {import('tailwindcss').Config} */
// 墨观 · 学术天文台 Design Token 桥接
// 原则：所有颜色走 RGB 通道变量（index.css :root / .dark），支撑 Tailwind 透明度修饰符（如 bg-copper/20）
// 旧调色板（copper/jade/vermillion/indigo/ink）为语义 token 的主题感知别名（backward compat）
const rgb = (name) => `rgb(var(--${name}-rgb) / <alpha-value>)`;

module.exports = {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        /* ===== 语义 token ===== */
        primary: rgb('primary'),
        'primary-foreground': 'var(--color-primary-foreground)',
        'primary-hover': rgb('primary-hover'),
        'primary-active': rgb('primary-active'),
        'primary-muted': 'var(--color-primary-muted)',
        'primary-border': 'var(--color-primary-border)',
        'primary-ring': 'var(--color-primary-ring)',
        'secondary-text': rgb('secondary-text'),
        cta: rgb('cta'),
        'cta-foreground': 'var(--color-cta-foreground)',
        'cta-hover': rgb('cta-hover'),
        'cta-active': rgb('cta-active'),
        'cta-ring': 'var(--color-cta-ring)',
        danger: rgb('danger'),
        'danger-foreground': 'var(--color-danger-foreground)',
        'danger-hover': rgb('danger-hover'),
        success: rgb('success'),
        warning: rgb('warning'),
        surface: rgb('surface'),
        'bg-muted': rgb('surface-muted'),
        border: rgb('border'),
        'border-strong': rgb('border-strong'),
        txt: rgb('txt'),
        'txt-muted': rgb('txt-muted'),
        'txt-light': rgb('txt-light'),
        bg: rgb('bg'),

        /* ===== 旧调色板别名（主题感知） ===== */
        copper: rgb('primary'),
        'copper-light': rgb('copper-light'),
        'copper-deep': rgb('primary-active'),
        vermillion: rgb('danger'),
        jade: rgb('success'),
        'success-bg': 'rgb(var(--success-rgb) / 0.12)',
        indigo: rgb('indigo'),

        /* ===== ink 中性系 ===== */
        ink: rgb('ink'),
        'ink-dark': rgb('ink-dark'),
        'ink-bg': rgb('ink-bg'),
      },
      boxShadow: {
        card: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
        'card-hover': '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
        elevated: '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
      },
    },
  },
  plugins: [],
}

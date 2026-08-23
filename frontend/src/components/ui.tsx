// 共享 UI 组件 — 墨观 SaaS Dashboard Design System
import { type ReactNode, type ButtonHTMLAttributes } from 'react';

// 按钮 — 5 个语义 variant + 3 个尺寸
type ButtonVariant = 'primary' | 'cta' | 'secondary' | 'ghost' | 'danger';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: string;
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading,
  icon,
  children,
  className = '',
  disabled,
  ...rest
}: ButtonProps) {
  const variants: Record<ButtonVariant, string> = {
    primary:
      'bg-primary text-white shadow-sm hover:bg-primary-hover hover:shadow-md active:bg-primary-active active:shadow-sm focus-visible:ring-primary-ring',
    cta:
      'bg-cta text-white shadow-sm hover:bg-cta-hover hover:shadow-md active:bg-cta-active active:shadow-sm focus-visible:ring-cta-ring',
    secondary:
      'border border-primary-border bg-primary-muted text-primary hover:bg-primary/10 hover:border-primary/40 focus-visible:ring-primary-ring',
    ghost:
      'text-txt-muted hover:bg-bg-muted hover:text-txt focus-visible:ring-primary-ring',
    danger:
      'bg-danger text-white shadow-sm hover:bg-danger-hover hover:shadow-md active:shadow-sm focus-visible:ring-red-300',
  };

  const sizes: Record<ButtonSize, string> = {
    sm: 'px-3 py-1.5 text-xs',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-base',
  };

  return (
    <button
      className={`inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${sizes[size]} ${className}`}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? (
        <>
          <i className="fas fa-circle-notch animate-spin text-xs" />
          处理中
        </>
      ) : icon ? (
        <>
          <i className={`fas ${icon} text-xs`} />
          {children}
        </>
      ) : (
        children
      )}
    </button>
  );
}

// 卡片 — 白色浮层 + 边框
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-border bg-surface p-6 shadow-card transition-all duration-200 hover:shadow-card-hover hover:border-border-strong ${className}`}>
      {children}
    </div>
  );
}

// 输入框
interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  icon?: string;
}

export function Input({ label, icon, className = '', ...rest }: InputProps) {
  return (
    <label className="block">
      {label && <span className="mb-1.5 block text-xs font-medium text-txt-muted">{label}</span>}
      <div className="relative">
        {icon && (
          <i className={`fas ${icon} absolute left-3 top-1/2 -translate-y-1/2 text-xs text-txt-light`} />
        )}
        <input
          className={`w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-txt placeholder:text-txt-light transition-colors duration-200 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 ${icon ? 'pl-9' : ''} ${className}`}
          {...rest}
        />
      </div>
    </label>
  );
}

// 文本域
interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
}

export function Textarea({ label, className = '', ...rest }: TextareaProps) {
  return (
    <label className="block">
      {label && <span className="mb-1.5 block text-xs font-medium text-txt-muted">{label}</span>}
      <textarea
        className={`w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-txt placeholder:text-txt-light transition-colors duration-200 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 ${className}`}
        {...rest}
      />
    </label>
  );
}

// 加载状态
export function Loading({ text = '加载中' }: { text?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-12 text-txt-muted">
      <i className="fas fa-circle-notch animate-spin text-primary" />
      <span className="text-sm">{text}</span>
    </div>
  );
}

// 空状态
export function EmptyState({ icon, title, hint, action }: { icon: string; title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-bg-muted">
        <i className={`fas ${icon} text-2xl text-txt-light`} />
      </div>
      <p className="text-sm font-medium text-txt">{title}</p>
      {hint && <p className="mt-1 text-xs text-txt-muted">{hint}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

// 错误提示
export function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-danger">
      <i className="fas fa-exclamation-circle" />
      <span>{message}</span>
    </div>
  );
}

// 成功提示
export function SuccessBanner({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-2.5 text-sm text-success">
      <i className="fas fa-check-circle" />
      <span>{message}</span>
    </div>
  );
}

// 警告提示
export function WarningBanner({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-warning">
      <i className="fas fa-exclamation-triangle" />
      <span>{message}</span>
    </div>
  );
}

// 页面标题
export function PageHeader({ title, subtitle, icon, action }: { title: string; subtitle?: string; icon: string; action?: ReactNode }) {
  return (
    <div className="mb-6 flex items-start justify-between">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <i className={`fas ${icon}`} />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-txt">{title}</h1>
          {subtitle && <p className="mt-0.5 text-xs text-txt-muted">{subtitle}</p>}
        </div>
      </div>
      {action}
    </div>
  );
}

// 徽章 — 状态标签
type BadgeVariant = 'default' | 'primary' | 'success' | 'danger' | 'warning'
  | 'copper' | 'jade' | 'vermillion' | 'indigo'; // backward compat

export function Badge({
  children,
  variant = 'default',
  className = '',
}: {
  children: ReactNode;
  variant?: BadgeVariant;
  className?: string;
}) {
  const variants: Record<BadgeVariant, string> = {
    default: 'border-border bg-bg-muted text-txt-muted',
    primary: 'border-primary-border bg-primary-muted text-primary',
    success: 'border-green-200 bg-green-50 text-success',
    danger: 'border-red-200 bg-red-50 text-danger',
    warning: 'border-amber-200 bg-amber-50 text-warning',
    // backward compat aliases
    copper: 'border-primary-border bg-primary-muted text-primary',
    jade: 'border-green-200 bg-green-50 text-success',
    vermillion: 'border-red-200 bg-red-50 text-danger',
    indigo: 'border-indigo-200 bg-indigo-50 text-indigo',
  };
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${variants[variant]} ${className}`}>
      {children}
    </span>
  );
}

// Tab 切换组
interface TabItem {
  key: string;
  label: string;
  icon?: string;
}

export function Tabs({
  items,
  active,
  onChange,
  className = '',
}: {
  items: TabItem[];
  active: string;
  onChange: (key: string) => void;
  className?: string;
}) {
  return (
    <div role="tablist" className={`inline-flex flex-wrap gap-1 rounded-lg border border-border bg-bg-muted p-1 ${className}`}>
      {items.map(item => (
        <button
          key={item.key}
          role="tab"
          aria-selected={active === item.key}
          onClick={() => onChange(item.key)}
          className={`flex cursor-pointer items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-ring ${
            active === item.key
              ? 'bg-surface text-primary shadow-sm'
              : 'text-txt-muted hover:text-txt'
          }`}
        >
          {item.icon && <i className={`fas ${item.icon}`} />}
          {item.label}
        </button>
      ))}
    </div>
  );
}

// 状态点 — 用于实时状态指示
export function StatusDot({ status = 'idle' }: { status?: 'idle' | 'running' | 'success' | 'error' }) {
  const colors = {
    idle: 'bg-txt-light',
    running: 'bg-success animate-pulse',
    success: 'bg-success',
    error: 'bg-danger',
  };
  return <span className={`inline-block h-2 w-2 rounded-full ${colors[status]}`} />;
}

// Select 下拉
interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options: { value: string; label: string }[];
}

export function Select({ label, options, className = '', ...rest }: SelectProps) {
  return (
    <label className="block">
      {label && <span className="mb-1.5 block text-xs font-medium text-txt-muted">{label}</span>}
      <select
        aria-label={label || undefined}
        className={`w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-txt transition-colors duration-200 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 ${className}`}
        {...rest}
      >
        {options.map(opt => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
    </label>
  );
}

// Toggle 开关
export function Toggle({
  checked,
  onChange,
  label,
  disabled,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  disabled?: boolean;
}) {
  return (
    <label className={`inline-flex items-center gap-2 ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}`}>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => !disabled && onChange(!checked)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-ring focus-visible:ring-offset-2 ${
          checked ? 'bg-primary' : 'bg-border-strong'
        }`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white shadow-sm transition-transform duration-200 ${
            checked ? 'translate-x-6' : 'translate-x-1'
          }`}
        />
      </button>
      {label && <span className="text-sm text-txt">{label}</span>}
    </label>
  );
}

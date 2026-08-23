/// <reference types="vite/client" />
// 全局错误边界 — 捕获渲染错误，防止白屏
import { Component, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  handleGoHome = () => {
    this.setState({ hasError: false, error: null });
    window.location.href = '/app';
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-ink-dark p-6">
          <div className="w-full max-w-md text-center">
            <div className="mb-6 flex justify-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-vermillion/10">
                <i className="fas fa-exclamation-triangle text-2xl text-vermillion" />
              </div>
            </div>
            <h1 className="mb-2 font-serif text-xl text-ink-bg">页面出错了</h1>
            <p className="mb-6 text-sm text-ink-bg/50">
              {this.state.error?.message || '发生了未知错误'}
            </p>
            <div className="flex justify-center gap-3">
              <button
                onClick={this.handleReset}
                className="cursor-pointer rounded-lg border border-copper/30 bg-ink-dark/40 px-4 py-2 text-sm text-copper-light transition-colors hover:border-copper/60 hover:bg-copper/5"
              >
                <i className="fas fa-redo mr-1.5" />
                重试
              </button>
              <button
                onClick={this.handleGoHome}
                className="cursor-pointer rounded-lg bg-copper px-4 py-2 text-sm font-medium text-ink-dark transition-colors hover:bg-copper-deep"
              >
                <i className="fas fa-home mr-1.5" />
                返回首页
              </button>
            </div>
            {!import.meta.env.PROD && (
              <details className="mt-6 text-left">
                <summary className="cursor-pointer text-xs text-ink-bg/50 hover:text-ink-bg/50">
                  错误详情
                </summary>
                <pre className="mt-2 max-h-40 overflow-auto rounded-lg bg-ink-dark/60 p-3 text-[10px] text-ink-bg/50">
                  {this.state.error?.stack}
                </pre>
              </details>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

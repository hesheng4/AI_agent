// E8: PWA 安装提示组件 — beforeinstallprompt 触发显示，用户可安装为原生 App
import { useEffect, useState } from 'react';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

export default function PWAInstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // 已安装则不提示
    if (window.matchMedia('(display-mode: standalone)').matches) return;

    const handler = (e: Event) => {
      e.preventDefault(); // 阻止 Chrome 自动弹窗，改用自定义 UI
      setDeferredPrompt(e as BeforeInstallPromptEvent);
      setVisible(true);
    };
    window.addEventListener('beforeinstallprompt', handler);
    return () => window.removeEventListener('beforeinstallprompt', handler);
  }, []);

  async function handleInstall() {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === 'accepted') {
      setVisible(false);
      setDeferredPrompt(null);
    }
  }

  function handleDismiss() {
    setVisible(false);
    setDeferredPrompt(null);
    // 7 天内不再提示
    localStorage.setItem('pwa-install-dismissed', Date.now().toString());
  }

  // 检查是否在dismiss冷却期
  const dismissed = localStorage.getItem('pwa-install-dismissed');
  if (dismissed && Date.now() - parseInt(dismissed) < 7 * 24 * 60 * 60 * 1000) {
    return null;
  }

  if (!visible) return null;

  return (
    <div className="fixed bottom-4 left-1/2 z-50 -translate-x-1/2 rounded-xl border border-copper/30 bg-ink-dark/95 px-4 py-3 shadow-2xl backdrop-blur-xl">
      <div className="flex items-center gap-3">
        <i className="fas fa-download text-copper" />
        <div className="mr-2">
          <div className="text-sm font-medium text-ink-bg">安装墨观 App</div>
          <div className="text-xs text-ink-bg/50">离线可用 · 桌面快捷启动</div>
        </div>
        <button onClick={handleInstall} className="rounded-lg bg-copper px-3 py-1.5 text-xs font-medium text-ink-dark transition hover:bg-copper-light">
          安装
        </button>
        <button onClick={handleDismiss} className="text-ink-bg/40 hover:text-ink-bg/70" aria-label="关闭">
          <i className="fas fa-times" />
        </button>
      </div>
    </div>
  );
}

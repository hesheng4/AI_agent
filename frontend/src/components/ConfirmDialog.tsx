// 自定义确认对话框 — 替换原生 confirm()
import { useEffect, useRef } from 'react';
import { AnimatePresence, motion } from 'motion/react';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function ConfirmDialog({
  open, title, message,
  confirmLabel = '确认', cancelLabel = '取消',
  danger = true, onConfirm, onCancel,
}: ConfirmDialogProps) {
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) setTimeout(() => confirmRef.current?.focus(), 50);
  }, [open]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={onCancel}
            className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm"
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="fixed left-1/2 top-1/2 z-50 w-full max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-xl border border-border bg-surface p-6 shadow-elevated"
          >
            <h3 className="text-sm font-medium text-txt">{title}</h3>
            <p className="mt-2 text-xs text-txt-muted">{message}</p>
            <div className="mt-5 flex justify-end gap-2">
              <button onClick={onCancel} className="cursor-pointer rounded-lg border border-border px-3 py-1.5 text-xs text-txt-muted transition-colors hover:bg-bg-muted">
                {cancelLabel}
              </button>
              <button
                ref={confirmRef}
                onClick={onConfirm}
                className={`cursor-pointer rounded-lg px-3 py-1.5 text-xs font-medium text-ink-dark transition-colors ${danger ? 'bg-vermillion hover:bg-vermillion/80' : 'bg-primary hover:bg-primary/80'}`}
              >
                {confirmLabel}
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

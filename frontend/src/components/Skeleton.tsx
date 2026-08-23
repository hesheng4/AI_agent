// 骨架屏 — 替代 spinner 加载占位
export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-bg-muted ${className}`} />;
}

export function SkeletonLine({ width = '100%', className = '' }: { width?: string; className?: string }) {
  return <div className={`animate-pulse rounded bg-bg-muted h-4 ${className}`} style={{ width }} />;
}

export function PageSkeleton() {
  return (
    <div className="space-y-6 p-6">
      <div className="animate-pulse rounded-lg bg-bg-muted h-8 w-48" />
      <div className="grid gap-4 sm:grid-cols-3">
        {[1, 2, 3].map(i => <div key={i} className="animate-pulse rounded-lg border border-border bg-surface h-32" />)}
      </div>
      <div className="animate-pulse rounded-lg bg-bg-muted h-64" />
    </div>
  );
}

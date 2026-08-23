// CountUp — 数字滚动动画，用于统计指标
import { useEffect, useRef, useState } from 'react';
import { useInView, useMotionValue, useSpring, motion } from 'motion/react';

interface CountUpProps {
  to: number;
  from?: number;
  duration?: number;
  decimals?: number;
  suffix?: string;
  prefix?: string;
  className?: string;
}

// 尊重 prefers-reduced-motion：直接显示终值
export default function CountUp({
  to,
  from = 0,
  duration = 2,
  decimals = 0,
  suffix = '',
  prefix = '',
  className = '',
}: CountUpProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: '-50px' });
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const [display, setDisplay] = useState(from);

  // 弹簧动画驱动数字增长
  const count = useMotionValue(from);
  const spring = useSpring(count, { duration: duration * 1000, bounce: 0 });

  useEffect(() => {
    if (!inView) return;
    if (prefersReduced) {
      setDisplay(to);
      return;
    }
    count.set(to);
    const unsub = spring.on('change', v => {
      setDisplay(v);
    });
    return () => unsub();
  }, [inView, to, count, spring, prefersReduced]);

  const formatted = display.toLocaleString('zh-CN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

  return (
    <motion.span ref={ref} className={className}>
      {prefix}
      {formatted}
      {suffix}
    </motion.span>
  );
}

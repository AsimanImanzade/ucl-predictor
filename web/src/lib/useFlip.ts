import { useLayoutEffect, useRef } from 'react';

const reduced = () => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

/**
 * FLIP: rows keyed by data-key slide from their old position to the new one when `order` changes.
 * The what-if ripple's one bold motion; skipped under prefers-reduced-motion.
 */
export function useFlip<T extends HTMLElement>(order: string) {
  const ref = useRef<T>(null);
  const last = useRef(new Map<string, number>());
  useLayoutEffect(() => {
    const root = ref.current;
    if (!root) return;
    const rows = [...root.querySelectorAll<HTMLElement>('[data-key]')];
    const next = new Map(rows.map((r) => [r.dataset.key!, r.getBoundingClientRect().top]));
    if (!reduced() && last.current.size) {
      for (const r of rows) {
        const before = last.current.get(r.dataset.key!);
        const dy = before === undefined ? 0 : before - next.get(r.dataset.key!)!;
        if (Math.abs(dy) < 1) continue;
        r.animate([{ transform: `translateY(${dy}px)` }, { transform: 'translateY(0)' }], { duration: 650, easing: 'cubic-bezier(.2,.7,.2,1)' });
      }
    }
    last.current = next;
  }, [order]);
  return ref;
}

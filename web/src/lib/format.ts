/** Mathematical certainty from the real table, independent of simulation counts. */
export type Certainty = 'clinched' | 'eliminated';

/**
 * Probability label: whole % from 10 to 90, one decimal outside that range,
 * "<0.1%" / ">99.9%" at the ends. "Qualified" / "Out" only when certainty is known.
 */
export function formatPct(p: number, certainty?: Certainty): string {
  if (certainty === 'clinched') return 'Qualified';
  if (certainty === 'eliminated') return 'Out';
  const x = p * 100;
  if (x < 0.05) return '<0.1%';
  if (x >= 99.95) return '>99.9%';
  if (x < 10) {
    const s = x.toFixed(1);
    return s === '10.0' ? '10%' : `${s}%`;
  }
  if (x > 90) return `${x.toFixed(1)}%`;
  return `${Math.round(x)}%`;
}

/** Signed change in percentage points ("+4.2", "−3.1"); null when it rounds to zero. */
export function formatDelta(d: number): string | null {
  const x = d * 100;
  if (Math.abs(x) < 0.05) return null;
  const s = Math.abs(x).toFixed(1);
  return x > 0 ? `+${s}` : `−${s}`;
}

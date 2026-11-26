import type { PointsThresholds } from '@uclpred/sim';

/** Below this many simulated finishes a total's share is too noisy to show (standard error up to 2.5 points). */
export const MIN_SAMPLES = 400;

export interface PointsRow {
  points: number;
  /** Simulated (club, run) finishes on exactly this total. */
  samples: number;
  /** Share of them in the top 8 / top 24; null when there are too few samples. */
  top8: number | null;
  top24: number | null;
  /** Change against the baseline, null when within the noise or not comparable. */
  d8: number | null;
  d24: number | null;
}

const rate = (hits: number, n: number) => hits / n;
/** Array.prototype.findLast is ES2023; the build targets ES2022. */
const lastWhere = (xs: number[], f: (x: number) => boolean) => [...xs].reverse().find(f);

/** Scenario minus baseline share, or null within 2 standard errors; moves to or from 0 or 1 always show. */
function change(hits: number, n: number, baseHits: number | undefined, baseN: number | undefined): number | null {
  if (n < MIN_SAMPLES || baseN === undefined || baseHits === undefined || baseN < MIN_SAMPLES) return null;
  const a = rate(hits, n);
  const b = rate(baseHits, baseN);
  const d = a - b;
  if (d === 0) return null;
  const certain = (p: number) => p === 0 || p === 1;
  if (certain(a) !== certain(b)) return d;
  const se = Math.sqrt((a * (1 - a)) / n + (b * (1 - b)) / baseN);
  return Math.abs(d) < 2 * se ? null : d;
}

/**
 * The points totals worth showing: from the lowest well-sampled total with a real top-24 chance (>= 0.5%)
 * to the highest one where the top 8 is not yet all but certain (<= 99.5%), plus the nearest well-sampled
 * total either side for context. Totals nobody finished on are left out; thin ones show a dash.
 */
export function pointsRows(t: PointsThresholds, base?: PointsThresholds): PointsRow[] {
  const totals = t.count.map((_, p) => p).filter((p) => t.count[p]! > 0);
  const sampled = totals.filter((p) => t.count[p]! >= MIN_SAMPLES);
  const lo = sampled.find((p) => rate(t.top24[p]!, t.count[p]!) >= 0.005);
  const hi = lastWhere(sampled, (p) => rate(t.top8[p]!, t.count[p]!) <= 0.995);
  let shown = totals;
  if (lo !== undefined && hi !== undefined && lo <= hi) {
    const below = lastWhere(sampled, (p) => p < lo);
    const above = sampled.find((p) => p > hi);
    shown = totals.filter((p) => (p >= lo && p <= hi) || p === below || p === above);
  }
  return shown.map((p) => {
    const n = t.count[p]!;
    const few = n < MIN_SAMPLES;
    return {
      points: p,
      samples: n,
      top8: few ? null : rate(t.top8[p]!, n),
      top24: few ? null : rate(t.top24[p]!, n),
      d8: change(t.top8[p]!, n, base?.top8[p], base?.count[p]),
      d24: change(t.top24[p]!, n, base?.top24[p], base?.count[p]),
    };
  });
}

/** The lowest shown total where the share reaches 50%, with that share. */
export function evenChance(rows: PointsRow[], key: 'top8' | 'top24'): { points: number; value: number } | null {
  const r = rows.find((x) => x[key] !== null && x[key] >= 0.5);
  return r ? { points: r.points, value: r[key]! } : null;
}

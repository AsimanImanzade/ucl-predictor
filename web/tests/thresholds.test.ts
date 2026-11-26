import { describe, expect, it } from 'vitest';
import type { PointsThresholds } from '@uclpred/sim';
import { evenChance, MIN_SAMPLES, pointsRows } from '../src/lib/thresholds';

/** count[p] finishes on p points, of which share8 / share24 made the top 8 / 24 (rounded). */
function make(spec: Record<number, [number, number, number]>): PointsThresholds {
  const t: PointsThresholds = { count: Array(25).fill(0), top8: Array(25).fill(0), top24: Array(25).fill(0) };
  for (const [p, [n, s8, s24]] of Object.entries(spec)) {
    t.count[+p] = n;
    t.top8[+p] = Math.round(n * s8);
    t.top24[+p] = Math.round(n * s24);
  }
  return t;
}

const t = make({
  3: [5000, 0, 0],
  4: [5000, 0, 0.001],
  5: [5000, 0, 0.02],
  6: [5000, 0, 0.2],
  7: [5000, 0, 0.6],
  8: [5000, 0, 0.9],
  9: [5000, 0, 0.99],
  10: [5000, 0.002, 1],
  11: [100, 0.05, 1],
  12: [5000, 0.3, 1],
  13: [5000, 0.6, 1],
  14: [5000, 0.996, 1],
  15: [5000, 1, 1],
  16: [5000, 1, 1],
  17: [300, 1, 1],
});

describe('pointsRows', () => {
  it('keeps the totals in play plus one either side, and dashes the thin ones', () => {
    const rows = pointsRows(t);
    // 5 is the first total with top 24 >= 0.5%, 13 the last with top 8 <= 99.5%; plus 4 and 14.
    expect(rows.map((r) => r.points)).toEqual([4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]);
    const r11 = rows.find((r) => r.points === 11)!;
    expect(r11).toMatchObject({ samples: 100, top8: null, top24: null });
    expect(rows.find((r) => r.points === 12)).toMatchObject({ samples: 5000, top8: 0.3, top24: 1 });
    expect(MIN_SAMPLES).toBeGreaterThan(100);
  });

  it('skips a context row that has too few samples', () => {
    const u = make({ 6: [50, 0, 0.001], 7: [5000, 0, 0.5], 8: [5000, 0.5, 1], 9: [50, 1, 1] });
    expect(pointsRows(u).map((r) => r.points)).toEqual([7, 8]);
  });

  it('takes the nearest well-sampled total either side as context, and leaves out empty totals', () => {
    const u = make({ 2: [1000, 0, 0], 9: [1000, 0, 1], 11: [1000, 0.5, 1], 20: [1000, 1, 1] });
    expect(pointsRows(u).map((r) => r.points)).toEqual([2, 9, 11, 20]);
  });

  it('shows changes against a baseline only beyond the noise', () => {
    const base = make({ 7: [5000, 0, 0.5], 8: [5000, 0.5, 0.9], 9: [5000, 0.9, 1] });
    const now = make({ 7: [5000, 0, 0.51], 8: [5000, 0.6, 0.9], 9: [100, 0.5, 1], 10: [5000, 0.9, 1] });
    const rows = pointsRows(now, base);
    const at = (p: number) => rows.find((r) => r.points === p)!;
    expect(at(7).d24).toBeNull(); // +1 pt on 5,000 samples: noise
    expect(at(8).d8).toBeCloseTo(0.1, 6);
    expect(at(8).d24).toBeNull(); // no change
    expect(at(9).d8).toBeNull(); // too few samples now
  });

  it('always shows a change to or from a certainty', () => {
    const base = make({ 8: [5000, 0, 0.5], 9: [5000, 0.5, 1] });
    const now = make({ 8: [5000, 0.0004, 0.5], 9: [5000, 0.5, 1] });
    expect(pointsRows(now, base).find((r) => r.points === 8)!.d8).toBeCloseTo(0.0004, 6);
  });
});

describe('evenChance', () => {
  it('finds the lowest well-sampled total at or above 50%', () => {
    const rows = pointsRows(t);
    expect(evenChance(rows, 'top8')).toEqual({ points: 13, value: 0.6 });
    expect(evenChance(rows, 'top24')).toEqual({ points: 7, value: 0.6 });
    expect(evenChance(pointsRows(make({ 5: [1000, 0, 0.2] })), 'top8')).toBeNull();
  });
});

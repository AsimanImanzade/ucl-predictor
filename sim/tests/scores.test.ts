import { describe, expect, it } from 'vitest';
import { createRng } from '../src/rng.js';
import { outcomeProbs, samplePoisson, scoreMatrix, ScoreSampler } from '../src/scores.js';
import type { Lambdas } from '../src/types.js';

describe('createRng', () => {
  it('same seed gives same first 5 numbers; different seeds differ', () => {
    const a = createRng(42);
    const b = createRng(42);
    const c = createRng(43);
    const xs = Array.from({ length: 5 }, () => a());
    const ys = Array.from({ length: 5 }, () => b());
    const zs = Array.from({ length: 5 }, () => c());
    expect(xs).toEqual(ys);
    expect(xs).not.toEqual(zs);
    for (const x of xs) {
      expect(x).toBeGreaterThanOrEqual(0);
      expect(x).toBeLessThan(1);
    }
  });
});

describe('scoreMatrix / outcomeProbs', () => {
  it('matches the Python golden outcome values', () => {
    const [h, d, a] = outcomeProbs(scoreMatrix(1.5, 1.1, -0.1));
    expect(Math.abs(h - 0.451989)).toBeLessThan(1e-6);
    expect(Math.abs(d - 0.282178)).toBeLessThan(1e-6);
    expect(Math.abs(a - 0.265834)).toBeLessThan(1e-6);
  });
  it('sums to 1', () => {
    const m = scoreMatrix(1.5, 1.1, -0.1);
    expect(m.length).toBe(121);
    expect(m.reduce((s, x) => s + x, 0)).toBeCloseTo(1, 12);
  });
});

const lambdas: Lambdas = {
  asOf: '2026-01-01T00:00:00Z',
  model: 'elo-dc-v1',
  rho: -0.1,
  teams: ['aaa-a', 'bbb-b'],
  home: [
    [null, [1.5, 1.1]],
    [[1.2, 1.3], null],
  ],
  neutral: [
    [null, [1.4, 1.2]],
    [[1.2, 1.4], null],
  ],
};

describe('ScoreSampler', () => {
  it('empirical shares match outcomeProbs over 100k samples', () => {
    const s = new ScoreSampler(lambdas);
    const rng = createRng(7);
    const n = 100000;
    let h = 0, d = 0, a = 0;
    for (let i = 0; i < n; i++) {
      const [x, y] = s.sample('aaa-a', 'bbb-b', 'home', rng);
      if (x > y) h++; else if (x === y) d++; else a++;
    }
    const [ph, pd, pa] = outcomeProbs(scoreMatrix(1.5, 1.1, -0.1));
    expect(Math.abs(h / n - ph)).toBeLessThan(0.01);
    expect(Math.abs(d / n - pd)).toBeLessThan(0.01);
    expect(Math.abs(a / n - pa)).toBeLessThan(0.01);
  });
  it('lambda returns the pair and errors are clear', () => {
    const s = new ScoreSampler(lambdas);
    expect(s.lambda('bbb-b', 'aaa-a', 'neutral')).toEqual([1.2, 1.4]);
    expect(() => s.lambda('zzz', 'aaa-a', 'home')).toThrow(/zzz/);
    expect(() => s.sample('aaa-a', 'aaa-a', 'home', createRng(1))).toThrow();
  });
});

describe('samplePoisson', () => {
  it('mean of 100k draws at 0.5 is within 0.02', () => {
    const rng = createRng(11);
    let sum = 0;
    for (let i = 0; i < 100000; i++) sum += samplePoisson(0.5, rng);
    expect(Math.abs(sum / 100000 - 0.5)).toBeLessThan(0.02);
  });
});

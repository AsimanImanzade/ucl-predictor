import { describe, expect, it } from 'vitest';
import { simulate } from '../src/simulate.js';
import type { Fixture, Lambdas, Season, Team } from '../src/types.js';

const N = 36;
const ids = Array.from({ length: N }, (_, i) => `t${i}`);

function makeSeason(played: (f: Fixture) => [number, number] | null): Season {
  const teams: Team[] = ids.map((id, i) => ({
    id, fdId: i, name: id, shortName: id, tla: id, crest: '', country: 'xxx', coefficient: i,
  }));
  const fixtures: Fixture[] = [];
  let fid = 1;
  for (let i = 0; i < N; i++) {
    for (let k = 1; k <= 4; k++) {
      const f: Fixture = {
        id: fid++, matchday: k, utcDate: '2026-09-15T19:00:00Z',
        homeId: ids[i]!, awayId: ids[(i + k) % N]!, played: false, homeGoals: null, awayGoals: null,
      };
      const r = played(f);
      if (r) Object.assign(f, { played: true, homeGoals: r[0], awayGoals: r[1] });
      fixtures.push(f);
    }
  }
  return { season: '2026-27', asOf: '2026-09-07T00:00:00Z', finalVenueTeamId: null, teams, fixtures };
}

function makeLambdas(): Lambdas {
  const strength = ids.map((_, i) => 1.4 - (i / N) * 0.8);
  const mk = (h: number) =>
    ids.map((_, i) =>
      ids.map((__, j) =>
        i === j ? null : ([Math.max(0.2, (strength[i]! * h) / strength[j]! ** 0.5), Math.max(0.2, strength[j]! / strength[i]! ** 0.5)] as [number, number]),
      ),
    );
  return { asOf: 'x', model: 'test', rho: -0.05, teams: ids, home: mk(1.2), neutral: mk(1.0) };
}

const lambdas = makeLambdas();
const open = makeSeason(() => null);

describe('simulate', () => {
  it('probabilities sum correctly', () => {
    const r = simulate(open, lambdas, { runs: 3000, seed: 7 });
    const sum = (f: (c: (typeof r.chances)[number]) => number) => r.chances.reduce((a, c) => a + f(c), 0);
    expect(sum((c) => c.top8)).toBeCloseTo(8, 9);
    expect(sum((c) => c.top24)).toBeCloseTo(24, 9);
    expect(sum((c) => c.reach.winner)).toBeCloseTo(1, 9);
    expect(sum((c) => c.reach.r16)).toBeCloseTo(16, 9);
    expect(sum((c) => c.reach.qf)).toBeCloseTo(8, 9);
    expect(sum((c) => c.reach.sf)).toBeCloseTo(4, 9);
    expect(sum((c) => c.reach.final)).toBeCloseTo(2, 9);
    expect(sum((c) => c.reach.po)).toBeCloseTo(16, 9);
    for (let k = 0; k < N; k++) expect(sum((c) => c.position[k]!)).toBeCloseTo(1, 9);
    for (const c of r.chances) expect(c.top8 + (c.top24 - c.top8) + c.out).toBeCloseTo(1, 9);
    expect(r.chances.map((c) => c.teamId)).toEqual([...ids].sort());
    expect(r.asOf).toBe(open.asOf);
  });

  it('never resamples fixed results', () => {
    const full = makeSeason((f) => [(f.id * 7) % 4, (f.id * 3) % 3]);
    const a = simulate(full, lambdas, { runs: 50, seed: 1 });
    const b = simulate(full, lambdas, { runs: 50, seed: 2 });
    for (const c of a.chances) {
      expect(c.position.filter((p) => p === 1)).toHaveLength(1);
      expect(c.position.reduce((x, y) => x + y, 0)).toBeCloseTo(1, 12);
    }
    expect(a.chances.map((c) => c.position)).toEqual(b.chances.map((c) => c.position));
    expect(a.chances.map((c) => c.expectedPoints)).toEqual(b.chances.map((c) => c.expectedPoints));
  });

  it('overrides fix unplayed fixtures; played results win over overrides', () => {
    const base = makeSeason((f) => (f.homeId === 't0' || f.awayId === 't0' ? null : [0, 0]));
    const overrides: Record<number, { homeGoals: number; awayGoals: number }> = {};
    for (const f of base.fixtures) {
      if (f.homeId === 't0') overrides[f.id] = { homeGoals: 5, awayGoals: 0 };
      else if (f.awayId === 't0') overrides[f.id] = { homeGoals: 0, awayGoals: 5 };
    }
    const r = simulate(base, lambdas, { runs: 200, seed: 3, overrides });
    const t0 = r.chances.find((c) => c.teamId === 't0')!;
    expect(t0.top8).toBe(1);
    expect(t0.expectedPoints).toBe(24);
    // overrides on a played fixture are ignored
    const played = base.fixtures.find((f) => f.played)!;
    const r2 = simulate(base, lambdas, { runs: 200, seed: 3, overrides: { ...overrides, [played.id]: { homeGoals: 9, awayGoals: 0 } } });
    expect(r2.chances).toEqual(r.chances);
  });

  it('is deterministic per seed and fast', () => {
    const a = simulate(open, lambdas, { runs: 2000, seed: 5 });
    const t = Date.now();
    const b = simulate(open, lambdas, { runs: 2000, seed: 5 });
    expect(Date.now() - t).toBeLessThan(2000);
    expect(b).toEqual(a);
    const c = simulate(open, lambdas, { runs: 2000, seed: 6 });
    expect(c).not.toEqual(a);
  });
});

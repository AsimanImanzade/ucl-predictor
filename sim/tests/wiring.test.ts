import { describe, expect, it } from 'vitest';
import { createRng } from '../src/rng.js';
import { ScoreSampler } from '../src/scores.js';
import { simulate } from '../src/simulate.js';
import { buildRecords } from '../src/table.js';
import { rankTable } from '../src/tiebreak.js';
import { playFinal, playTwoLegged, type MatchSampler } from '../src/tie.js';
import type { Fixture, LambdaPair, Lambdas, Season, Team } from '../src/types.js';

const N = 36;
const ids = Array.from({ length: N }, (_, i) => `t${i}`);

/** A fully played league phase (8 matches per team) with an arbitrary but fixed set of results. */
function playedSeason(): Season {
  const teams: Team[] = ids.map((id, i) => ({
    id, fdId: i, name: id, shortName: id, tla: id, crest: '', country: 'xxx', coefficient: i,
  }));
  const fixtures: Fixture[] = [];
  let fid = 1;
  for (let i = 0; i < N; i++) {
    for (let k = 1; k <= 4; k++) {
      fixtures.push({
        id: fid, matchday: k, utcDate: '2026-09-15T19:00:00Z', homeId: ids[i]!, awayId: ids[(i + k) % N]!,
        played: true, homeGoals: (fid * 7) % 4, awayGoals: (fid * 3) % 3,
      });
      fid++;
    }
  }
  return { season: '2026-27', asOf: '2026-09-07T00:00:00Z', finalVenueTeamId: null, teams, fixtures };
}

function finalRanking(season: Season): string[] {
  const results = season.fixtures.map((f) => ({ homeId: f.homeId, awayId: f.awayId, homeGoals: f.homeGoals!, awayGoals: f.awayGoals! }));
  return rankTable(buildRecords(ids, results), new Map(season.teams.map((t) => [t.id, t.coefficient])));
}

function lambdasFrom(pair: (a: string, b: string) => LambdaPair, neutral = pair): Lambdas {
  const grid = (f: (a: string, b: string) => LambdaPair) => ids.map((a) => ids.map((b) => (a === b ? null : f(a, b))));
  return { asOf: 'x', model: 'test', rho: 0, teams: ids, home: grid(pair), neutral: grid(neutral) };
}

describe('knockout wiring inside simulate', () => {
  const season = playedSeason();
  const ranking = finalRanking(season);
  const rank = new Map(ranking.map((id, i) => [id, i + 1]));

  it('the better-ranked side always wins: every stage holds exactly the expected seeds', () => {
    // Near-certain results: the better-ranked team scores ~10, the other ~0, wherever they play.
    const lam = lambdasFrom((a, b) => (rank.get(a)! < rank.get(b)! ? [12, 1e-6] : [1e-6, 12]));
    const r = simulate(season, lam, { runs: 300, seed: 11 });
    for (const c of r.chances) {
      const k = rank.get(c.teamId)!;
      expect(c.top8).toBe(k <= 8 ? 1 : 0);
      expect(c.reach.po).toBe(k >= 9 && k <= 24 ? 1 : 0);
      // Exactly 1 for ranks 1-16 also proves each play-off winner is looked up once (playoffTie).
      expect(c.reach.r16).toBe(k <= 16 ? 1 : 0);
      expect(c.reach.qf).toBe(k <= 8 ? 1 : 0);
      // Pairs {1,2} and {3,4} are split across halves, so the semi-finalists are ranks 1-4.
      expect(c.reach.sf).toBe(k <= 4 ? 1 : 0);
      expect(c.reach.final).toBe(k <= 2 ? 1 : 0);
      expect(c.reach.winner).toBe(k === 1 ? 1 : 0);
    }
  });

  it('the better-placed side hosts the second leg (and extra time) in the play-offs and round of 16', () => {
    // Equal teams, strong home advantage: only extra time at the second-leg venue breaks the symmetry.
    const lam = lambdasFrom(() => [2.5, 0.5], () => [1, 1]);
    const r = simulate(season, lam, { runs: 20000, seed: 3 });
    const mean = (lo: number, hi: number, f: (c: (typeof r.chances)[number]) => number) => {
      const xs = r.chances.filter((c) => rank.get(c.teamId)! >= lo && rank.get(c.teamId)! <= hi).map(f);
      return xs.reduce((a, b) => a + b, 0) / xs.length;
    };
    // Seeded play-off sides (9-16) host leg 2: they advance more often than unseeded sides (17-24).
    expect(mean(9, 16, (c) => c.reach.r16)).toBeGreaterThan(0.52);
    expect(mean(17, 24, (c) => c.reach.r16)).toBeLessThan(0.48);
    // Top-8 sides host leg 2 of the round of 16.
    expect(mean(1, 8, (c) => c.reach.qf)).toBeGreaterThan(0.52);
  });
});

function stub(scores: [number, number][], lam: LambdaPair) {
  const lambdaCalls: { a: string; b: string; venue: string }[] = [];
  let i = 0;
  const sampler: MatchSampler = {
    sample: () => scores[i++]!,
    lambda(a, b, venue) {
      lambdaCalls.push({ a, b, venue });
      return lam;
    },
  };
  return { sampler, lambdaCalls };
}

describe('ties: extra time and aggregate', () => {
  it('level aggregate: extra time goals decide, at the second-leg venue', () => {
    for (let s = 1; s <= 200; s++) {
      // lambda(second, first): second-leg host expects 10 extra-time goals, the visitor none.
      const { sampler, lambdaCalls } = stub([[1, 0], [1, 0]], [30, 0]);
      expect(playTwoLegged('A', 'B', sampler, createRng(s))).toBe('B');
      expect(lambdaCalls).toEqual([{ a: 'B', b: 'A', venue: 'home' }]);
    }
    for (let s = 1; s <= 200; s++) {
      const { sampler } = stub([[2, 2], [0, 0]], [0, 30]);
      expect(playTwoLegged('A', 'B', sampler, createRng(s))).toBe('A');
    }
  });

  it('the second-leg host can win on aggregate without extra time', () => {
    // A 1-0 B, then B 3-0 A: B through 3-1.
    const { sampler, lambdaCalls } = stub([[1, 0], [3, 0]], [0, 0]);
    expect(playTwoLegged('A', 'B', sampler, createRng(1))).toBe('B');
    expect(lambdaCalls).toEqual([]);
  });

  it('level final goes to extra time with the venue team as host', () => {
    for (let s = 1; s <= 200; s++) {
      const { sampler, lambdaCalls } = stub([[1, 1]], [30, 0]);
      expect(playFinal('A', 'B', 'B', sampler, createRng(s))).toBe('B');
      expect(lambdaCalls).toEqual([{ a: 'B', b: 'A', venue: 'home' }]);
    }
  });

  it('level final at a neutral venue uses neutral rates', () => {
    for (let s = 1; s <= 200; s++) {
      const { sampler, lambdaCalls } = stub([[0, 0]], [0, 30]);
      expect(playFinal('A', 'B', null, sampler, createRng(s))).toBe('B');
      expect(lambdaCalls).toEqual([{ a: 'A', b: 'B', venue: 'neutral' }]);
    }
  });
});

describe('ScoreSampler orientation', () => {
  it('first goal count belongs to the first team, using that pair-and-venue cell', () => {
    const lam: Lambdas = {
      asOf: 'x', model: 'test', rho: 0, teams: ['A', 'B'],
      home: [[null, [3, 0.2]], [[0.4, 2.2], null]],
      neutral: [[null, [1.5, 0.7]], [[0.7, 1.5], null]],
    };
    const s = new ScoreSampler(lam);
    const rng = createRng(9);
    const mean = (a: string, b: string, venue: 'home' | 'neutral') => {
      let x = 0;
      let y = 0;
      for (let i = 0; i < 20000; i++) {
        const [g1, g2] = s.sample(a, b, venue, rng);
        x += g1;
        y += g2;
      }
      return [x / 20000, y / 20000];
    };
    const [ah, bh] = mean('A', 'B', 'home');
    expect(ah).toBeCloseTo(3, 1);
    expect(bh).toBeCloseTo(0.2, 1);
    const [bh2, ah2] = mean('B', 'A', 'home');
    expect(bh2).toBeCloseTo(0.4, 1);
    expect(ah2).toBeCloseTo(2.2, 1);
    const [an, bn] = mean('A', 'B', 'neutral');
    expect(an).toBeCloseTo(1.5, 1);
    expect(bn).toBeCloseTo(0.7, 1);
  });
});

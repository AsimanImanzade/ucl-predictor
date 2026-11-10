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

// Elo-like strengths with a clear favourite (t0).
const elo = ids.map((_, i) => (i === 0 ? 400 : 200 - i * 8));
const BETA = 0.16;
function makeLambdas(extra: Partial<Lambdas> = {}): Lambdas {
  const mk = (h: number) =>
    ids.map((_, i) =>
      ids.map((__, j) =>
        i === j
          ? null
          : ([
              h * 1.3 * Math.exp((BETA * (elo[i]! - elo[j]!)) / 100),
              1.3 * Math.exp((BETA * (elo[j]! - elo[i]!)) / 100),
            ] as [number, number]),
      ),
    );
  return { asOf: 'x', model: 'test', rho: -0.05, teams: ids, home: mk(1.2), neutral: mk(1.0), ...extra };
}

const open = makeSeason(() => null);
const maxWin = (r: ReturnType<typeof simulate>) => Math.max(...r.chances.map((c) => c.reach.winner));

describe('rating uncertainty', () => {
  it('sigma0_identical_to_current', () => {
    const old = simulate(open, makeLambdas(), { runs: 500, seed: 3 });
    const withFields = simulate(open, makeLambdas({ ratingSigma: 0, eloCoef: 0.16 }), { runs: 500, seed: 3 });
    expect(withFields).toEqual(old);
  });

  it('sigma_reduces_concentration', () => {
    const l = makeLambdas({ eloCoef: BETA });
    const a = maxWin(simulate(open, l, { runs: 4000, seed: 5, ratingSigma: 0 }));
    const b = maxWin(simulate(open, l, { runs: 4000, seed: 5, ratingSigma: 100 }));
    expect(b).toBeLessThan(a);
  });

  it('noisy_played_fixtures_never_resampled', () => {
    const season = makeSeason((f) => [f.homeId === 't0' ? 3 : 0, 0]);
    const r = simulate(season, makeLambdas({ eloCoef: BETA }), { runs: 200, seed: 1, ratingSigma: 100 });
    for (const c of r.chances) {
      for (const p of c.position) expect(p === 0 || p === 1).toBe(true);
    }
  });

  it('deterministic_with_sigma', () => {
    const l = makeLambdas({ eloCoef: BETA });
    const a = simulate(open, l, { runs: 300, seed: 9, ratingSigma: 70 });
    const b = simulate(open, l, { runs: 300, seed: 9, ratingSigma: 70 });
    expect(a).toEqual(b);
  });

  it('sigma_without_eloCoef_throws', () => {
    expect(() => simulate(open, makeLambdas(), { runs: 10, seed: 1, ratingSigma: 50 })).toThrow(
      'ratingSigma > 0 requires lambdas.eloCoef',
    );
    expect(() => simulate(open, makeLambdas({ ratingSigma: 50 }), { runs: 10, seed: 1 })).toThrow(
      'ratingSigma > 0 requires lambdas.eloCoef',
    );
  });
});

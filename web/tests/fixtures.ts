import { simulate, type Fixture, type Lambdas, type Season, type Team } from '@uclpred/sim';
import type { Snapshot, TeamMeta, TeamsFile } from '../src/lib/types';

export const N = 36;
export const ids = Array.from({ length: N }, (_, i) => `t${String(i).padStart(2, '0')}`);

/** 36 teams, 8 matchdays, 4 home + 4 away each; matchdays 1..playedThrough are played. */
export function makeSeason(playedThrough = 0): Season {
  const teams: Team[] = ids.map((id, i) => ({
    id, fdId: i, name: `Team ${i}`, shortName: `Team ${i}`, tla: `T${String.fromCharCode(65 + Math.floor(i / 26), 65 + (i % 26))}`,
    crest: `https://crests.example/${i}.png`, country: 'XXX', coefficient: 100 - i,
  }));
  const fixtures: Fixture[] = [];
  let fid = 1000;
  for (let k = 1; k <= 8; k++) {
    // Even team 2i meets odd team 2i+2k-1: 8 distinct opponents; evens host matchdays 1-4, odds 5-8.
    for (let i = 0; i < N / 2; i++) {
      const a = ids[(2 * i) % N]!;
      const b = ids[(2 * i + 2 * k - 1) % N]!;
      const [homeId, awayId] = k <= 4 ? [a, b] : [b, a];
      const played = k <= playedThrough;
      fixtures.push({
        id: fid++, matchday: k, utcDate: `2026-09-${String(8 + k).padStart(2, '0')}T19:00:00Z`, homeId, awayId,
        played, homeGoals: played ? (fid * 7) % 4 : null, awayGoals: played ? (fid * 3) % 3 : null,
      });
    }
  }
  return { season: '2026-27', asOf: '2026-09-07T00:00:00Z', finalVenueTeamId: null, teams, fixtures };
}

export function makeLambdas(season: Season): Lambdas {
  const strength = ids.map((_, i) => 1.4 - (i / N) * 0.8);
  const mk = (h: number) =>
    ids.map((_, i) => ids.map((__, j) => (i === j ? null : ([(strength[i]! * h) / strength[j]! ** 0.5, strength[j]! / strength[i]! ** 0.5] as [number, number]))));
  return { asOf: season.asOf, model: 'test', rho: -0.05, eloCoef: 0.12, ratingSigma: 0, teams: ids, home: mk(1.2), neutral: mk(1) };
}

export function makeSnapshot(playedThrough = 0, runs = 300): Snapshot {
  const season = makeSeason(playedThrough);
  const lambdas = makeLambdas(season);
  const res = simulate(season, lambdas, { runs, seed: 1 });
  return {
    meta: { id: 'live', label: 'Live', matchday: null, asOf: season.asOf, file: 'live.json', model: 'test', runs, seed: 1, ratingSigma: 0 },
    season,
    lambdas,
    chances: res.chances,
    ratings: Object.fromEntries(ids.map((id, i) => [id, 1800 - i * 10])),
  };
}

export function makeTeams(season: Season): TeamsFile {
  return Object.fromEntries(
    season.teams.map((t): [string, TeamMeta] => [
      t.id,
      { id: t.id, name: t.shortName, fullName: t.name, code: t.tla, crest: t.crest, colors: ['#d01f2f', '#f4f6fa'], country: t.country, coefficient: t.coefficient },
    ]),
  );
}

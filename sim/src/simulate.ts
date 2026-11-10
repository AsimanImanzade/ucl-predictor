import { createRng } from './rng.js';
import { NoisySampler, sampleNormals, ScoreSampler } from './scores.js';
import { buildRecords, type MatchResult } from './table.js';
import { rankTable } from './tiebreak.js';
import { drawBracket, drawPlayoffs } from './bracket.js';
import { playFinal, playTwoLegged, type MatchSampler } from './tie.js';
import type { Lambdas, Overrides, Season, SimResult, Stage, TeamChances, TeamId } from './types.js';

export interface SimOptions {
  runs: number;
  seed: number;
  overrides?: Overrides;
  /** Elo-point sigma of per-run team rating noise; overrides lambdas.ratingSigma. */
  ratingSigma?: number;
}

/**
 * Monte Carlo of the whole competition. Browser-safe: no Node APIs.
 * Played fixtures (real results) and overrides on unplayed fixtures are fixed; the rest
 * are sampled with the home side hosting.
 */
export function simulate(season: Season, lambdas: Lambdas, opts: SimOptions): SimResult {
  const { runs, seed, overrides } = opts;
  const rng = createRng(seed);
  const baseSampler = new ScoreSampler(lambdas);
  const sigma = opts.ratingSigma ?? lambdas.ratingSigma ?? 0;
  if (!Number.isFinite(sigma) || sigma < 0) throw new Error('ratingSigma must be a finite number >= 0');
  if (sigma > 0 && lambdas.eloCoef === undefined) throw new Error('ratingSigma > 0 requires lambdas.eloCoef');
  let sampler: MatchSampler = baseSampler;
  const teamIds: TeamId[] = season.teams.map((t) => t.id);
  const n = teamIds.length;
  const teamIndex = new Map<TeamId, number>();
  teamIds.forEach((id, i) => teamIndex.set(id, i));
  const coefficient = new Map<TeamId, number>(season.teams.map((t) => [t.id, t.coefficient]));

  const fixed: MatchResult[] = [];
  const open: { homeId: TeamId; awayId: TeamId }[] = [];
  for (const f of season.fixtures) {
    if (f.played && f.homeGoals !== null && f.awayGoals !== null) {
      fixed.push({ homeId: f.homeId, awayId: f.awayId, homeGoals: f.homeGoals, awayGoals: f.awayGoals });
      continue;
    }
    const o = overrides?.[f.id];
    if (o) fixed.push({ homeId: f.homeId, awayId: f.awayId, homeGoals: o.homeGoals, awayGoals: o.awayGoals });
    else open.push({ homeId: f.homeId, awayId: f.awayId });
  }

  const position = new Int32Array(n * n);
  const stages: Stage[] = ['po', 'r16', 'qf', 'sf', 'final', 'winner'];
  const reach = new Map<Stage, Int32Array>(stages.map((s) => [s, new Int32Array(n)]));
  const pointsSum = new Float64Array(n);
  const bump = (stage: Stage, id: TeamId): void => {
    reach.get(stage)![teamIndex.get(id)!]!++;
  };

  const results: MatchResult[] = new Array<MatchResult>(fixed.length + open.length);
  for (let i = 0; i < fixed.length; i++) results[i] = fixed[i]!;

  const playRound = (teams: TeamId[]): TeamId[] => {
    const next: TeamId[] = [];
    for (let i = 0; i < teams.length; i += 2) {
      const a = teams[i]!;
      const b = teams[i + 1]!;
      next.push(rng() < 0.5 ? playTwoLegged(a, b, sampler, rng) : playTwoLegged(b, a, sampler, rng));
    }
    return next;
  };

  for (let run = 0; run < runs; run++) {
    if (sigma > 0) {
      const z = sampleNormals(n, rng);
      const noise = new Map<TeamId, number>();
      for (let i = 0; i < n; i++) noise.set(teamIds[i]!, sigma * z[i]!);
      sampler = new NoisySampler(baseSampler, lambdas.eloCoef!, noise);
    }
    for (let k = 0; k < open.length; k++) {
      const m = open[k]!;
      const [hg, ag] = sampler.sample(m.homeId, m.awayId, 'home', rng);
      results[fixed.length + k] = { homeId: m.homeId, awayId: m.awayId, homeGoals: hg, awayGoals: ag };
    }
    const records = buildRecords(teamIds, results);
    for (const rec of records.values()) pointsSum[teamIndex.get(rec.id)!]! += rec.pts;
    const ranking = rankTable(records, coefficient);
    for (let p = 0; p < n; p++) {
      const id = ranking[p]!;
      position[teamIndex.get(id)! * n + p]!++;
      if (p >= 8 && p < 24) bump('po', id);
    }

    const ties = drawPlayoffs(ranking, rng);
    const poWinner = ties.map((t) => playTwoLegged(t.unseeded, t.seeded, sampler, rng));
    const slots = drawBracket(ranking, rng);
    const r16: TeamId[] = [];
    for (const s of slots) {
      const w = poWinner[s.playoffTie]!;
      bump('r16', s.top);
      bump('r16', w);
      r16.push(playTwoLegged(w, s.top, sampler, rng));
    }
    for (const id of r16) bump('qf', id);
    const qf = playRound(r16);
    for (const id of qf) bump('sf', id);
    const sf = playRound(qf);
    for (const id of sf) bump('final', id);
    const champ = playFinal(sf[0]!, sf[1]!, season.finalVenueTeamId, sampler, rng);
    bump('winner', champ);
  }

  const chances: TeamChances[] = teamIds.map((teamId, i) => {
    const pos = Array.from({ length: n }, (_, p) => position[i * n + p]! / runs);
    let top8 = 0;
    let top24 = 0;
    for (let p = 0; p < n; p++) {
      if (p < 8) top8 += position[i * n + p]!;
      if (p < 24) top24 += position[i * n + p]!;
    }
    top8 /= runs;
    top24 /= runs;
    const r = {} as Record<Stage, number>;
    for (const s of stages) r[s] = reach.get(s)![i]! / runs;
    return { teamId, position: pos, top8, top24, out: 1 - top24, reach: r, expectedPoints: pointsSum[i]! / runs };
  });
  chances.sort((a, b) => (a.teamId < b.teamId ? -1 : a.teamId > b.teamId ? 1 : 0));
  return { runs, seed, asOf: season.asOf, chances };
}

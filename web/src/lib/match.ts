import { outcomeProbs, scoreMatrix, type Lambdas, type TeamId } from '@uclpred/sim';

const MAX_GOALS = 10;

export interface ScoreProb {
  home: number;
  away: number;
  p: number;
}

export interface MatchProbs {
  lambdaHome: number;
  lambdaAway: number;
  home: number;
  draw: number;
  away: number;
  /** Three most likely exact scores. */
  top: ScoreProb[];
  /** grid[h][a] for 0..maxShown goals; the last row/column holds "maxShown or more". */
  grid: number[][];
}

/** Single-match probabilities from the same Dixon-Coles matrix the simulator samples. */
export function matchProbs(lambdas: Lambdas, homeId: TeamId, awayId: TeamId, maxShown = 5, venue: 'home' | 'neutral' = 'home'): MatchProbs {
  const i = lambdas.teams.indexOf(homeId);
  const j = lambdas.teams.indexOf(awayId);
  const cell = i >= 0 && j >= 0 ? (venue === 'home' ? lambdas.home : lambdas.neutral)[i]?.[j] : null;
  if (!cell) throw new Error(`no lambdas for ${homeId} v ${awayId}`);
  const [lh, la] = cell;
  const m = scoreMatrix(lh, la, lambdas.rho, MAX_GOALS);
  const [home, draw, away] = outcomeProbs(m, MAX_GOALS);
  const n = MAX_GOALS + 1;
  const scores: ScoreProb[] = [];
  const grid = Array.from({ length: maxShown + 1 }, () => new Array<number>(maxShown + 1).fill(0));
  for (let h = 0; h < n; h++) {
    for (let a = 0; a < n; a++) {
      const p = m[h * n + a]!;
      scores.push({ home: h, away: a, p });
      grid[Math.min(h, maxShown)]![Math.min(a, maxShown)]! += p;
    }
  }
  scores.sort((x, y) => y.p - x.p);
  return { lambdaHome: lh, lambdaAway: la, home, draw, away, top: scores.slice(0, 3), grid };
}

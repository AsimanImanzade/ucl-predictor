import type { Manifest, Snapshot } from './types';
import { matchProbs } from './match';

/** Ranked probability score for home / draw / away; outcome 0 = home win, 1 = draw, 2 = away win. */
export function rps(p: [number, number, number], outcome: 0 | 1 | 2): number {
  const o = [0, 0, 0];
  o[outcome] = 1;
  const c1 = p[0] - o[0]!;
  const c2 = p[0] + p[1] - o[0]! - o[1]!;
  return 0.5 * (c1 * c1 + c2 * c2);
}

export interface SeasonAccuracy {
  n: number;
  meanRps: number;
  /** Matches where the most likely outcome happened. */
  favouriteRight: number;
}

/**
 * Scores every played match with the forecast from the last snapshot before its kickoff
 * (pre-season for matchday 1, "after matchday 1" for matchday 2, and so on).
 */
export function seasonAccuracy(manifest: Manifest, snaps: Snapshot[], live: Snapshot): SeasonAccuracy {
  const byId = new Map(snaps.map((s) => [s.meta.id, s]));
  let n = 0;
  let sum = 0;
  let right = 0;
  for (const f of live.season.fixtures) {
    if (!f.played || f.homeGoals === null || f.awayGoals === null) continue;
    const before = manifest.snapshots.filter((s) => s.asOf < f.utcDate).sort((a, b) => (a.asOf < b.asOf ? 1 : -1))[0];
    const snap = before && byId.get(before.id);
    if (!snap) continue;
    const m = matchProbs(snap.lambdas, f.homeId, f.awayId);
    const p: [number, number, number] = [m.home, m.draw, m.away];
    const outcome = f.homeGoals > f.awayGoals ? 0 : f.homeGoals === f.awayGoals ? 1 : 2;
    sum += rps(p, outcome);
    n++;
    if (p.indexOf(Math.max(...p)) === outcome) right++;
  }
  return { n, meanRps: n ? sum / n : NaN, favouriteRight: right };
}

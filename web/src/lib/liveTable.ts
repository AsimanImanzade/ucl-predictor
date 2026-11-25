import type { Season, TeamId } from '@uclpred/sim';
import type { LiveScores } from './liveScores';
import { applyGuesses, type Guesses } from './scenario';

/**
 * Scores for the what-if and "as it stands" views. A game in play counts at its live
 * score unless the user typed their own; at full time the real score is locked in.
 * Games live.json already counts are left alone. Key order follows the season, so the
 * result serialises the same way each poll (the scenario sim keys on it).
 */
export function withLive(user: Guesses, season: Season, scores: LiveScores): Guesses {
  const out: Guesses = {};
  for (const f of season.fixtures) {
    if (f.played) continue;
    const s = scores.get(f.id);
    const mine = user[f.id];
    if (s && (s.status === 'FINISHED' || !mine)) out[f.id] = { homeGoals: s.home, awayGoals: s.away };
    else if (mine) out[f.id] = mine;
  }
  return out;
}

/** The season with every live score counted, for the "as it stands" table. */
export function asItStands(season: Season, scores: LiveScores): Season {
  return applyGuesses(season, withLive({}, season, scores));
}

/** Clubs in a game that is still running. */
export function playingNow(season: Season, scores: LiveScores): Set<TeamId> {
  const out = new Set<TeamId>();
  for (const f of season.fixtures) {
    const s = scores.get(f.id);
    if (!f.played && s && s.status !== 'FINISHED') {
      out.add(f.homeId);
      out.add(f.awayId);
    }
  }
  return out;
}

/** Games live.json does not count yet but the feed has a score for: still running, or at full time. */
export function liveCount(season: Season, scores: LiveScores): { running: number; finished: number } {
  let running = 0;
  let finished = 0;
  for (const f of season.fixtures) {
    const s = f.played ? undefined : scores.get(f.id);
    if (s?.status === 'FINISHED') finished++;
    else if (s) running++;
  }
  return { running, finished };
}

/** How many of the user's own scores the scenario uses (full time overrules a guess). */
export function usedGuessCount(user: Guesses, scenario: Guesses): number {
  return Object.keys(user).filter((id) => scenario[Number(id)] === user[Number(id)]).length;
}

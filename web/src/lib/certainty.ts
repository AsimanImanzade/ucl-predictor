import type { Season, TeamId } from '@uclpred/sim';
import type { Certainty } from './format';
import { standings, type StandingRow } from './standings';

const LEAGUE_MATCHES = 8;

export interface TeamCertainty {
  top8?: Certainty;
  top24?: Certainty;
}

/**
 * Mathematical certainty from the real table, by sound bounds (never wrong, sometimes late):
 * clinched top k when at most k-1 rivals can still reach the team's current points;
 * eliminated from top k when k rivals already have more than the team's maximum.
 * Once all league matches are played, the final ranking decides.
 */
export function certainty(season: Season, teamId: TeamId, rows: StandingRow[] = standings(season)): TeamCertainty {
  const me = rows.find((r) => r.teamId === teamId);
  if (!me) return {};
  const complete = season.fixtures.every((f) => f.played);
  const out: TeamCertainty = {};
  for (const [key, k] of [['top8', 8], ['top24', 24]] as const) {
    if (complete) {
      out[key] = me.rank <= k ? 'clinched' : 'eliminated';
      continue;
    }
    const rivals = rows.filter((r) => r.teamId !== teamId);
    const canReach = rivals.filter((r) => r.pts + 3 * (LEAGUE_MATCHES - r.played) >= me.pts).length;
    const myMax = me.pts + 3 * (LEAGUE_MATCHES - me.played);
    const already = rivals.filter((r) => r.pts > myMax).length;
    if (canReach <= k - 1) out[key] = 'clinched';
    else if (already >= k) out[key] = 'eliminated';
  }
  return out;
}

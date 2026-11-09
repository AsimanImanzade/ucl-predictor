import type { TeamId } from './types.js';

export interface TeamRecord {
  id: TeamId;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  gf: number;
  ga: number;
  gd: number;
  pts: number;
  /** Goals scored in away matches (tiebreak 3). */
  awayGf: number;
  /** Wins in away matches (tiebreak 5). */
  awayWins: number;
  /** Each opponent once per match played (league phase has no repeat pairings). */
  opponents: TeamId[];
}

export interface MatchResult {
  homeId: TeamId;
  awayId: TeamId;
  homeGoals: number;
  awayGoals: number;
}

function emptyRecord(id: TeamId): TeamRecord {
  return {
    id,
    played: 0,
    won: 0,
    drawn: 0,
    lost: 0,
    gf: 0,
    ga: 0,
    gd: 0,
    pts: 0,
    awayGf: 0,
    awayWins: 0,
    opponents: [],
  };
}

function apply(rec: TeamRecord, gf: number, ga: number, isAway: boolean, opp: TeamId): void {
  rec.played++;
  rec.gf += gf;
  rec.ga += ga;
  rec.gd += gf - ga;
  rec.opponents.push(opp);
  if (isAway) rec.awayGf += gf;
  if (gf > ga) {
    rec.won++;
    rec.pts += 3;
    if (isAway) rec.awayWins++;
  } else if (gf === ga) {
    rec.drawn++;
    rec.pts += 1;
  } else {
    rec.lost++;
  }
}

/** Aggregate match results into one record per team (3/1/0 points). Every id in teamIds gets a record. */
export function buildRecords(teamIds: TeamId[], results: MatchResult[]): Map<TeamId, TeamRecord> {
  const records = new Map<TeamId, TeamRecord>();
  for (const id of teamIds) records.set(id, emptyRecord(id));
  for (const m of results) {
    const home = records.get(m.homeId);
    const away = records.get(m.awayId);
    if (!home || !away) throw new Error(`result references unknown team: ${m.homeId} v ${m.awayId}`);
    apply(home, m.homeGoals, m.awayGoals, false, m.awayId);
    apply(away, m.awayGoals, m.homeGoals, true, m.homeId);
  }
  return records;
}

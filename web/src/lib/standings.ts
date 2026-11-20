import { buildRecords, rankTable, type MatchResult, type Season, type TeamId } from '@uclpred/sim';

export type FormResult = 'W' | 'D' | 'L';

export interface StandingRow {
  rank: number;
  teamId: TeamId;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  gf: number;
  ga: number;
  gd: number;
  pts: number;
  /** Up to the last five results, oldest first. */
  form: FormResult[];
}

/** The real league-phase table from played fixtures, ranked by the simulator's own tiebreak chain. */
export function standings(season: Season): StandingRow[] {
  const ids = season.teams.map((t) => t.id);
  const played = season.fixtures
    .filter((f) => f.played && f.homeGoals !== null && f.awayGoals !== null)
    .sort((a, b) => (a.utcDate < b.utcDate ? -1 : a.utcDate > b.utcDate ? 1 : a.id - b.id));
  const results: MatchResult[] = played.map((f) => ({ homeId: f.homeId, awayId: f.awayId, homeGoals: f.homeGoals!, awayGoals: f.awayGoals! }));
  const records = buildRecords(ids, results);
  const ranking = rankTable(records, new Map(season.teams.map((t) => [t.id, t.coefficient])));

  const form = new Map<TeamId, FormResult[]>(ids.map((id) => [id, []]));
  const res = (gf: number, ga: number): FormResult => (gf > ga ? 'W' : gf === ga ? 'D' : 'L');
  for (const m of results) {
    form.get(m.homeId)!.push(res(m.homeGoals, m.awayGoals));
    form.get(m.awayId)!.push(res(m.awayGoals, m.homeGoals));
  }
  return ranking.map((teamId, i) => {
    const r = records.get(teamId)!;
    return {
      rank: i + 1, teamId, played: r.played, won: r.won, drawn: r.drawn, lost: r.lost,
      gf: r.gf, ga: r.ga, gd: r.gd, pts: r.pts, form: form.get(teamId)!.slice(-5),
    };
  });
}

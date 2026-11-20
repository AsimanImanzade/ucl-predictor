import type { Lambdas, Season } from '@uclpred/sim';
import type { Snapshot, TeamsFile } from './types.ts';

const EPS = 1e-6;

/** What the simulator itself relies on; the Worker runs this before every simulation. */
export function validateSimInputs(season: Season, lambdas: Lambdas): string[] {
  const p: string[] = [];
  const teams = season.teams.map((t) => t.id);
  if (teams.length !== 36 || new Set(teams).size !== 36) p.push(`expected 36 distinct teams, got ${teams.length}`);
  if (season.fixtures.length !== 144) p.push(`expected 144 fixtures, got ${season.fixtures.length}`);

  const home = new Map(teams.map((t) => [t, 0]));
  const away = new Map(teams.map((t) => [t, 0]));
  for (const f of season.fixtures) {
    if (!home.has(f.homeId) || !away.has(f.awayId)) {
      p.push(`fixture ${f.id} references an unknown team`);
      continue;
    }
    home.set(f.homeId, home.get(f.homeId)! + 1);
    away.set(f.awayId, away.get(f.awayId)! + 1);
    const goalsOk = (g: number | null) => g !== null && Number.isInteger(g) && g >= 0;
    if (f.played && !(goalsOk(f.homeGoals) && goalsOk(f.awayGoals))) p.push(`fixture ${f.id} is played but has no valid score`);
    if (!f.played && (f.homeGoals !== null || f.awayGoals !== null)) p.push(`fixture ${f.id} is unplayed but has a score`);
  }
  for (const t of teams) {
    if (home.get(t) !== 4 || away.get(t) !== 4) p.push(`${t}: ${home.get(t)} home / ${away.get(t)} away fixtures (need 4/4)`);
  }
  if (lambdas.teams.join() !== teams.join()) p.push('team order differs between season and lambdas');
  if (lambdas.asOf !== season.asOf) p.push(`asOf differs: season ${season.asOf}, lambdas ${lambdas.asOf}`);
  return p;
}

/** Every check from the spec's update step; returns human-readable problems (empty = valid). */
export function validateSnapshot(s: Snapshot): string[] {
  const { season, chances } = s;
  const p = validateSimInputs(season, s.lambdas);
  const teams = season.teams.map((t) => t.id);
  const chanceIds = chances.map((c) => c.teamId).sort();
  if (chanceIds.join() !== [...teams].sort().join()) p.push('chances do not cover exactly the season teams');
  if (s.meta.asOf !== season.asOf) p.push(`asOf differs: season ${season.asOf}, meta ${s.meta.asOf}`);

  const sum = (f: (c: Snapshot['chances'][number]) => number) => chances.reduce((a, c) => a + f(c), 0);
  if (Math.abs(sum((c) => c.top8) - 8) > EPS) p.push(`sum of Top 8 is ${sum((c) => c.top8)}, not 8`);
  if (Math.abs(sum((c) => c.top24) - 24) > EPS) p.push(`sum of Top 24 is ${sum((c) => c.top24)}, not 24`);
  if (Math.abs(sum((c) => c.reach.winner) - 1) > EPS) p.push(`sum of winner is ${sum((c) => c.reach.winner)}, not 1`);
  for (const c of chances) {
    const pos = c.position.reduce((a, b) => a + b, 0);
    if (c.position.length !== 36 || Math.abs(pos - 1) > EPS) p.push(`${c.teamId}: position distribution sums to ${pos}`);
  }

  if (s.ratings) {
    const r = s.ratings;
    if (Object.keys(r).sort().join() !== [...teams].sort().join()) p.push('ratings do not cover exactly the season teams');
    for (const [t, v] of Object.entries(r)) if (!Number.isFinite(v)) p.push(`${t}: rating ${v} is not finite`);
  }
  return p;
}

export function validateTeams(teams: TeamsFile, season: Season): string[] {
  const p: string[] = [];
  const seen = new Map<string, string>();
  for (const t of season.teams) {
    const m = teams[t.id];
    if (!m) {
      p.push(`teams.json has no entry for ${t.id}`);
      continue;
    }
    if (!/^[A-Z]{3}$/.test(m.code)) p.push(`${t.id}: code "${m.code}" is not three capital letters`);
    const other = seen.get(m.code);
    if (other) p.push(`duplicate code ${m.code}: ${other} and ${t.id}`);
    seen.set(m.code, t.id);
  }
  return p;
}

export function snapshotLabel(id: string): { label: string; matchday: number | null } {
  if (id === 'live') return { label: 'Live', matchday: null };
  const m = /^md(\d\d)$/.exec(id);
  if (!m) throw new Error(`unknown snapshot id ${id}`);
  const n = Number(m[1]);
  return n === 0 ? { label: 'Before matchday 1', matchday: 0 } : { label: `After matchday ${n}`, matchday: n };
}

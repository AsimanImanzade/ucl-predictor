import type { TeamRecord } from './table.js';
import type { TeamId } from './types.js';

/**
 * Rank the league phase using the UEFA criteria, applied across all tied teams at once
 * (no head-to-head), per the applying-ucl-format-rules skill:
 *   1 pts, 2 gd, 3 gf, 4 away gf, 5 wins, 6 away wins,
 *   7-9 opponents' collective pts / gd / gf (their FINAL records in this same table),
 *   [disciplinary points skipped: no card data exists in simulation],
 *   10 club coefficient, then team id ascending for determinism.
 * Teams missing from `coefficient` count as 0.
 */
export function rankTable(
  records: Map<TeamId, TeamRecord>,
  coefficient: Map<TeamId, number>,
): TeamId[] {
  const n = records.size;
  const ids: TeamId[] = new Array(n);
  const oppPts = new Map<TeamId, number>();
  const oppGd = new Map<TeamId, number>();
  const oppGf = new Map<TeamId, number>();

  let i = 0;
  for (const rec of records.values()) {
    ids[i++] = rec.id;
    let p = 0;
    let d = 0;
    let g = 0;
    const opps = rec.opponents;
    for (let k = 0; k < opps.length; k++) {
      const o = records.get(opps[k]!);
      if (o) {
        p += o.pts;
        d += o.gd;
        g += o.gf;
      }
    }
    oppPts.set(rec.id, p);
    oppGd.set(rec.id, d);
    oppGf.set(rec.id, g);
  }

  ids.sort((x, y) => {
    const a = records.get(x)!;
    const b = records.get(y)!;
    return (
      b.pts - a.pts ||
      b.gd - a.gd ||
      b.gf - a.gf ||
      b.awayGf - a.awayGf ||
      b.won - a.won ||
      b.awayWins - a.awayWins ||
      oppPts.get(y)! - oppPts.get(x)! ||
      oppGd.get(y)! - oppGd.get(x)! ||
      oppGf.get(y)! - oppGf.get(x)! ||
      (coefficient.get(y) ?? 0) - (coefficient.get(x) ?? 0) ||
      (x < y ? -1 : x > y ? 1 : 0)
    );
  });
  return ids;
}

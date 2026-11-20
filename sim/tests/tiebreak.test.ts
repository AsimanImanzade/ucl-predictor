import { describe, expect, it } from 'vitest';
import { buildRecords } from '../src/table.js';
import { rankTable } from '../src/tiebreak.js';

const r = (homeId: string, awayId: string, homeGoals: number, awayGoals: number) => ({
  homeId,
  awayId,
  homeGoals,
  awayGoals,
});
const noCoef = new Map<string, number>();

describe('buildRecords', () => {
  it('computes full stats for a known team', () => {
    const recs = buildRecords(
      ['t', 'a', 'b', 'c', 'e', 'idle'],
      [r('t', 'a', 2, 1), r('b', 't', 0, 0), r('c', 't', 2, 1), r('e', 't', 0, 2)],
    );
    const t = recs.get('t')!;
    expect(t).toMatchObject({
      id: 't',
      played: 4,
      won: 2,
      drawn: 1,
      lost: 1,
      gf: 5,
      ga: 3,
      gd: 2,
      pts: 7,
      awayGf: 3,
      awayWins: 1,
    });
    expect(t.opponents).toEqual(['a', 'b', 'c', 'e']);
    expect(recs.get('idle')).toMatchObject({ played: 0, pts: 0, gd: 0, opponents: [] });
  });
});

describe('rankTable', () => {
  it('orders by points first', () => {
    const recs = buildRecords(['a', 'b', 'c'], [r('a', 'b', 0, 1), r('b', 'c', 1, 1), r('c', 'a', 0, 3)]);
    // a: 3 (W), b: 4 (W, D), c: 1
    expect(rankTable(recs, noCoef)).toEqual(['b', 'a', 'c']);
  });

  it('breaks a three-way tie on pts/gd/gf by away goals across all three', () => {
    const recs = buildRecords(
      ['hi', 'mid', 'low', 'x', 'y'],
      [
        r('hi', 'x', 0, 1),
        r('y', 'hi', 2, 3),
        r('mid', 'x', 1, 0),
        r('y', 'mid', 3, 2),
        r('low', 'x', 2, 0),
        r('y', 'low', 3, 1),
      ],
    );
    for (const id of ['hi', 'mid', 'low']) {
      expect(recs.get(id)).toMatchObject({ pts: 3, gd: 0, gf: 3, won: 1 });
    }
    const order = rankTable(recs, noCoef).filter((id) => id.length > 1 && id !== 'x' && id !== 'y');
    expect(order).toEqual(['hi', 'mid', 'low']); // alphabetical would give hi, low, mid
  });

  it("breaks a tie by opponents' collective points", () => {
    const recs = buildRecords(
      ['aaa', 'zzz', 'weak', 'strong', 't'],
      [r('aaa', 'weak', 1, 0), r('zzz', 'strong', 1, 0), r('strong', 't', 1, 0)],
    );
    const order = rankTable(recs, noCoef);
    expect(order.indexOf('zzz')).toBeLessThan(order.indexOf('aaa'));
  });

  it('breaks a full tie by coefficient, then id; missing coefficient counts as 0', () => {
    const recs = buildRecords(['a', 'b', 'c', 'd'], [
      r('a', 'b', 1, 1),
      r('b', 'a', 1, 1),
      r('c', 'd', 1, 1),
      r('d', 'c', 1, 1),
    ]);
    const coef = new Map([
      ['a', 10],
      ['b', 50],
      ['c', 30],
    ]);
    // draws at home and away: every criterion before coefficient is equal for all four
    const order = rankTable(recs, coef);
    expect(order).toEqual(['b', 'c', 'a', 'd']);
    // equal coefficients fall back to id ascending
    expect(rankTable(recs, noCoef)).toEqual(['a', 'b', 'c', 'd']);
  });
});

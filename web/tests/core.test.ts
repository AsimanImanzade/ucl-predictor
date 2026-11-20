import { describe, expect, it } from 'vitest';
import type { Season } from '@uclpred/sim';
import { certainty } from '../src/lib/certainty';
import { shownDelta } from '../src/lib/delta';
import { matchProbs } from '../src/lib/match';
import { standings } from '../src/lib/standings';
import { makeLambdas, makeSeason } from './fixtures';

/** Replace results so that `winner` wins every match it has played so far. */
function withResults(season: Season, playedThrough: number, score: (homeId: string, awayId: string) => [number, number]): Season {
  return {
    ...season,
    fixtures: season.fixtures.map((f) => {
      const played = f.matchday <= playedThrough;
      const [h, a] = played ? score(f.homeId, f.awayId) : [null, null];
      return { ...f, played, homeGoals: h, awayGoals: a };
    }),
  };
}

describe('standings', () => {
  it('counts P W D L GF GA GD Pts and ranks with the official tiebreaks', () => {
    // Lower id always wins 2-0; equal-strength rule makes t00 top with 2 wins after 2 matchdays.
    const s = withResults(makeSeason(), 2, (h, a) => (h < a ? [2, 0] : [0, 2]));
    const rows = standings(s);
    expect(rows).toHaveLength(36);
    expect(rows.map((r) => r.rank)).toEqual(Array.from({ length: 36 }, (_, i) => i + 1));
    const top = rows[0]!;
    expect(top.teamId).toBe('t00');
    expect(top).toMatchObject({ played: 2, won: 2, drawn: 0, lost: 0, gf: 4, ga: 0, gd: 4, pts: 6 });
    expect(top.form).toEqual(['W', 'W']);
  });

  it('keeps the last five results, oldest first', () => {
    const s = withResults(makeSeason(), 7, () => [1, 1]);
    const r = standings(s).find((x) => x.teamId === 't05')!;
    expect(r.form).toEqual(['D', 'D', 'D', 'D', 'D']);
    expect(r.pts).toBe(7);
  });

  it('before any match everyone is level, ordered by coefficient', () => {
    const rows = standings(makeSeason());
    expect(rows[0]!.teamId).toBe('t00'); // highest coefficient in the fixture
    expect(rows.every((r) => r.played === 0 && r.form.length === 0)).toBe(true);
  });
});

describe('certainty', () => {
  it('nothing is certain before the season', () => {
    expect(certainty(makeSeason(), 't00')).toEqual({});
  });

  it('clinches when no more than 7 (or 23) rivals can still reach its points', () => {
    // t00 wins 7 of 7 (21 pts); every other match is 0-0, so rivals have at most 7 + 3 = 10.
    const s = withResults(makeSeason(), 7, (h, a) => (h === 't00' ? [1, 0] : a === 't00' ? [0, 1] : [0, 0]));
    expect(certainty(s, 't00')).toEqual({ top8: 'clinched', top24: 'clinched' });
    // After one matchday a win guarantees nothing.
    const early = withResults(makeSeason(), 1, (h, a) => (h === 't00' ? [1, 0] : a === 't00' ? [0, 1] : [0, 0]));
    expect(certainty(early, 't00')).toEqual({});
  });

  it('eliminates when enough rivals already have more than its maximum', () => {
    // t01 loses 7 of 7 (max 3 pts); every rival already has at least 6.
    const s = withResults(makeSeason(), 7, (h, a) => (h === 't01' ? [0, 1] : a === 't01' ? [1, 0] : [0, 0]));
    expect(certainty(s, 't01')).toEqual({ top8: 'eliminated', top24: 'eliminated' });
  });

  it('never claims certainty that later results could undo', () => {
    const s = withResults(makeSeason(), 7, () => [0, 0]);
    for (const t of s.teams) expect(certainty(s, t.id)).toEqual({});
  });

  it('uses the final table once all 144 matches are played', () => {
    const s = withResults(makeSeason(), 8, (h, a) => (h < a ? [1, 0] : [0, 1]));
    const rows = standings(s);
    expect(certainty(s, rows[0]!.teamId)).toEqual({ top8: 'clinched', top24: 'clinched' });
    expect(certainty(s, rows[11]!.teamId)).toEqual({ top8: 'eliminated', top24: 'clinched' });
    expect(certainty(s, rows[29]!.teamId)).toEqual({ top8: 'eliminated', top24: 'eliminated' });
  });
});

describe('matchProbs', () => {
  const season = makeSeason();
  const lambdas = makeLambdas(season);
  it('W/D/L sum to 1 and top scores are sorted', () => {
    const m = matchProbs(lambdas, 't00', 't01');
    expect(m.home + m.draw + m.away).toBeCloseTo(1, 9);
    expect(m.top).toHaveLength(3);
    expect(m.top[0]!.p).toBeGreaterThanOrEqual(m.top[1]!.p);
    expect(m.top[1]!.p).toBeGreaterThanOrEqual(m.top[2]!.p);
  });

  it('grid is (maxShown+1)^2 with the tail folded into the last row and column', () => {
    const m = matchProbs(lambdas, 't00', 't01', 5);
    expect(m.grid).toHaveLength(6);
    expect(m.grid.every((r) => r.length === 6)).toBe(true);
    const total = m.grid.flat().reduce((a, b) => a + b, 0);
    expect(total).toBeCloseTo(1, 9);
  });

  it('is oriented: the stronger home side is favoured, and the reverse fixture differs', () => {
    const a = matchProbs(lambdas, 't00', 't35');
    const b = matchProbs(lambdas, 't35', 't00');
    expect(a.home).toBeGreaterThan(a.away);
    expect(b.away).toBeGreaterThan(b.home);
  });
});

describe('shownDelta', () => {
  it('hides changes inside two Monte Carlo standard errors', () => {
    // 20k runs at p = 0.5: se of a difference ~ 0.5 points, threshold ~ 1 point.
    expect(shownDelta(0.505, 0.5, 20000)).toBeNull();
    expect(shownDelta(0.53, 0.5, 20000)).toBeCloseTo(0.03, 12);
    expect(shownDelta(0.47, 0.5, 20000)).toBeCloseTo(-0.03, 12);
  });

  it('shows any change from or to certainty', () => {
    expect(shownDelta(1, 0.999, 20000)).toBeCloseTo(0.001, 12);
    expect(shownDelta(0, 0.002, 20000)).toBeCloseTo(-0.002, 12);
    expect(shownDelta(0, 0, 20000)).toBeNull();
  });
});

describe('snapshotBefore', () => {
  it('picks the latest snapshot taken strictly before kickoff', async () => {
    const { snapshotBefore } = await import('../src/lib/data');
    const m = {
      season: '2026-27', model: 'm', updatedAt: '', liveId: 'live',
      snapshots: [
        { id: 'md00', label: '', matchday: 0, asOf: '2026-09-07T00:00:00Z', file: '' },
        { id: 'md01', label: '', matchday: 1, asOf: '2026-09-11T00:00:00Z', file: '' },
        { id: 'live', label: '', matchday: null, asOf: '2026-11-10T16:05:46Z', file: '' },
      ],
    };
    expect(snapshotBefore(m, '2026-09-08T16:45:00Z')).toBe('md00');
    expect(snapshotBefore(m, '2026-10-13T16:45:00Z')).toBe('md01');
    expect(snapshotBefore(m, '2026-11-24T17:45:00Z')).toBe('live');
    expect(snapshotBefore(m, '2026-09-01T00:00:00Z')).toBeNull();
  });
});

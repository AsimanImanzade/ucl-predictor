import { describe, expect, it } from 'vitest';
import { createRng } from '../src/rng.js';
import { drawBracket, drawPlayoffs } from '../src/bracket.js';
import { playFinal, playTwoLegged, type MatchSampler } from '../src/tie.js';
import type { LambdaPair } from '../src/types.js';

const ranking = Array.from({ length: 36 }, (_, i) => `t${i + 1}`);
const pos = (id: string) => Number(id.slice(1));

describe('drawPlayoffs', () => {
  it('pairs seeded pairs with the matching unseeded pairs, in line order', () => {
    const rng = createRng(1);
    const seenOpp9 = new Set<number>();
    for (let n = 0; n < 10000; n++) {
      const ties = drawPlayoffs(ranking, rng);
      expect(ties).toHaveLength(8);
      const lines: [number[], number[]][] = [
        [[9, 10], [23, 24]], [[11, 12], [21, 22]], [[13, 14], [19, 20]], [[15, 16], [17, 18]],
      ];
      lines.forEach(([s, u], l) => {
        for (const k of [2 * l, 2 * l + 1]) {
          expect(s).toContain(pos(ties[k]!.seeded));
          expect(u).toContain(pos(ties[k]!.unseeded));
        }
        expect(new Set([ties[2 * l]!.seeded, ties[2 * l + 1]!.seeded]).size).toBe(2);
        expect(new Set([ties[2 * l]!.unseeded, ties[2 * l + 1]!.unseeded]).size).toBe(2);
        expect(pos(ties[2 * l]!.seeded)).toBe(s[0]);
      });
      const t9 = ties.find((t) => t.seeded === 't9')!;
      seenOpp9.add(pos(t9.unseeded));
      const t15 = ties.find((t) => t.seeded === 't15')!;
      expect([17, 18]).toContain(pos(t15.unseeded));
    }
    expect([...seenOpp9].sort()).toEqual([23, 24]);
  });
});

describe('drawBracket', () => {
  it('splits pairs across halves and interleaves seeds per slot', () => {
    const rng = createRng(2);
    const lineOf: Record<number, number[]> = { 1: [6, 7], 2: [6, 7], 3: [4, 5], 4: [4, 5], 5: [2, 3], 6: [2, 3], 7: [0, 1], 8: [0, 1] };
    for (let n = 0; n < 10000; n++) {
      const slots = drawBracket(ranking, rng);
      expect(slots).toHaveLength(8);
      const where = new Map(slots.map((s, i) => [pos(s.top), i]));
      for (const [a, b] of [[1, 2], [3, 4], [5, 6], [7, 8]] as const) {
        expect(Math.floor(where.get(a)! / 4)).not.toBe(Math.floor(where.get(b)! / 4));
      }
      for (let h = 0; h < 2; h++) {
        const g = (k: number) => pos(slots[h * 4 + k]!.top);
        expect([1, 2]).toContain(g(0));
        expect([7, 8]).toContain(g(1));
        expect([3, 4]).toContain(g(2));
        expect([5, 6]).toContain(g(3));
      }
      for (const s of slots) expect(lineOf[pos(s.top)]).toContain(s.playoffTie);
      for (const [a, b] of [[1, 2], [3, 4], [5, 6], [7, 8]] as const) {
        expect(slots[where.get(a)!]!.playoffTie).not.toBe(slots[where.get(b)!]!.playoffTie);
      }
    }
  });
});

function stub(scores: [number, number][], lam: LambdaPair = [1.5, 1]) {
  const calls: { a: string; b: string; venue: string }[] = [];
  let i = 0;
  const sampler: MatchSampler = {
    sample(a, b, venue) {
      calls.push({ a, b, venue });
      return scores[i++]!;
    },
    lambda: () => lam,
  };
  return { sampler, calls };
}

describe('playTwoLegged', () => {
  it('level aggregate ignores away goals and goes to extra time/penalties', () => {
    // leg1: A 1-0 B; leg2: B 1-0 A => level 1-1
    const winners = new Set<string>();
    for (let s = 1; s <= 200; s++) {
      const { sampler, calls } = stub([[1, 0], [1, 0]], [0, 0]); // 1-1 agg; lambda 0: no ET goals
      winners.add(playTwoLegged('A', 'B', sampler, createRng(s)));
      expect(calls).toEqual([
        { a: 'A', b: 'B', venue: 'home' },
        { a: 'B', b: 'A', venue: 'home' },
      ]);
    }
    expect(winners).toEqual(new Set(['A', 'B'])); // penalties 50/50
  });

  it('away goals do not decide: team with more away goals can lose on penalties', () => {
    // leg1 A 2-1 B; leg2 B 1-0 A => 2-2 agg, B has the away goal; still pens
    const winners = new Set<string>();
    for (let s = 1; s <= 200; s++) {
      const { sampler } = stub([[2, 1], [1, 0]], [0, 0]);
      winners.add(playTwoLegged('A', 'B', sampler, createRng(s)));
    }
    expect(winners.size).toBe(2);
  });

  it('decides on aggregate without extra time when not level', () => {
    const { sampler } = stub([[1, 0], [0, 0]]);
    expect(playTwoLegged('A', 'B', sampler, createRng(1))).toBe('A');
  });
});

describe('playFinal', () => {
  it('venue team a hosts at home', () => {
    const { sampler, calls } = stub([[2, 1]]);
    expect(playFinal('A', 'B', 'A', sampler, createRng(1))).toBe('A');
    expect(calls).toEqual([{ a: 'A', b: 'B', venue: 'home' }]);
  });
  it('venue team b hosts at home with b as host', () => {
    const { sampler, calls } = stub([[1, 2]]);
    expect(playFinal('A', 'B', 'B', sampler, createRng(1))).toBe('A');
    expect(calls).toEqual([{ a: 'B', b: 'A', venue: 'home' }]);
  });
  it('neutral otherwise', () => {
    const { sampler, calls } = stub([[0, 1]]);
    expect(playFinal('A', 'B', null, sampler, createRng(1))).toBe('B');
    expect(calls).toEqual([{ a: 'A', b: 'B', venue: 'neutral' }]);
  });
});

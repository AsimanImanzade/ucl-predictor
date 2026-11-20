import type { TeamId } from './types.js';

type Rng = () => number;

export interface PlayoffTie {
  seeded: TeamId;
  unseeded: TeamId;
}

export interface R16Slot {
  top: TeamId;
  /** Index (0..7) into the drawPlayoffs output. */
  playoffTie: number;
}

/** Lines A..D: [first seeded position, first unseeded position] (1-based, pairs of two). */
const LINES: readonly [number, number][] = [
  [9, 23],
  [11, 21],
  [13, 19],
  [15, 17],
];

/** Top-8 pairs in per-half slot order, with the play-off line (A=0..D=3) each one meets. */
const SLOT_PAIRS: readonly [number, number][] = [
  [1, 3], // {1,2} v line D
  [7, 0], // {7,8} v line A
  [3, 2], // {3,4} v line C
  [5, 1], // {5,6} v line B
];

/** 8 play-off ties in line order A,A,B,B,C,C,D,D; one coin flip per line picks the pairing. */
export function drawPlayoffs(ranking: TeamId[], rng: Rng): PlayoffTie[] {
  const ties: PlayoffTie[] = [];
  for (const [s, u] of LINES) {
    const s1 = ranking[s - 1]!;
    const s2 = ranking[s]!;
    const u1 = ranking[u - 1]!;
    const u2 = ranking[u]!;
    if (rng() < 0.5) {
      ties.push({ seeded: s1, unseeded: u1 }, { seeded: s2, unseeded: u2 });
    } else {
      ties.push({ seeded: s1, unseeded: u2 }, { seeded: s2, unseeded: u1 });
    }
  }
  return ties;
}

/** 8 R16 slots in bracket order (0-3 half 1, 4-7 half 2; QF = (0,1),(2,3),(4,5),(6,7)). */
export function drawBracket(ranking: TeamId[], rng: Rng): R16Slot[] {
  const slots: R16Slot[] = new Array<R16Slot>(8);
  for (let k = 0; k < 4; k++) {
    const [p, line] = SLOT_PAIRS[k]!;
    const x = ranking[p - 1]!;
    const y = ranking[p]!;
    const swapTies = rng() < 0.5; // which top seed takes which tie of the line
    const swapHalves = rng() < 0.5; // which half the first seed goes to
    const tx = 2 * line + (swapTies ? 1 : 0);
    const ty = 2 * line + (swapTies ? 0 : 1);
    slots[swapHalves ? 4 + k : k] = { top: x, playoffTie: tx };
    slots[swapHalves ? k : 4 + k] = { top: y, playoffTie: ty };
  }
  return slots;
}

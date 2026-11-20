import { describe, expect, it } from 'vitest';
import { rps } from '../src/lib/accuracy';

describe('rps', () => {
  it('is 0 for a certain correct forecast and 1 for a certain wrong extreme', () => {
    expect(rps([1, 0, 0], 0)).toBe(0);
    expect(rps([1, 0, 0], 2)).toBe(1);
  });
  it('matches the hand-computed value', () => {
    // p = (0.5, 0.3, 0.2), draw: cum p (0.5, 0.8), cum o (0, 1) -> 0.5 * (0.25 + 0.04) = 0.145
    expect(rps([0.5, 0.3, 0.2], 1)).toBeCloseTo(0.145, 12);
  });
});

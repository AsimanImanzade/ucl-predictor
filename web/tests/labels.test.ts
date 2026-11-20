import { describe, expect, it } from 'vitest';
import { progressLabel } from '../src/lib/labels';
import { makeSeason } from './fixtures';

describe('progressLabel', () => {
  it('names where the league phase stands', () => {
    expect(progressLabel(makeSeason(0))).toBe('Before matchday 1');
    expect(progressLabel(makeSeason(4))).toBe('After matchday 4');
    expect(progressLabel(makeSeason(8))).toBe('League phase complete');
  });

  it('reports a matchday in progress', () => {
    const s = makeSeason(4);
    const md5 = s.fixtures.filter((f) => f.matchday === 5);
    for (const f of md5.slice(0, 9)) Object.assign(f, { played: true, homeGoals: 1, awayGoals: 0 });
    expect(progressLabel(s)).toBe('During matchday 5 (9 of 18 played)');
  });
});

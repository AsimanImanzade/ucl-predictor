import { describe, expect, it } from 'vitest';
import { FALLBACK_COLOR, parseClubColors } from '../src/lib/teamColors';

describe('parseClubColors', () => {
  it('maps football-data colour names to hex, in order', () => {
    expect(parseClubColors('Black / Yellow')).toEqual(['#15171c', '#f5c400']);
    expect(parseClubColors('Claret / Sky Blue')).toEqual(['#7b1e3a', '#78b7e6']);
  });

  it('keeps at most two colours for the chip', () => {
    expect(parseClubColors('Red / Navy Blue / Orange')).toHaveLength(2);
  });

  it('skips unknown names and falls back to a neutral chip', () => {
    expect(parseClubColors('Teal / Red')).toEqual(['#d01f2f']);
    expect(parseClubColors(null)).toEqual([FALLBACK_COLOR]);
    expect(parseClubColors('')).toEqual([FALLBACK_COLOR]);
  });

  it('is case and space tolerant', () => {
    expect(parseClubColors(' sky blue /WHITE ')).toEqual(['#78b7e6', '#f4f6fa']);
  });
});

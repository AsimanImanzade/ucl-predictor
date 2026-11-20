import { describe, expect, it } from 'vitest';
import { applyGuesses, decodeGuesses, encodeGuesses, loadGuesses, reconcile, saveGuesses, STORAGE_KEY } from '../src/lib/scenario';
import { makeSeason } from './fixtures';

function memoryStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() {
      return m.size;
    },
    clear: () => m.clear(),
    getItem: (k) => m.get(k) ?? null,
    key: (i) => [...m.keys()][i] ?? null,
    removeItem: (k) => void m.delete(k),
    setItem: (k, v) => void m.set(k, String(v)),
  };
}

const throwing: Storage = {
  length: 0,
  clear() {},
  key: () => null,
  getItem() {
    throw new Error('blocked');
  },
  setItem() {
    throw new Error('blocked');
  },
  removeItem() {
    throw new Error('blocked');
  },
};

describe('reconcile', () => {
  it('drops a guess for a fixture that has since been played and reports the real score', () => {
    const season = makeSeason(4);
    const md5 = season.fixtures.filter((f) => f.matchday === 5);
    const a = md5[0]!;
    const b = md5[1]!;
    const saved = { [a.id]: { homeGoals: 2, awayGoals: 1 }, [b.id]: { homeGoals: 0, awayGoals: 0 } };
    // The real match a is played after the guess was saved.
    Object.assign(a, { played: true, homeGoals: 3, awayGoals: 3 });
    const { kept, dropped } = reconcile(saved, season);
    expect(kept).toEqual({ [b.id]: { homeGoals: 0, awayGoals: 0 } });
    expect(dropped).toEqual([{ fixtureId: a.id, guess: { homeGoals: 2, awayGoals: 1 }, actual: { homeGoals: 3, awayGoals: 3 } }]);
  });

  it('silently discards unknown fixtures and impossible scores', () => {
    const season = makeSeason(0);
    const f = season.fixtures[0]!;
    const { kept, dropped } = reconcile({ 999999: { homeGoals: 1, awayGoals: 0 }, [f.id]: { homeGoals: -1, awayGoals: 0 } }, season);
    expect(kept).toEqual({});
    expect(dropped).toEqual([]);
  });
});

describe('share encoding', () => {
  it('round-trips, sorted by fixture id', () => {
    const g = { 575396: { homeGoals: 0, awayGoals: 0 }, 575395: { homeGoals: 2, awayGoals: 1 } };
    const s = encodeGuesses(g);
    expect(s).toBe('575395:2-1,575396:0-0');
    expect(decodeGuesses(s)).toEqual(g);
  });

  it('ignores malformed entries', () => {
    expect(decodeGuesses('575395:2-1,bad,1:x-1,2:1-1-1,3:4-')).toEqual({ 575395: { homeGoals: 2, awayGoals: 1 } });
    expect(decodeGuesses(null)).toEqual({});
    expect(decodeGuesses('')).toEqual({});
  });
});

describe('storage', () => {
  it('saves and loads guesses; an empty scenario removes the key', () => {
    const st = memoryStorage();
    saveGuesses({ 5: { homeGoals: 1, awayGoals: 2 } }, st);
    expect(loadGuesses(st)).toEqual({ 5: { homeGoals: 1, awayGoals: 2 } });
    saveGuesses({}, st);
    expect(st.getItem(STORAGE_KEY)).toBeNull();
  });

  it('survives blocked or corrupt storage', () => {
    expect(loadGuesses(throwing)).toEqual({});
    expect(() => saveGuesses({ 5: { homeGoals: 1, awayGoals: 2 } }, throwing)).not.toThrow();
    const st = memoryStorage();
    st.setItem(STORAGE_KEY, '{not json');
    expect(loadGuesses(st)).toEqual({});
    st.setItem(STORAGE_KEY, JSON.stringify({ 5: { homeGoals: 'two', awayGoals: 1 }, 6: { homeGoals: 1, awayGoals: 1 } }));
    expect(loadGuesses(st)).toEqual({ 6: { homeGoals: 1, awayGoals: 1 } });
  });
});

describe('applyGuesses', () => {
  it('plays guessed fixtures that are still unplayed and leaves real results alone', () => {
    const season = makeSeason(1);
    const played = season.fixtures[0]!;
    const open = season.fixtures.find((f) => !f.played)!;
    const out = applyGuesses(season, { [played.id]: { homeGoals: 9, awayGoals: 9 }, [open.id]: { homeGoals: 4, awayGoals: 0 } });
    expect(out.fixtures.find((f) => f.id === played.id)).toEqual(played);
    expect(out.fixtures.find((f) => f.id === open.id)).toMatchObject({ played: true, homeGoals: 4, awayGoals: 0 });
    expect(open.played).toBe(false); // input not mutated
  });
});

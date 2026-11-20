import type { Overrides, Season } from '@uclpred/sim';

export interface Guess {
  homeGoals: number;
  awayGoals: number;
}

/** Fixture id -> guessed score; the same shape as the simulator's overrides. */
export type Guesses = Overrides;

export interface DroppedGuess {
  fixtureId: number;
  guess: Guess;
  actual: Guess;
}

export const STORAGE_KEY = 'floodlit:what-if:2026-27';
export const MAX_GOALS = 15;

const validGoals = (g: unknown): g is number => typeof g === 'number' && Number.isInteger(g) && g >= 0 && g <= MAX_GOALS;
const validGuess = (g: unknown): g is Guess =>
  typeof g === 'object' && g !== null && validGoals((g as Guess).homeGoals) && validGoals((g as Guess).awayGoals);

/**
 * Played fixtures lock automatically: a saved guess for a match that has since been played
 * is dropped (and reported, so the page can say so). Unknown fixtures and impossible scores
 * are discarded silently.
 */
export function reconcile(saved: Guesses, season: Season): { kept: Guesses; dropped: DroppedGuess[] } {
  const byId = new Map(season.fixtures.map((f) => [f.id, f]));
  const kept: Guesses = {};
  const dropped: DroppedGuess[] = [];
  for (const [key, guess] of Object.entries(saved)) {
    const f = byId.get(Number(key));
    if (!f || !validGuess(guess)) continue;
    if (f.played && f.homeGoals !== null && f.awayGoals !== null) {
      dropped.push({ fixtureId: f.id, guess: { homeGoals: guess.homeGoals, awayGoals: guess.awayGoals }, actual: { homeGoals: f.homeGoals, awayGoals: f.awayGoals } });
      continue;
    }
    kept[f.id] = { homeGoals: guess.homeGoals, awayGoals: guess.awayGoals };
  }
  return { kept, dropped };
}

/** "575395:2-1,575396:0-0", sorted by fixture id: short enough for a share link. */
export function encodeGuesses(g: Guesses): string {
  return Object.entries(g)
    .map(([id, s]) => [Number(id), s] as const)
    .sort((a, b) => a[0] - b[0])
    .map(([id, s]) => `${id}:${s.homeGoals}-${s.awayGoals}`)
    .join(',');
}

export function decodeGuesses(s: string | null): Guesses {
  const out: Guesses = {};
  for (const part of (s ?? '').split(',')) {
    const m = /^(\d+):(\d{1,2})-(\d{1,2})$/.exec(part.trim());
    if (!m) continue;
    const guess = { homeGoals: Number(m[2]), awayGoals: Number(m[3]) };
    if (validGuess(guess)) out[Number(m[1])] = guess;
  }
  return out;
}

const defaultStorage = (): Storage | undefined => {
  try {
    return globalThis.localStorage;
  } catch {
    return undefined;
  }
};

export function loadGuesses(storage: Storage | undefined = defaultStorage()): Guesses {
  try {
    const raw = storage?.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== 'object' || parsed === null) return {};
    const out: Guesses = {};
    for (const [k, v] of Object.entries(parsed)) if (/^\d+$/.test(k) && validGuess(v)) out[Number(k)] = { homeGoals: v.homeGoals, awayGoals: v.awayGoals };
    return out;
  } catch {
    return {};
  }
}

/** Best effort: private windows and blocked storage just mean the scenario is not remembered. */
export function saveGuesses(g: Guesses, storage: Storage | undefined = defaultStorage()): void {
  try {
    if (Object.keys(g).length === 0) storage?.removeItem(STORAGE_KEY);
    else storage?.setItem(STORAGE_KEY, JSON.stringify(g));
  } catch {
    /* not remembered */
  }
}

/** The season as if the guesses had happened (for the scenario points table). */
export function applyGuesses(season: Season, g: Guesses): Season {
  return {
    ...season,
    fixtures: season.fixtures.map((f) => {
      const guess = g[f.id];
      return !f.played && guess ? { ...f, played: true, homeGoals: guess.homeGoals, awayGoals: guess.awayGoals } : f;
    }),
  };
}

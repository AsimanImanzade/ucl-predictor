import { useEffect, useRef, useState } from 'react';
import type { Fixture } from '@uclpred/sim';
import { LIVE_URL } from './config';

/**
 * Live scores from the `live/` Worker: display only. Odds and the table come from
 * live.json, which counts finished games once the update workflow has run.
 */
export type LiveStatus = 'IN_PLAY' | 'PAUSED' | 'FINISHED';
export interface LiveScore {
  status: LiveStatus;
  home: number;
  away: number;
}
export type LiveScores = ReadonlyMap<number, LiveScore>;

export const LIVE_WINDOW_MS = 150 * 60_000;
export const POLL_MS = 60_000;
/** A late or long game keeps polling up to kickoff + 4h while its held score is not final. */
const OVERRUN_MS = 90 * 60_000;
const STATUSES = new Set<string>(['IN_PLAY', 'PAUSED', 'FINISHED']);
const EMPTY: LiveScores = new Map();

/** Any game not yet counted whose kickoff..kickoff+2h30 window contains `now`. */
export function inLiveWindow(fixtures: readonly Fixture[], now: number): boolean {
  return fixtures.some((f) => {
    if (f.played) return false;
    const ko = Date.parse(f.utcDate);
    return ko <= now && now < ko + LIVE_WINDOW_MS;
  });
}

const goals = (n: unknown): n is number => Number.isInteger(n) && (n as number) >= 0;

export function parseLive(json: unknown): Map<number, LiveScore> {
  const out = new Map<number, LiveScore>();
  const matches = (json as { matches?: unknown } | null)?.matches;
  if (!Array.isArray(matches)) return out;
  for (const m of matches as Record<string, unknown>[]) {
    if (typeof m?.id === 'number' && typeof m.status === 'string' && STATUSES.has(m.status) && goals(m.home) && goals(m.away)) {
      out.set(m.id, { status: m.status as LiveStatus, home: m.home, away: m.away });
    }
  }
  return out;
}

/** Polls once a minute while a game is in its window and the tab is visible. */
export function useLiveScores(fixtures: readonly Fixture[], url: string = LIVE_URL): LiveScores {
  const [scores, setScores] = useState<LiveScores>(EMPTY);
  // A ref, not an effect dependency: a new array each render must not restart polling.
  const fixturesRef = useRef(fixtures);
  const scoresRef = useRef(scores);
  useEffect(() => {
    fixturesRef.current = fixtures;
    scoresRef.current = scores;
  });
  useEffect(() => {
    if (!url) return;
    let alive = true;
    let busy = false;
    let lastAt = -Infinity;
    const active = (now: number) => {
      const fx = fixturesRef.current;
      if (inLiveWindow(fx, now)) return true;
      const running = [...scoresRef.current.values()].some((s) => s.status !== 'FINISHED');
      return running && inLiveWindow(fx, now - OVERRUN_MS);
    };
    const poll = async () => {
      if (busy || document.visibilityState === 'hidden' || !active(Date.now())) return;
      busy = true;
      lastAt = Date.now();
      try {
        // A hung request would leave `busy` set and stop polling.
        const res = await fetch(url, { signal: AbortSignal.timeout(15_000) });
        if (res.ok) {
          const next = parseLive(await res.json());
          if (alive) setScores(next);
        }
      } catch {
        // Offline or the Worker is down: keep the last scores.
      } finally {
        busy = false;
      }
    };
    const onVisible = () => {
      if (document.visibilityState === 'visible' && Date.now() - lastAt >= 30_000) void poll();
    };
    void poll();
    const timer = setInterval(() => void poll(), POLL_MS);
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      alive = false;
      clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [url]);
  return scores;
}

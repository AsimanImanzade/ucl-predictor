import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, renderHook, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import type { Fixture } from '@uclpred/sim';
import { FixtureRow } from '../src/components/FixtureRow';
import { inLiveWindow, parseLive, useLiveScores, type LiveScore } from '../src/lib/liveScores';
import { makeSnapshot, makeTeams } from './fixtures';

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.resetModules();
  vi.doUnmock('../src/lib/data');
  vi.doUnmock('../src/lib/liveScores');
});

const KO = '2026-11-25T20:00:00Z';
const at = (iso: string) => Date.parse(iso);
const fx = (over: Partial<Fixture> = {}): Fixture => ({
  id: 7, matchday: 5, utcDate: KO, homeId: 't00', awayId: 't01', played: false, homeGoals: null, awayGoals: null, ...over,
});

describe('inLiveWindow', () => {
  it('is true from kickoff until 2h30 after it, for unplayed games only', () => {
    expect(inLiveWindow([fx()], at('2026-11-25T19:59:59Z'))).toBe(false);
    expect(inLiveWindow([fx()], at(KO))).toBe(true);
    expect(inLiveWindow([fx()], at('2026-11-25T22:29:59Z'))).toBe(true);
    expect(inLiveWindow([fx()], at('2026-11-25T22:30:00Z'))).toBe(false);
    expect(inLiveWindow([fx({ played: true, homeGoals: 1, awayGoals: 0 })], at('2026-11-25T21:00:00Z'))).toBe(false);
  });
});

describe('parseLive', () => {
  it('keeps well-formed entries by fixture id and drops the rest', () => {
    const m = parseLive({
      matches: [
        { id: 1, status: 'IN_PLAY', home: 1, away: 0 },
        { id: 2, status: 'PAUSED', home: 0, away: 0 },
        { id: 3, status: 'FINISHED', home: 2, away: 2 },
        { id: 4, status: 'TIMED', home: null, away: null },
        { id: 5, status: 'IN_PLAY', home: null, away: 0 },
        { id: '6', status: 'IN_PLAY', home: 1, away: 1 },
      ],
    });
    expect([...m.keys()]).toEqual([1, 2, 3]);
    expect(m.get(2)).toEqual({ status: 'PAUSED', home: 0, away: 0 });
    expect(parseLive(null).size).toBe(0);
    expect(parseLive({ matches: 'x' }).size).toBe(0);
  });
});

describe('useLiveScores', () => {
  const LIVE = 'https://live.example/';
  const reply = (matches: unknown[]) => vi.fn(async (_url: string) => new Response(JSON.stringify({ matches })));

  // Fake only the clock and the interval: Response.json() needs the real setTimeout/setImmediate.
  const fakeClock = (iso: string) => vi.useFakeTimers({ now: at(iso), toFake: ['setInterval', 'clearInterval', 'Date'] });

  /** Moves the fake clock, then yields one real macrotask so fetch and json() settle. */
  async function tick(ms = 0) {
    await act(async () => {
      vi.advanceTimersByTime(ms);
      await new Promise((r) => setTimeout(r, 0));
    });
  }

  function setVisibility(state: 'visible' | 'hidden') {
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => state });
    document.dispatchEvent(new Event('visibilitychange'));
  }

  it('polls every 60 s inside the window, pauses while the tab is hidden, and catches up on return', async () => {
    fakeClock('2026-11-25T20:10:00Z');
    setVisibility('visible');
    const fetchMock = reply([{ id: 7, status: 'IN_PLAY', home: 1, away: 0 }]);
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useLiveScores([fx()], LIVE));
    await tick(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]![0]).toBe(LIVE);
    expect(result.current.get(7)).toEqual({ status: 'IN_PLAY', home: 1, away: 0 });

    await tick(60_000);
    expect(fetchMock).toHaveBeenCalledTimes(2);

    setVisibility('hidden');
    await tick(180_000);
    expect(fetchMock).toHaveBeenCalledTimes(2);

    await act(async () => setVisibility('visible'));
    await tick(0);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it('makes no request outside every window or without an endpoint', async () => {
    fakeClock('2026-11-25T18:00:00Z');
    setVisibility('visible');
    const fetchMock = reply([]);
    vi.stubGlobal('fetch', fetchMock);
    const first = renderHook(() => useLiveScores([fx()], LIVE));
    await tick(60_000);
    expect(fetchMock).not.toHaveBeenCalled();
    // Kickoff arrives while the page is open: polling starts on the next tick.
    await tick(2 * 3600_000);
    expect(fetchMock).toHaveBeenCalled();
    first.unmount();

    const none = reply([]);
    vi.stubGlobal('fetch', none);
    vi.setSystemTime(at('2026-11-25T20:10:00Z'));
    renderHook(() => useLiveScores([fx()], ''));
    await tick(120_000);
    expect(none).not.toHaveBeenCalled();
  });

  it('keeps polling past the window while a held score is still running, then stops once it is finished', async () => {
    fakeClock('2026-11-25T22:20:00Z');
    setVisibility('visible');
    let status = 'IN_PLAY';
    const fetchMock = vi.fn(async (_url: string) => new Response(JSON.stringify({ matches: [{ id: 7, status, home: 2, away: 2 }] })));
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useLiveScores([fx()], LIVE));
    await tick(0);
    await tick(20 * 60_000); // 22:40, window closed at 22:30 but the game still runs
    const calls = fetchMock.mock.calls.length;
    expect(result.current.get(7)?.status).toBe('IN_PLAY');
    status = 'FINISHED';
    await tick(60_000);
    expect(fetchMock.mock.calls.length).toBe(calls + 1);
    expect(result.current.get(7)?.status).toBe('FINISHED');
    await tick(5 * 60_000);
    expect(fetchMock.mock.calls.length).toBe(calls + 1);
  });

  it('keeps the last scores when a poll fails', async () => {
    fakeClock('2026-11-25T20:10:00Z');
    setVisibility('visible');
    vi.stubGlobal('fetch', reply([{ id: 7, status: 'IN_PLAY', home: 1, away: 0 }]));
    const { result } = renderHook(() => useLiveScores([fx()], LIVE));
    await tick(0);
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('offline'); }));
    await tick(60_000);
    expect(result.current.get(7)?.home).toBe(1);
  });
});

describe('live badges', () => {
  const snap = makeSnapshot(4);
  const teams = makeTeams(snap.season);
  const open = snap.season.fixtures.find((f) => !f.played)!;
  const done = snap.season.fixtures.find((f) => f.played)!;
  const row = (f: Fixture, live?: LiveScore) =>
    render(
      <MemoryRouter>
        <ul>
          <FixtureRow fixture={f} teams={teams} lambdas={snap.lambdas} live={live} />
        </ul>
      </MemoryRouter>,
    );

  it('shows LIVE with the current score and keeps the pre-match odds', () => {
    const { container } = row(open, { status: 'IN_PLAY', home: 2, away: 1 });
    expect(container.querySelector('.live-badge--live')?.textContent).toMatch(/LIVE/);
    expect(container.querySelector('.fx__score')?.textContent).toBe('2–1');
    expect(container.querySelector('.wdl')).not.toBeNull();
    expect(screen.getByRole('link').getAttribute('aria-label')).toMatch(/live score 2–1/);
  });

  it('shows HT at half time and FT once football-data has it but live.json does not', () => {
    row(open, { status: 'PAUSED', home: 0, away: 0 });
    expect(screen.getByText('HT')).toBeTruthy();
    expect(screen.getByText('Half time')).toBeTruthy();
    cleanup();
    const { container } = row(open, { status: 'FINISHED', home: 3, away: 3 });
    expect(container.querySelector('.live-badge--ft')?.textContent).toMatch(/FT/);
    expect(container.querySelector('.fx__score')?.textContent).toBe('3–3');
  });

  it('ignores the feed for games live.json already counts', () => {
    const { container } = row(done, { status: 'FINISHED', home: 9, away: 9 });
    expect(container.querySelector('.live-badge')).toBeNull();
    expect(container.querySelector('.fx__score')?.textContent).toBe(`${done.homeGoals}–${done.awayGoals}`);
  });

  it('Match page scoreboard shows the live score and says the forecast waits for full time', async () => {
    const manifest = {
      season: '2026-27', model: 'test', updatedAt: snap.meta.asOf, liveId: 'live',
      snapshots: [{ id: 'live', label: 'Live', matchday: null, asOf: snap.meta.asOf, file: 'live.json' }],
    };
    vi.doMock('../src/lib/data', () => ({
      useManifest: () => manifest,
      useSnapshot: () => snap,
      useTeams: () => teams,
      snapshotBefore: () => null,
    }));
    vi.doMock('../src/lib/liveScores', async (orig) => ({
      ...(await orig<typeof import('../src/lib/liveScores')>()),
      useLiveScores: () => new Map([[open.id, { status: 'IN_PLAY', home: 1, away: 0 }]]),
    }));
    vi.resetModules();
    const { MatchPage } = await import('../src/pages/MatchPage');
    const { container } = render(
      <MemoryRouter initialEntries={[`/match/${open.id}`]}>
        <Routes>
          <Route path="match/:id" element={<MatchPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(container.querySelector('.scoreboard__score')?.textContent).toBe('1–0');
    expect(container.querySelector('.scoreboard .live-badge--live')).not.toBeNull();
    expect(screen.getByText(/forecast updates after full time/i)).toBeTruthy();
    expect(screen.getByText('Forecast')).toBeTruthy();
  });
});

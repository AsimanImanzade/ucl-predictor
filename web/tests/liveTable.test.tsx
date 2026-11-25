import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { STORAGE_KEY } from '../src/lib/scenario';
import type { TeamChances } from '@uclpred/sim';
import { StandingsTable } from '../src/components/StandingsTable';
import { asItStands, playingNow, withLive } from '../src/lib/liveTable';
import type { LiveScore } from '../src/lib/liveScores';
import { standings } from '../src/lib/standings';
import { makeSnapshot, makeTeams } from './fixtures';

afterEach(() => {
  cleanup();
  vi.resetModules();
  vi.doUnmock('../src/lib/data');
  vi.doUnmock('../src/lib/liveScores');
  vi.doUnmock('../src/lib/useScenarioSim');
  localStorage.clear();
});

const snap = makeSnapshot(4);
const teams = makeTeams(snap.season);
const open = snap.season.fixtures.filter((f) => !f.played);
const done = snap.season.fixtures.find((f) => f.played)!;
const [a, b, c] = [open[0]!, open[1]!, open[2]!];
const live = (status: LiveScore['status'], home: number, away: number): LiveScore => ({ status, home, away });

describe('withLive', () => {
  it('fills games in play with the live score unless the user typed one; full time locks the real score', () => {
    const scores = new Map([
      [a.id, live('IN_PLAY', 1, 0)],
      [b.id, live('PAUSED', 0, 0)],
      [c.id, live('FINISHED', 2, 2)],
      [done.id, live('FINISHED', 9, 9)],
    ]);
    const user = { [b.id]: { homeGoals: 3, awayGoals: 0 }, [c.id]: { homeGoals: 0, awayGoals: 5 }, [open[3]!.id]: { homeGoals: 1, awayGoals: 1 } };
    expect(withLive(user, snap.season, scores)).toEqual({
      [a.id]: { homeGoals: 1, awayGoals: 0 },
      [b.id]: { homeGoals: 3, awayGoals: 0 },
      [c.id]: { homeGoals: 2, awayGoals: 2 },
      [open[3]!.id]: { homeGoals: 1, awayGoals: 1 },
    });
  });

  it('is the user guesses unchanged when nothing is live', () => {
    const user = { [a.id]: { homeGoals: 1, awayGoals: 1 } };
    expect(withLive(user, snap.season, new Map())).toEqual(user);
  });
});

describe('as it stands', () => {
  it('counts games in progress in points and goals, and lists the clubs playing now', () => {
    const scores = new Map([[a.id, live('IN_PLAY', 2, 0)], [b.id, live('FINISHED', 1, 1)]]);
    const before = new Map(standings(snap.season).map((r) => [r.teamId, r]));
    const after = new Map(standings(asItStands(snap.season, scores)).map((r) => [r.teamId, r]));
    expect(after.get(a.homeId)!.pts).toBe(before.get(a.homeId)!.pts + 3);
    expect(after.get(a.homeId)!.gf).toBe(before.get(a.homeId)!.gf + 2);
    expect(after.get(a.awayId)!.ga).toBe(before.get(a.awayId)!.ga + 2);
    expect(after.get(b.homeId)!.pts).toBe(before.get(b.homeId)!.pts + 1);
    expect([...playingNow(snap.season, scores)].sort()).toEqual([a.homeId, a.awayId].sort());
  });
});

describe('tables', () => {
  const chances = new Map<string, TeamChances>(snap.chances.map((x) => [x.teamId, x]));

  it('the compact What-if table keeps GF, GA and GD', () => {
    const { container } = render(
      <MemoryRouter>
        <StandingsTable rows={standings(snap.season)} chances={chances} teams={teams} caption="t" compact />
      </MemoryRouter>,
    );
    const kept = [...container.querySelectorAll('thead th.show-compact')].map((th) => th.textContent);
    expect(kept).toEqual(['GF', 'GA', 'GD']);
    expect(container.querySelectorAll('tbody tr:first-child td.show-compact')).toHaveLength(3);
  });

  it('marks clubs playing now', () => {
    render(
      <MemoryRouter>
        <StandingsTable rows={standings(snap.season)} chances={chances} teams={teams} caption="t" playing={new Set([a.homeId])} />
      </MemoryRouter>,
    );
    expect(screen.getAllByText('Playing now')).toHaveLength(1);
  });

  function mockData(scores: Map<number, LiveScore>) {
    const manifest = {
      season: '2026-27', model: 'test', updatedAt: snap.meta.asOf, liveId: 'live',
      snapshots: [{ id: 'live', label: 'Live', matchday: null, asOf: snap.meta.asOf, file: 'live.json' }],
    };
    vi.doMock('../src/lib/data', () => ({ useManifest: () => manifest, useSnapshot: () => snap, useTeams: () => teams }));
    vi.doMock('../src/lib/liveScores', async (orig) => ({
      ...(await orig<typeof import('../src/lib/liveScores')>()),
      useLiveScores: () => scores,
    }));
  }

  it('Table page counts live games as it stands and keeps the official chances', async () => {
    mockData(new Map([[a.id, live('IN_PLAY', 4, 0)]]));
    vi.resetModules();
    const { TablePage } = await import('../src/pages/TablePage');
    render(
      <MemoryRouter>
        <TablePage />
      </MemoryRouter>,
    );
    expect(await screen.findByText(/As it stands, with 1 game in progress/)).toBeTruthy();
    expect(screen.getByText(/chances update after full time/i)).toBeTruthy();
    const expected = standings(asItStands(snap.season, new Map([[a.id, live('IN_PLAY', 4, 0)]])));
    const homeRow = screen.getAllByRole('row').find((r) => r.getAttribute('data-key') === a.homeId)!;
    const rank = expected.find((r) => r.teamId === a.homeId)!;
    expect(within(homeRow).getAllByRole('cell')[0]!.textContent).toBe(String(rank.rank));
    expect(within(homeRow).getByText('Playing now')).toBeTruthy();
  });

  it('Table page says which games are still running and which just finished', async () => {
    mockData(new Map([[a.id, live('IN_PLAY', 1, 0)], [b.id, live('FINISHED', 0, 0)]]));
    vi.resetModules();
    const { TablePage } = await import('../src/pages/TablePage');
    render(
      <MemoryRouter>
        <TablePage />
      </MemoryRouter>,
    );
    expect(await screen.findByText(/As it stands, with 1 game in progress and 1 just finished/)).toBeTruthy();
    expect(screen.getByText(/red dot marks the clubs playing now/i)).toBeTruthy();
  });

  it('My scenario counts a guess overruled by full time once, as a live score', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ [b.id]: { homeGoals: 5, awayGoals: 0 } }));
    mockData(new Map([[a.id, live('IN_PLAY', 1, 0)], [b.id, live('FINISHED', 2, 2)]]));
    vi.doMock('../src/lib/useScenarioSim', () => ({
      useScenarioSim: () => ({ baseline: null, result: null, running: true, ms: null, error: null }),
    }));
    vi.resetModules();
    const { ScenarioTable } = await import('../src/pages/ScenarioTable');
    render(
      <MemoryRouter>
        <ScenarioTable />
      </MemoryRouter>,
    );
    expect(screen.getByText(/My scenario: live data plus 2 live scores\./)).toBeTruthy();
  });

  it('What-if pre-fills games in play, locks games at full time and simulates with both', async () => {
    mockData(new Map([[a.id, live('IN_PLAY', 1, 0)], [b.id, live('FINISHED', 2, 2)]]));
    const seen: unknown[] = [];
    vi.doMock('../src/lib/useScenarioSim', () => ({
      useScenarioSim: (_live: unknown, g: unknown) => {
        seen.push(g);
        return { baseline: null, result: null, running: false, ms: null, error: null };
      },
    }));
    vi.resetModules();
    const { WhatIfPage } = await import('../src/pages/WhatIfPage');
    const { container } = render(
      <MemoryRouter initialEntries={['/what-if']}>
        <WhatIfPage />
      </MemoryRouter>,
    );
    const rows = container.querySelectorAll('.guess--live');
    expect(rows).toHaveLength(1);
    const row = within(rows[0] as HTMLElement);
    expect((row.getByLabelText(`${teams[a.homeId]!.name} goals`) as HTMLInputElement).value).toBe('1');
    expect((row.getByLabelText(`${teams[a.awayId]!.name} goals`) as HTMLInputElement).value).toBe('0');
    expect(screen.getByText(/Full time, result locked/)).toBeTruthy();
    expect(seen.at(-1)).toEqual({ [a.id]: { homeGoals: 1, awayGoals: 0 }, [b.id]: { homeGoals: 2, awayGoals: 2 } });
  });
});

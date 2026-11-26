import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import type { Snapshot } from '../src/lib/types';
import { STORAGE_KEY } from '../src/lib/scenario';
import { makeSnapshot, makeTeams } from './fixtures';

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  vi.resetModules();
  vi.doUnmock('../src/lib/data');
  vi.doUnmock('../src/lib/useScenarioSim');
});

const team = { name: 'Arsenal', code: 'ARS', crest: 'https://crests.example/57.png', colors: ['#d01f2f', '#f4f6fa'] };

describe('TeamBadge crest kill switch', () => {
  it('shows the crest by default and falls back to the chip if it fails to load', async () => {
    const { TeamBadge } = await import('../src/components/TeamBadge');
    const { container } = render(<TeamBadge team={team} />);
    const img = container.querySelector('img')!;
    expect(img.getAttribute('src')).toBe(team.crest);
    fireEvent.error(img);
    expect(container.querySelector('img')).toBeNull();
    expect(container.querySelector('.badge__chip')).not.toBeNull();
    expect(screen.getByText('ARS')).toBeTruthy();
  });

  it('VITE_SHOW_CRESTS=false swaps every crest for a colour chip and short code', async () => {
    vi.stubEnv('VITE_SHOW_CRESTS', 'false');
    vi.resetModules();
    const { TeamBadge } = await import('../src/components/TeamBadge');
    const { container } = render(<TeamBadge team={team} />);
    expect(container.querySelector('img')).toBeNull();
    const chip = container.querySelector<HTMLElement>('.badge__chip')!;
    expect(chip.style.background).toContain('linear-gradient');
    expect(screen.getByText('ARS')).toBeTruthy();
    expect(screen.getByText('Arsenal')).toBeTruthy();
  });
});

describe('What-if lock-in', () => {
  let live: Snapshot;

  beforeEach(() => {
    live = makeSnapshot(4);
    localStorage.clear();
  });

  async function renderWhatIf() {
    const manifest = {
      season: '2026-27', model: 'test', updatedAt: live.meta.asOf, liveId: 'live',
      snapshots: [{ id: 'live', label: 'Live', matchday: null, asOf: live.meta.asOf, file: 'live.json' }],
    };
    const teams = makeTeams(live.season);
    vi.doMock('../src/lib/data', () => ({
      useManifest: () => manifest,
      useSnapshot: () => live,
      useTeams: () => teams,
    }));
    vi.doMock('../src/lib/useScenarioSim', () => ({
      useScenarioSim: () => ({ baseline: null, result: null, running: false, ms: null, error: null }),
    }));
    vi.resetModules();
    const { WhatIfPage } = await import('../src/pages/WhatIfPage');
    return render(
      <MemoryRouter initialEntries={['/what-if']}>
        <WhatIfPage />
      </MemoryRouter>,
    );
  }

  it('drops a saved guess once the real match is played, says so, and forgets it', async () => {
    const md5 = live.season.fixtures.filter((f) => f.matchday === 5);
    const played = md5[0]!;
    const open = md5[1]!;
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ [played.id]: { homeGoals: 2, awayGoals: 1 }, [open.id]: { homeGoals: 0, awayGoals: 0 } }));
    // The match is played after the guess was saved: flip it in the test data.
    Object.assign(played, { played: true, homeGoals: 3, awayGoals: 1 });

    await renderWhatIf();

    expect(await screen.findByText(/One of your guesses was removed/)).toBeTruthy();
    expect(screen.getByText(/your guess 2.1, result 3.1/)).toBeTruthy();
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY)!);
    expect(stored).toEqual({ [open.id]: { homeGoals: 0, awayGoals: 0 } });
    // The played match is locked to its real result.
    expect(screen.getAllByText('Played, result locked')).toHaveLength(1);
    expect(screen.getByText('1 score entered')).toBeTruthy();
  });

  it('keeps guesses for matches that are still to be played, with no notice', async () => {
    const open = live.season.fixtures.find((f) => !f.played)!;
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ [open.id]: { homeGoals: 1, awayGoals: 1 } }));
    await renderWhatIf();
    expect(screen.queryByText(/guesses? (was|were) removed/)).toBeNull();
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!)).toEqual({ [open.id]: { homeGoals: 1, awayGoals: 1 } });
  });
});

describe('PointsNeeded', () => {
  const runs = 2000;
  const snap = makeSnapshot(2, runs);

  it('lists the totals in play with their top-8 and top-24 shares and a plain headline', async () => {
    const { PointsNeeded } = await import('../src/components/PointsNeeded');
    const { pointsRows, evenChance } = await import('../src/lib/thresholds');
    render(<PointsNeeded thresholds={snap.thresholds!} runs={runs} />);
    expect(screen.getByRole('heading', { name: 'Points needed' })).toBeTruthy();
    const rows = pointsRows(snap.thresholds!);
    const bodyRows = screen.getAllByRole('row').slice(1);
    expect(bodyRows).toHaveLength(rows.length);
    expect(bodyRows[0]!.querySelector('th')!.textContent).toBe(`${rows[0]!.points} pts`);
    const even = evenChance(rows, 'top8')!;
    expect(screen.getByText(/More likely than not/).textContent).toContain(`top 8 from ${even.points} pts`);
  });

  it('dashes thin totals and shows changes against the baseline', async () => {
    const { PointsNeeded } = await import('../src/components/PointsNeeded');
    const make = (spec: Record<number, [number, number, number]>) => {
      const t = { count: Array<number>(25).fill(0), top8: Array<number>(25).fill(0), top24: Array<number>(25).fill(0) };
      for (const [p, [n, a, b]] of Object.entries(spec)) [t.count[+p], t.top8[+p], t.top24[+p]] = [n, a, b];
      return t;
    };
    const baseline = make({ 7: [5000, 0, 2500], 8: [5000, 1500, 4500], 9: [100, 60, 100], 10: [5000, 4500, 5000] });
    const now = make({ 7: [5000, 0, 2500], 8: [5000, 2500, 4500], 9: [100, 60, 100], 10: [5000, 4500, 5000] });
    const { container } = render(<PointsNeeded thresholds={now} baseline={baseline} runs={20000} tone="scenario" deltaKey="1" />);
    const row = (p: number) => [...container.querySelectorAll('tbody tr')].find((r) => r.querySelector('th')!.textContent === `${p} pts`)!;
    expect(row(8).querySelector('.delta--rise')!.textContent).toContain('+20.0');
    expect(row(7).querySelector('.delta')).toBeNull();
    expect(row(9).classList.contains('is-few')).toBe(true);
    expect(row(9).textContent).toContain('Too few simulations');
    expect(screen.getByText(/A dash means fewer than 400/)).toBeTruthy();
    expect(screen.getByText(/Changes are against live chances from the same 20,000 simulations/)).toBeTruthy();
  });
});

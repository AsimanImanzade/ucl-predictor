import { describe, expect, it } from 'vitest';
import { snapshotLabel, validateSnapshot, validateTeams } from '../src/lib/validate';
import { makeSeason, makeSnapshot, makeTeams } from './fixtures';

describe('validateSnapshot', () => {
  it('accepts a consistent snapshot', () => {
    expect(validateSnapshot(makeSnapshot(2))).toEqual([]);
  });

  it('rejects a missing fixture and a lopsided home/away count', () => {
    const s = makeSnapshot();
    s.season.fixtures.pop();
    const p = validateSnapshot(s);
    expect(p.some((m) => m.includes('144 fixtures'))).toBe(true);
    expect(p.some((m) => m.includes('home / '))).toBe(true);
  });

  it('rejects a played fixture without goals and an unplayed one with goals', () => {
    const s = makeSnapshot(1);
    s.season.fixtures[0]!.homeGoals = null;
    const last = s.season.fixtures.at(-1)!;
    last.homeGoals = 1;
    last.awayGoals = 0;
    const p = validateSnapshot(s);
    expect(p.some((m) => m.includes(`${s.season.fixtures[0]!.id}`) && m.includes('played'))).toBe(true);
    expect(p.some((m) => m.includes(`${last.id}`) && m.includes('unplayed'))).toBe(true);
  });

  it('rejects team set or order mismatches between season, lambdas and chances', () => {
    const s = makeSnapshot();
    s.lambdas.teams = [...s.lambdas.teams].reverse();
    expect(validateSnapshot(s).some((m) => m.includes('order'))).toBe(true);
    const c = makeSnapshot();
    c.chances = c.chances.slice(1);
    expect(validateSnapshot(c).some((m) => m.includes('chances'))).toBe(true);
  });

  it('rejects asOf disagreement', () => {
    const s = makeSnapshot();
    s.lambdas.asOf = '2026-10-01T00:00:00Z';
    expect(validateSnapshot(s).some((m) => m.includes('asOf'))).toBe(true);
  });

  it('rejects probability sums that are off', () => {
    const s = makeSnapshot();
    s.chances[0]!.top8 += 0.01;
    s.chances[0]!.reach.winner += 0.01;
    const p = validateSnapshot(s);
    expect(p.some((m) => m.includes('Top 8'))).toBe(true);
    expect(p.some((m) => m.includes('winner'))).toBe(true);
  });

  it('rejects ratings that miss a team', () => {
    const s = makeSnapshot();
    delete s.ratings![s.season.teams[0]!.id];
    expect(validateSnapshot(s).some((m) => m.includes('ratings'))).toBe(true);
  });
});

describe('validateTeams', () => {
  const season = makeSeason();
  it('accepts unique 3-letter codes covering every team', () => {
    expect(validateTeams(makeTeams(season), season)).toEqual([]);
  });
  it('rejects duplicate or malformed codes and missing teams', () => {
    const t = makeTeams(season);
    t[season.teams[1]!.id]!.code = t[season.teams[0]!.id]!.code;
    t[season.teams[2]!.id]!.code = 'FK';
    delete t[season.teams[3]!.id];
    const p = validateTeams(t, season);
    expect(p.some((m) => m.includes('duplicate'))).toBe(true);
    expect(p.some((m) => m.includes('FK'))).toBe(true);
    expect(p.some((m) => m.includes(season.teams[3]!.id))).toBe(true);
  });
});

describe('snapshotLabel', () => {
  it('names snapshots for people', () => {
    expect(snapshotLabel('md00')).toEqual({ label: 'Before matchday 1', matchday: 0 });
    expect(snapshotLabel('md04')).toEqual({ label: 'After matchday 4', matchday: 4 });
    expect(snapshotLabel('live')).toEqual({ label: 'Live', matchday: null });
  });
});

describe('validateSimInputs', () => {
  it('accepts matching season and lambdas, rejects mismatches the simulator would mis-handle', async () => {
    const { validateSimInputs } = await import('../src/lib/validate');
    const s = makeSnapshot(1);
    expect(validateSimInputs(s.season, s.lambdas)).toEqual([]);
    const bad = makeSnapshot(1);
    bad.season.fixtures[0]!.awayGoals = null;
    bad.lambdas.teams = bad.lambdas.teams.slice(1);
    bad.lambdas.asOf = 'x';
    const p = validateSimInputs(bad.season, bad.lambdas);
    expect(p.some((m) => m.includes('no valid score'))).toBe(true);
    expect(p.some((m) => m.includes('order'))).toBe(true);
    expect(p.some((m) => m.includes('asOf'))).toBe(true);
  });
});

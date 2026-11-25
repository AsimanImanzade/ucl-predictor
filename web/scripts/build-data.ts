/**
 * Assemble web/public/data/ from the immutable snapshot store plus fresh exports.
 *   node web/scripts/build-data.ts [mdNN ...] live
 * Past snapshots come from data/snapshots/2026-27/mdNN.json (committed, never overwritten).
 * The ids given are built from data/export/<id>/{season,lambdas,chances}.json; a new mdNN
 * is then added to the store. Teams come from data/processed/cl_2026_teams.json.
 * Every snapshot is validated; any problem aborts without writing.
 */
import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import type { Lambdas, Season, SimResult, TeamId } from '@uclpred/sim';
import { parseClubColors } from '../src/lib/teamColors.ts';
import type { Manifest, Snapshot, TeamMeta, TeamsFile } from '../src/lib/types.ts';
import { checkMatchdayLabel, checkSnapshotOrder, snapshotLabel, validateSnapshot, validateTeams } from '../src/lib/validate.ts';

const ROOT = path.resolve(import.meta.dirname, '../..');
const EXPORT = path.join(ROOT, 'data/export');
const OUT = path.join(ROOT, 'web/public/data');
const STORE = path.join(ROOT, 'data/snapshots/2026-27');
const FD_TEAMS = path.join(ROOT, 'data/processed/cl_2026_teams.json');
const CALIBRATION = path.join(ROOT, 'reports/calibration-bins-v21.json');

/** Display fixes for football-data short names. */
const NAMES: Record<TeamId, string> = {
  'svk-slovan-bratislava': 'Slovan Bratislava',
  'ukr-shakhtar-donetsk': 'Shakhtar',
  'gre-aek': 'AEK Athens',
  'aze-sabah': 'Sabah',
};

/** Unique 3-letter codes where football-data's TLA clashes or is not three letters. */
const CODES: Record<TeamId, string> = {
  'esp-barcelona': 'BAR',
  'nor-bodo-glimt': 'BOD',
  'aut-lask-linz': 'LAS',
};

const readJson = <T>(file: string): T => JSON.parse(readFileSync(file, 'utf8')) as T;

function fail(msg: string, problems: string[]): never {
  console.error(`${msg}:\n  ${problems.slice(0, 30).join('\n  ')}`);
  process.exit(1);
}

function buildSnapshot(id: string): Snapshot {
  const dir = path.join(EXPORT, id);
  const season = readJson<Season>(path.join(dir, 'season.json'));
  const { ratings, ...lambdas } = readJson<Lambdas & { ratings?: Record<TeamId, number> }>(path.join(dir, 'lambdas.json'));
  const sim = readJson<SimResult>(path.join(dir, 'chances.json'));
  if (sim.asOf !== season.asOf) fail(`${id}`, [`chances.json asOf ${sim.asOf} differs from season ${season.asOf}: re-run the simulator`]);
  const { label, matchday } = snapshotLabel(id);
  const snap: Snapshot = {
    meta: { id, label, matchday, asOf: season.asOf, file: `${id}.json`, model: lambdas.model, runs: sim.runs, seed: sim.seed, ratingSigma: lambdas.ratingSigma ?? 0 },
    season,
    lambdas,
    chances: sim.chances,
    ...(ratings ? { ratings } : {}),
  };
  return checked(snap);
}

function checked(snap: Snapshot): Snapshot {
  const { id } = snap.meta;
  const problems = [...validateSnapshot(snap), ...checkMatchdayLabel(id, snap.season)];
  if (problems.length) fail(`invalid snapshot ${id}`, problems);
  if (snap.meta.ratingSigma !== 0) fail(`snapshot ${id}`, ['ratingSigma > 0: apply the "Before M2 uses sigma > 0" follow-ups first']);
  return snap;
}

function storeIds(): string[] {
  if (!existsSync(STORE)) return [];
  return readdirSync(STORE)
    .filter((f) => /^md\d\d\.json$/.test(f))
    .map((f) => f.slice(0, -'.json'.length))
    .sort();
}

function loadStored(id: string): Snapshot {
  const snap = readJson<Snapshot>(path.join(STORE, `${id}.json`));
  if (snap.meta.id !== id) fail(`stored snapshot ${id}`, [`meta.id is ${snap.meta.id}`]);
  return checked(snap);
}

interface FdTeam {
  id: number;
  clubColors?: string | null;
  venue?: string | null;
}

function buildTeams(season: Season): TeamsFile {
  const fd = existsSync(FD_TEAMS) ? readJson<FdTeam[]>(FD_TEAMS) : [];
  if (!fd.length) console.warn('warning: no data/processed/cl_2026_teams.json; chips use the neutral colour');
  const byFd = new Map(fd.map((t) => [t.id, t]));
  const teams: TeamsFile = {};
  for (const t of season.teams) {
    const f = byFd.get(t.fdId);
    const meta: TeamMeta = {
      id: t.id,
      name: NAMES[t.id] ?? t.shortName,
      fullName: t.name,
      code: CODES[t.id] ?? t.tla,
      crest: t.crest,
      colors: parseClubColors(f?.clubColors),
      country: t.country,
      coefficient: t.coefficient,
      ...(f?.venue ? { venue: f.venue } : {}),
    };
    teams[t.id] = meta;
  }
  const problems = validateTeams(teams, season);
  if (problems.length) fail('invalid teams', problems);
  return teams;
}

function main(): void {
  const ids = process.argv.length > 2 ? process.argv.slice(2) : ['live'];
  if (!ids.includes('live')) fail('usage', ['the snapshot list must include live']);
  const stored = storeIds();
  const clash = ids.filter((id) => stored.includes(id));
  if (clash.length) fail('immutable snapshots', clash.map((id) => `${id} is already in data/snapshots/2026-27 and is never overwritten`));
  const built = ids.map(buildSnapshot);
  const order = (s: Snapshot) => s.meta.matchday ?? Number.POSITIVE_INFINITY;
  const snaps = [...stored.map(loadStored), ...built].sort((a, b) => order(a) - order(b));
  const orderProblems = checkSnapshotOrder(snaps.map((s) => s.meta));
  if (orderProblems.length) fail('snapshot order', orderProblems);
  const live = snaps.find((s) => s.meta.id === 'live')!;
  const teams = buildTeams(live.season);
  const models = new Set(snaps.map((s) => s.meta.model));
  if (models.size !== 1) fail('mixed models', [...models]);
  const manifest: Manifest = {
    season: live.season.season,
    model: live.meta.model,
    updatedAt: live.meta.asOf,
    liveId: 'live',
    snapshots: snaps.map(({ meta }) => ({ id: meta.id, label: meta.label, matchday: meta.matchday, asOf: meta.asOf, file: meta.file })),
  };
  mkdirSync(STORE, { recursive: true });
  // 'wx' fails if the file exists: a stored snapshot is never replaced.
  for (const s of built) if (s.meta.id !== 'live') writeFileSync(path.join(STORE, s.meta.file), JSON.stringify(s), { flag: 'wx' });
  mkdirSync(OUT, { recursive: true });
  for (const s of snaps) writeFileSync(path.join(OUT, s.meta.file), JSON.stringify(s));
  writeFileSync(path.join(OUT, 'teams.json'), JSON.stringify(teams, null, 1) + '\n');
  writeFileSync(path.join(OUT, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
  // Methodology page: binned calibration of the current model (uclpred calibration-bins).
  if (existsSync(CALIBRATION)) copyFileSync(CALIBRATION, path.join(OUT, 'calibration.json'));
  else console.warn('warning: reports/calibration-bins-v21.json missing; Methodology shows no calibration chart');
  for (const s of snaps) {
    const played = s.season.fixtures.filter((f) => f.played).length;
    console.log(`${s.meta.id.padEnd(5)} ${s.meta.label.padEnd(18)} asOf ${s.meta.asOf}  played ${played}/144  ${s.meta.runs} runs  ${s.meta.model}`);
  }
  const added = built.filter((s) => s.meta.id !== 'live').map((s) => s.meta.id);
  console.log(`wrote ${snaps.length} snapshots, teams.json, manifest.json -> ${path.relative(ROOT, OUT)}${added.length ? `; stored ${added.join(', ')}` : ''}`);
}

main();

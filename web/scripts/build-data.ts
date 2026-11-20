/**
 * Assemble web/public/data/ from the pipeline exports and simulator outputs.
 *   node web/scripts/build-data.ts [md00 md01 ... live]
 * Reads data/export/<id>/{season,lambdas,chances}.json and data/processed/cl_2026_teams.json.
 * Every snapshot is validated; any problem aborts without writing.
 */
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import type { Lambdas, Season, SimResult, TeamId } from '@uclpred/sim';
import { parseClubColors } from '../src/lib/teamColors.ts';
import type { Manifest, Snapshot, TeamMeta, TeamsFile } from '../src/lib/types.ts';
import { snapshotLabel, validateSnapshot, validateTeams } from '../src/lib/validate.ts';

const ROOT = path.resolve(import.meta.dirname, '../..');
const EXPORT = path.join(ROOT, 'data/export');
const OUT = path.join(ROOT, 'web/public/data');
const FD_TEAMS = path.join(ROOT, 'data/processed/cl_2026_teams.json');
const CALIBRATION = path.join(ROOT, 'reports/calibration-bins-v21.json');
const DEFAULT_IDS = ['md00', 'md01', 'md02', 'md03', 'md04', 'live'];

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
  const problems = validateSnapshot(snap);
  if (problems.length) fail(`invalid snapshot ${id}`, problems);
  if (snap.meta.ratingSigma !== 0) fail(`snapshot ${id}`, ['ratingSigma > 0: apply the "Before M2 uses sigma > 0" follow-ups first']);
  return snap;
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
  const ids = process.argv.length > 2 ? process.argv.slice(2) : DEFAULT_IDS;
  if (!ids.includes('live')) fail('usage', ['the snapshot list must include live']);
  const snaps = ids.map(buildSnapshot);
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
  console.log(`wrote ${snaps.length} snapshots, teams.json, manifest.json -> ${path.relative(ROOT, OUT)}`);
}

main();

import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { simulate } from './simulate.js';
import type { Lambdas, Season, SimResult } from './types.js';

function pct(x: number): string {
  return (x * 100).toFixed(1).padStart(5) + '%';
}

export function formatTable(season: Season, res: SimResult, ms: number): string {
  const names = new Map(season.teams.map((t) => [t.id, t.shortName || t.name]));
  const rows = [...res.chances].sort((a, b) => b.expectedPoints - a.expectedPoints);
  const lines = ['Team                       | Pts(exp) |  Top 8 | Top 24 |    R16 |     QF |     SF |  Final |    Win'];
  for (const c of rows) {
    lines.push(
      [
        (names.get(c.teamId) ?? c.teamId).slice(0, 26).padEnd(26),
        c.expectedPoints.toFixed(2).padStart(8),
        pct(c.top8), pct(c.top24), pct(c.reach.r16), pct(c.reach.qf), pct(c.reach.sf), pct(c.reach.final), pct(c.reach.winner),
      ].join(' | '),
    );
  }
  const sum = (f: (c: SimResult['chances'][number]) => number) => res.chances.reduce((a, c) => a + f(c), 0);
  lines.push(
    `Check: sum Top 8 = ${sum((c) => c.top8).toFixed(2)}, Top 24 = ${sum((c) => c.top24).toFixed(2)}, Win = ${sum((c) => c.reach.winner).toFixed(2)} | ${res.runs} runs, seed ${res.seed}, ${(ms / 1000).toFixed(1)} s`,
  );
  return lines.join('\n');
}

/** Repo root (sim/src/.. /..): relative paths never depend on the cwd pnpm picks. */
export const REPO_ROOT = path.resolve(import.meta.dirname, '../..');

export interface CliArgs {
  input: string;
  out: string;
  runs: number;
  seed: number;
  sigma: number | undefined;
}

const USAGE = 'usage: pnpm --filter @uclpred/sim cli -- --input <dir> [--runs 50000] [--seed 1] [--sigma 0] [--out <file>]  (paths: absolute or relative to the repo root)';

export function parseArgs(argv: string[]): CliArgs | { error: string } {
  const get = (name: string): string | undefined | null => {
    const i = argv.indexOf(`--${name}`);
    if (i < 0) return undefined;
    const v = argv[i + 1];
    return v === undefined || v.startsWith('--') ? null : v;
  };
  const input = get('input');
  if (!input) return { error: USAGE };
  const int = (name: string, fallback: number, min: number): number | string => {
    const raw = get(name);
    if (raw === undefined) return fallback;
    const n = raw === null ? NaN : Number(raw);
    return Number.isSafeInteger(n) && n >= min ? n : `--${name} must be an integer >= ${min}`;
  };
  const runs = int('runs', 50000, 1);
  if (typeof runs === 'string') return { error: runs };
  const seed = int('seed', 1, 0);
  if (typeof seed === 'string') return { error: seed };
  const sigmaRaw = get('sigma');
  const sigma = sigmaRaw === undefined ? undefined : sigmaRaw === null ? NaN : Number(sigmaRaw);
  if (sigma !== undefined && !(Number.isFinite(sigma) && sigma >= 0)) return { error: '--sigma must be a finite number >= 0' };
  const fromRoot = (p: string): string => (path.isAbsolute(p) ? p : path.resolve(REPO_ROOT, p));
  const dir = fromRoot(input);
  const out = get('out');
  return { input: dir, out: out ? fromRoot(out) : path.join(dir, 'chances.json'), runs, seed, sigma };
}

function main(): void {
  const args = parseArgs(process.argv.slice(2));
  if ('error' in args) {
    console.error(args.error);
    process.exit(2);
  }
  const { input: dir, out: outPath, runs, seed, sigma } = args;
  const season = JSON.parse(readFileSync(path.join(dir, 'season.json'), 'utf8')) as Season;
  const lambdas = JSON.parse(readFileSync(path.join(dir, 'lambdas.json'), 'utf8')) as Lambdas;
  const t0 = performance.now();
  const res = simulate(season, lambdas, sigma === undefined ? { runs, seed } : { runs, seed, ratingSigma: sigma });
  const ms = performance.now() - t0;
  writeFileSync(outPath, JSON.stringify(res));
  console.log(`as of ${season.asOf}  (${dir})`);
  console.log(formatTable(season, res, ms));
}

// Run only as a script, never on import (tests import parseArgs / formatTable).
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();

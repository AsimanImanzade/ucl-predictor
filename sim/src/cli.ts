import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { simulate } from './simulate.js';
import type { Lambdas, Season, SimResult } from './types.js';

function arg(name: string, fallback?: string): string | undefined {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 ? process.argv[i + 1] : fallback;
}

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

function main(): void {
  const input = arg('input');
  if (!input) {
    console.error('usage: pnpm --filter @uclpred/sim cli -- --input <dir> [--runs 50000] [--seed 1]');
    console.error('  <dir> is absolute or relative to the repo root (pnpm runs this with cwd = sim/).');
    process.exit(2);
  }
  const runs = Number(arg('runs', '50000'));
  const seed = Number(arg('seed', '1'));
  const dir = path.isAbsolute(input) ? input : path.resolve(process.cwd(), '..', input);
  const season = JSON.parse(readFileSync(path.join(dir, 'season.json'), 'utf8')) as Season;
  const lambdas = JSON.parse(readFileSync(path.join(dir, 'lambdas.json'), 'utf8')) as Lambdas;
  const t0 = performance.now();
  const res = simulate(season, lambdas, { runs, seed });
  const ms = performance.now() - t0;
  writeFileSync(path.join(dir, 'chances.json'), JSON.stringify(res));
  console.log(`as of ${season.asOf}  (${dir})`);
  console.log(formatTable(season, res, ms));
}

main();

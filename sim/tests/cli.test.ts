import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { parseArgs, REPO_ROOT } from '../src/cli.js';

describe('sim CLI arguments', () => {
  it('importing the CLI does not run it, and paths resolve from the repo root', () => {
    expect(REPO_ROOT).toBe(path.resolve(import.meta.dirname, '../..'));
    const a = parseArgs(['--input', 'data/export/live']);
    expect(a).toEqual({ input: path.join(REPO_ROOT, 'data/export/live'), out: path.join(REPO_ROOT, 'data/export/live/chances.json'), runs: 50000, seed: 1, sigma: undefined });
  });

  it('accepts absolute paths and explicit options', () => {
    const a = parseArgs(['--', '--input', '/tmp/x', '--runs', '200', '--seed', '7', '--sigma', '0', '--out', 'o.json']);
    expect(a).toMatchObject({ input: '/tmp/x', runs: 200, seed: 7, sigma: 0, out: path.join(REPO_ROOT, 'o.json') });
  });

  it.each([
    [[], 'usage'],
    [['--input', 'x', '--runs', '0'], '--runs'],
    [['--input', 'x', '--runs', '2.5'], '--runs'],
    [['--input', 'x', '--runs', 'abc'], '--runs'],
    [['--input', 'x', '--seed', '1.5'], '--seed'],
    [['--input', 'x', '--seed', '-1'], '--seed'],
    [['--input', 'x', '--sigma', '-1'], '--sigma'],
    [['--input', 'x', '--runs'], '--runs'],
  ])('rejects %j', (argv, msg) => {
    const a = parseArgs(argv as string[]);
    expect('error' in a && a.error).toContain(msg);
  });
});

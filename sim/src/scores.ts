import type { Lambdas, LambdaPair, TeamId } from './types.js';

export type Venue = 'home' | 'neutral';
type Rng = () => number;

function poissonPmf(lambda: number, n: number): Float64Array {
  const out = new Float64Array(n + 1);
  let p = Math.exp(-lambda);
  out[0] = p;
  for (let k = 1; k <= n; k++) {
    p = (p * lambda) / k;
    out[k] = p;
  }
  return out;
}

/** Dixon-Coles score matrix, row-major: index = homeGoals * (maxGoals + 1) + awayGoals. */
export function scoreMatrix(lh: number, la: number, rho: number, maxGoals = 10): Float64Array {
  const n = maxGoals + 1;
  const ph = poissonPmf(lh, maxGoals);
  const pa = poissonPmf(la, maxGoals);
  const m = new Float64Array(n * n);
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) m[i * n + j] = ph[i]! * pa[j]!;
  }
  m[0] = m[0]! * (1 - lh * la * rho);
  m[1] = m[1]! * (1 + lh * rho);
  m[n] = m[n]! * (1 + la * rho);
  m[n + 1] = m[n + 1]! * (1 - rho);
  let sum = 0;
  for (let k = 0; k < m.length; k++) {
    if (m[k]! < 0) m[k] = 0;
    sum += m[k]!;
  }
  for (let k = 0; k < m.length; k++) m[k] = m[k]! / sum;
  return m;
}

export function outcomeProbs(m: Float64Array, maxGoals = 10): [number, number, number] {
  const n = maxGoals + 1;
  let home = 0, draw = 0, away = 0;
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      const v = m[i * n + j]!;
      if (i > j) home += v;
      else if (i === j) draw += v;
      else away += v;
    }
  }
  return [home, draw, away];
}

/** Knuth's multiplication method; fine for small lambda. */
export function samplePoisson(lambda: number, rng: Rng): number {
  const limit = Math.exp(-lambda);
  let k = 0;
  let p = 1;
  do {
    k++;
    p *= rng();
  } while (p > limit);
  return k - 1;
}

const MAX_GOALS = 10;
const N = MAX_GOALS + 1;

export class ScoreSampler {
  private readonly index = new Map<TeamId, number>();
  private readonly cdfs = new Map<number, Float64Array>();

  constructor(private readonly lambdas: Lambdas) {
    lambdas.teams.forEach((t, i) => this.index.set(t, i));
  }

  private idx(t: TeamId): number {
    const i = this.index.get(t);
    if (i === undefined) throw new Error(`ScoreSampler: unknown team id "${t}"`);
    return i;
  }

  lambda(a: TeamId, b: TeamId, venue: Venue): LambdaPair {
    const i = this.idx(a);
    const j = this.idx(b);
    const cell = (venue === 'home' ? this.lambdas.home : this.lambdas.neutral)[i]?.[j];
    if (!cell) throw new Error(`ScoreSampler: no lambdas for ${a} vs ${b} (${venue})`);
    return cell;
  }

  private cdf(a: TeamId, b: TeamId, venue: Venue): Float64Array {
    const i = this.idx(a);
    const j = this.idx(b);
    const key = ((i * this.lambdas.teams.length + j) << 1) | (venue === 'home' ? 0 : 1);
    let c = this.cdfs.get(key);
    if (!c) {
      const [lh, la] = this.lambda(a, b, venue);
      const m = scoreMatrix(lh, la, this.lambdas.rho, MAX_GOALS);
      c = new Float64Array(m.length);
      let acc = 0;
      for (let k = 0; k < m.length; k++) {
        acc += m[k]!;
        c[k] = acc;
      }
      c[c.length - 1] = 1;
      this.cdfs.set(key, c);
    }
    return c;
  }

  sample(a: TeamId, b: TeamId, venue: Venue, rng: Rng): [number, number] {
    const c = this.cdf(a, b, venue);
    const u = rng();
    let lo = 0;
    let hi = c.length - 1;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (c[mid]! > u) hi = mid;
      else lo = mid + 1;
    }
    return [Math.floor(lo / N), lo % N];
  }
}

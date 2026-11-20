import type { Lambdas, Overrides, Season, SimResult } from '@uclpred/sim';

export const SCENARIO_RUNS = 20000;
export const SCENARIO_SEED = 1;

export type WorkerRequest =
  | { type: 'init'; key: string; season: Season; lambdas: Lambdas }
  | { type: 'run'; id: number; key: string; overrides: Overrides };

export type WorkerResponse =
  | { type: 'baseline'; key: string; result: SimResult; ms: number }
  | { type: 'result'; id: number; key: string; result: SimResult; ms: number }
  | { type: 'error'; id?: number; key: string; message: string };

/// <reference lib="webworker" />
import { simulate, type Lambdas, type Season } from '@uclpred/sim';
import { validateSimInputs } from '../lib/validate';
import { SCENARIO_RUNS, SCENARIO_SEED, type WorkerRequest, type WorkerResponse } from './protocol';

declare const self: DedicatedWorkerGlobalScope;

let inputs: { key: string; season: Season; lambdas: Lambdas } | null = null;
const post = (m: WorkerResponse) => self.postMessage(m);

self.onmessage = (e: MessageEvent<WorkerRequest>) => {
  const msg = e.data;
  try {
    if (msg.type === 'init') {
      const problems = validateSimInputs(msg.season, msg.lambdas);
      if (problems.length) throw new Error(`Forecast data failed its checks: ${problems.slice(0, 3).join('; ')}`);
      inputs = { key: msg.key, season: msg.season, lambdas: msg.lambdas };
      const t = performance.now();
      // Baseline with the same runs and seed as every scenario, so deltas compare like with like.
      const result = simulate(msg.season, msg.lambdas, { runs: SCENARIO_RUNS, seed: SCENARIO_SEED });
      post({ type: 'baseline', key: msg.key, result, ms: performance.now() - t });
      return;
    }
    if (!inputs || inputs.key !== msg.key) throw new Error('Simulation inputs are not loaded.');
    const t = performance.now();
    const result = simulate(inputs.season, inputs.lambdas, { runs: SCENARIO_RUNS, seed: SCENARIO_SEED, overrides: msg.overrides });
    post({ type: 'result', id: msg.id, key: msg.key, result, ms: performance.now() - t });
  } catch (err) {
    post({ type: 'error', id: msg.type === 'run' ? msg.id : undefined, key: msg.key, message: err instanceof Error ? err.message : String(err) });
  }
};

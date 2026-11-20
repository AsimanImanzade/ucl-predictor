import { useEffect, useRef, useState } from 'react';
import type { SimResult } from '@uclpred/sim';
import { createRunQueue } from './runQueue';
import type { Guesses } from './scenario';
import type { Snapshot } from './types';
import type { WorkerRequest, WorkerResponse } from '../worker/protocol';

export interface ScenarioSim {
  baseline: SimResult | null;
  result: SimResult | null;
  running: boolean;
  ms: number | null;
  error: string | null;
}

let worker: Worker | null = null;
let initKey: string | null = null;
let nextId = 0;
/** Baselines survive page changes: the worker computes each one once. */
const baselines = new Map<string, SimResult>();
/** One run in flight; while it runs, only the newest request waits (stale ones never run). */
const queue = createRunQueue<WorkerRequest>((m) => getWorker().postMessage(m));
const failListeners = new Set<(message: string) => void>();

function getWorker(): Worker {
  if (!worker) {
    worker = new Worker(new URL('../worker/sim.worker.ts', import.meta.url), { type: 'module' });
    worker.addEventListener('message', (e: MessageEvent<WorkerResponse>) => {
      if (e.data.type === 'baseline') baselines.set(e.data.key, e.data.result);
      queue.done();
    });
    // The worker script itself failed (e.g. could not load): stop waiting for it.
    worker.addEventListener('error', () => {
      queue.done();
      failListeners.forEach((l) => l('The simulator could not start in this browser.'));
    });
  }
  return worker;
}

/**
 * Runs the unchanged simulator in a Web Worker: a 20k-run baseline once per live snapshot,
 * then each scenario (debounced). The latest request wins; superseded requests never run.
 */
export function useScenarioSim(live: Snapshot, guesses: Guesses, debounceMs = 200): ScenarioSim {
  const key = live.meta.asOf;
  const [state, setState] = useState<ScenarioSim>(() => ({ baseline: baselines.get(key) ?? null, result: null, running: true, ms: null, error: null }));
  const reqId = useRef(-1);

  useEffect(() => {
    const w = getWorker();
    const onMessage = (e: MessageEvent<WorkerResponse>) => {
      const m = e.data;
      if (m.key !== key) return;
      if (m.type === 'baseline') {
        setState((s) => ({ ...s, baseline: m.result }));
      } else if (m.type === 'result') {
        if (m.id !== reqId.current) return;
        setState((s) => ({ ...s, result: m.result, running: false, ms: m.ms, error: null }));
        if (import.meta.env.DEV) console.info(`[what-if] ${m.result.runs} runs in ${Math.round(m.ms)} ms`);
      } else if (m.id === undefined || m.id === reqId.current) {
        setState((s) => ({ ...s, running: false, error: m.message }));
      }
    };
    const onFail = (message: string) => setState((s) => ({ ...s, running: false, error: message }));
    w.addEventListener('message', onMessage);
    failListeners.add(onFail);
    // A baseline that arrived before this listener was attached.
    const cached = baselines.get(key);
    if (cached) setState((s) => (s.baseline ? s : { ...s, baseline: cached }));
    if (initKey !== key) {
      initKey = key;
      queue.submit({ type: 'init', key, season: live.season, lambdas: live.lambdas });
    }
    return () => {
      w.removeEventListener('message', onMessage);
      failListeners.delete(onFail);
    };
  }, [key, live]);

  const sig = JSON.stringify(guesses);
  const empty = sig === '{}';
  useEffect(() => {
    // No scores entered: the baseline is the answer, no second run needed.
    if (empty) {
      reqId.current = -1;
      return;
    }
    const id = ++nextId;
    reqId.current = id;
    setState((s) => ({ ...s, running: true }));
    const t = setTimeout(() => queue.submit({ type: 'run', id, key, overrides: guesses }), debounceMs);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sig, key]);

  return empty ? { ...state, result: state.baseline, running: state.baseline === null } : state;
}

import { useEffect, useSyncExternalStore } from 'react';
import type { Season } from '@uclpred/sim';
import { loadGuesses, reconcile, saveGuesses, STORAGE_KEY, type DroppedGuess, type Guesses } from './scenario';

/** One shared, persisted scenario for the What-if page and the "My scenario" table view. */
interface State {
  guesses: Guesses;
  /** Guesses removed because the real match has been played; shown until dismissed. */
  dropped: DroppedGuess[];
}

let state: State = { guesses: loadGuesses(), dropped: [] };
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

export const scenarioStore = {
  get: () => state,
  setGuesses(guesses: Guesses) {
    state = { ...state, guesses };
    saveGuesses(guesses);
    emit();
  },
  addDropped(dropped: DroppedGuess[]) {
    if (!dropped.length) return;
    const seen = new Set(state.dropped.map((d) => d.fixtureId));
    state = { ...state, dropped: [...state.dropped, ...dropped.filter((d) => !seen.has(d.fixtureId))] };
    emit();
  },
  dismissDropped() {
    state = { ...state, dropped: [] };
    emit();
  },
  subscribe(l: () => void) {
    listeners.add(l);
    return () => listeners.delete(l);
  },
  /** Test hook: reload from storage. */
  reload() {
    state = { guesses: loadGuesses(), dropped: [] };
    emit();
  },
};

if (typeof window !== 'undefined') {
  // Another tab changed the scenario.
  window.addEventListener('storage', (e) => {
    if (e.key === STORAGE_KEY) scenarioStore.reload();
  });
}

export function useScenario(): State {
  return useSyncExternalStore(scenarioStore.subscribe, scenarioStore.get, scenarioStore.get);
}

/**
 * The stored scenario checked against the live data: guesses for matches that have since been
 * played are removed (and listed in `dropped` until the notice is dismissed).
 */
export function useReconciledScenario(season: Season): State {
  const s = useScenario();
  useEffect(() => {
    const { kept, dropped } = reconcile(scenarioStore.get().guesses, season);
    if (dropped.length || Object.keys(kept).length !== Object.keys(scenarioStore.get().guesses).length) {
      scenarioStore.setGuesses(kept);
      scenarioStore.addDropped(dropped);
    }
  }, [season]);
  // Render with reconciled guesses straight away, before the effect commits them.
  const { kept } = reconcile(s.guesses, season);
  return { guesses: kept, dropped: s.dropped };
}

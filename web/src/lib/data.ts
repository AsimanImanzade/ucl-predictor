import { use } from 'react';
import type { Manifest, Snapshot, TeamsFile } from './types';

const cache = new Map<string, Promise<unknown>>();

function fetchJson<T>(path: string): Promise<T> {
  let p = cache.get(path) as Promise<T> | undefined;
  if (!p) {
    p = fetch(`/data/${path}`).then((r) => {
      if (!r.ok) throw new Error(`Could not load ${path} (HTTP ${r.status}).`);
      return r.json() as Promise<T>;
    });
    // A failed load is retried on the next render instead of being cached forever.
    p.catch(() => cache.delete(path));
    cache.set(path, p);
  }
  return p;
}

export const loadManifest = () => fetchJson<Manifest>('manifest.json');
export const loadTeams = () => fetchJson<TeamsFile>('teams.json');
export function loadSnapshot(manifest: Manifest, id: string): Promise<Snapshot> {
  const meta = manifest.snapshots.find((s) => s.id === id);
  if (!meta) {
    // Cached so React's `use` sees the same rejected promise on every render.
    const key = `missing:${id}`;
    if (!cache.has(key)) {
      const p = Promise.reject(new Error(`Unknown forecast snapshot "${id}".`));
      p.catch(() => undefined);
      cache.set(key, p);
    }
    return cache.get(key) as Promise<Snapshot>;
  }
  return fetchJson<Snapshot>(meta.file);
}

/** Suspense hooks: components suspend until the JSON is in. */
export const useManifest = () => use(loadManifest());
export const useTeams = () => use(loadTeams());
export function useSnapshot(id: string): Snapshot {
  const manifest = useManifest();
  return use(loadSnapshot(manifest, id));
}

let allSnapshots: Promise<Snapshot[]> | null = null;
/** Every snapshot in manifest order (Team page history). */
export function useAllSnapshots(): Snapshot[] {
  const manifest = useManifest();
  allSnapshots ??= Promise.all(manifest.snapshots.map((s) => loadSnapshot(manifest, s.id)));
  allSnapshots.catch(() => (allSnapshots = null));
  return use(allSnapshots);
}

/** The last snapshot taken before a kickoff, for "the model's view before the match". */
export function snapshotBefore(manifest: Manifest, kickoff: string): string | null {
  const before = manifest.snapshots.filter((s) => s.asOf < kickoff).sort((a, b) => (a.asOf < b.asOf ? 1 : -1));
  return before[0]?.id ?? null;
}

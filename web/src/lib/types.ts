import type { Lambdas, Season, TeamChances, TeamId } from '@uclpred/sim';

/** One forecast snapshot listed in `manifest.json`. */
export interface SnapshotMeta {
  /** "md00" … "md08" or "live". */
  id: string;
  /** "Before matchday 1", "After matchday 3", "Live". */
  label: string;
  /** Matchdays complete at this snapshot; null for live. */
  matchday: number | null;
  asOf: string;
  file: string;
}

export interface Manifest {
  season: string;
  model: string;
  /** asOf of the live snapshot. */
  updatedAt: string;
  liveId: string;
  snapshots: SnapshotMeta[];
}

/** `<id>.json`: export and simulator outputs, unchanged, plus run metadata. */
export interface Snapshot {
  meta: SnapshotMeta & { model: string; runs: number; seed: number; ratingSigma: number };
  season: Season;
  lambdas: Lambdas;
  chances: TeamChances[];
  /** Elo at asOf (display only). */
  ratings?: Record<TeamId, number>;
}

/** Display metadata for one club (`teams.json`). */
export interface TeamMeta {
  id: TeamId;
  name: string;
  fullName: string;
  /** Unique 3-letter code shown with the colour chip. */
  code: string;
  crest: string;
  colors: string[];
  country: string;
  coefficient: number;
  venue?: string;
}

export type TeamsFile = Record<TeamId, TeamMeta>;

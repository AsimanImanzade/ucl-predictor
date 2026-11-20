export type TeamId = string;

export interface Team {
  id: TeamId;
  fdId: number;
  name: string;
  shortName: string;
  tla: string;
  crest: string;
  country: string;
  coefficient: number;
}

export interface Fixture {
  id: number;
  matchday: number;
  utcDate: string;
  homeId: TeamId;
  awayId: TeamId;
  played: boolean;
  homeGoals: number | null;
  awayGoals: number | null;
}

export interface Season {
  season: string;
  asOf: string;
  finalVenueTeamId: TeamId | null;
  teams: Team[];
  fixtures: Fixture[];
}

export type LambdaPair = [number, number];

export interface Lambdas {
  asOf: string;
  model: string;
  rho: number;
  teams: TeamId[];
  home: (LambdaPair | null)[][];
  neutral: (LambdaPair | null)[][];
  /** GLM beta per 100 Elo points; required when ratingSigma > 0. */
  eloCoef?: number;
  /** Per-run team rating noise, in Elo points; missing means 0. */
  ratingSigma?: number;
}

export type Overrides = Record<number, { homeGoals: number; awayGoals: number }>;

export type Stage = 'po' | 'r16' | 'qf' | 'sf' | 'final' | 'winner';

export interface TeamChances {
  teamId: TeamId;
  /** length 36: probability of finishing league phase in each position (index 0 = 1st) */
  position: number[];
  top8: number;
  top24: number;
  out: number;
  reach: Record<Stage, number>;
  expectedPoints: number;
}

export interface SimResult {
  runs: number;
  seed: number;
  asOf: string;
  chances: TeamChances[];
}

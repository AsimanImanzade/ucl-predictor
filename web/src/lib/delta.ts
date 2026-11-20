/**
 * Scenario minus baseline, or null when the change is within Monte Carlo noise:
 * |d| < 2 standard errors of the difference of two independent estimates over `runs`.
 * Moves to or from exactly 0 or 1 are always shown (a guess can settle a team's fate).
 */
export function shownDelta(scenario: number, baseline: number, runs: number): number | null {
  const d = scenario - baseline;
  if (d === 0) return null;
  const certain = (p: number) => p === 0 || p === 1;
  if (certain(scenario) !== certain(baseline)) return d;
  const se = Math.sqrt((scenario * (1 - scenario) + baseline * (1 - baseline)) / runs);
  return Math.abs(d) < 2 * se ? null : d;
}

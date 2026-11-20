import { samplePoisson, type Venue } from './scores.js';
import type { LambdaPair, TeamId } from './types.js';

type Rng = () => number;

/** The slice of ScoreSampler the knockout code needs (lets tests force scores). */
export interface MatchSampler {
  sample(a: TeamId, b: TeamId, venue: Venue, rng: Rng): [number, number];
  lambda(a: TeamId, b: TeamId, venue: Venue): LambdaPair;
}

/** Level after 90 (or aggregate): 30 minutes of extra time, then penalties 50/50. */
function extraTimeThenPens(
  a: TeamId,
  b: TeamId,
  lamA: number,
  lamB: number,
  rng: Rng,
): TeamId {
  const ga = samplePoisson((lamA * 30) / 90, rng);
  const gb = samplePoisson((lamB * 30) / 90, rng);
  if (ga !== gb) return ga > gb ? a : b;
  return rng() < 0.5 ? a : b;
}

/** Two legs, aggregate only (no away goals). Extra time is played at leg 2's venue. */
export function playTwoLegged(
  firstHome: TeamId,
  secondHome: TeamId,
  sampler: MatchSampler,
  rng: Rng,
): TeamId {
  const [g1h, g1a] = sampler.sample(firstHome, secondHome, 'home', rng);
  const [g2h, g2a] = sampler.sample(secondHome, firstHome, 'home', rng);
  const first = g1h + g2a;
  const second = g1a + g2h;
  if (first !== second) return first > second ? firstHome : secondHome;
  const [lamSecond, lamFirst] = sampler.lambda(secondHome, firstHome, 'home');
  const w = extraTimeThenPens(secondHome, firstHome, lamSecond, lamFirst, rng);
  return w;
}

/** Single-match final; venueTeamId (if a or b) hosts, otherwise neutral. */
export function playFinal(
  a: TeamId,
  b: TeamId,
  venueTeamId: TeamId | null,
  sampler: MatchSampler,
  rng: Rng,
): TeamId {
  let host = a;
  let guest = b;
  let venue: Venue = 'neutral';
  if (venueTeamId === a) venue = 'home';
  else if (venueTeamId === b) {
    host = b;
    guest = a;
    venue = 'home';
  }
  const [gh, gg] = sampler.sample(host, guest, venue, rng);
  if (gh !== gg) return gh > gg ? host : guest;
  const [lh, lg] = sampler.lambda(host, guest, venue);
  return extraTimeThenPens(host, guest, lh, lg, rng);
}

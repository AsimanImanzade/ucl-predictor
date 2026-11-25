/**
 * Cloudflare Worker: live scores for the dashboard (display only, never the odds).
 *
 * The Cache API does nothing on *.workers.dev, so visitors never reach football-data:
 * a once-a-minute cron refreshes KV, and GET / only reads KV. That caps football-data at
 * one request a minute (free plan: 10/min) however many people are watching.
 * Secret: FOOTBALL_DATA_TOKEN. KV binding: LIVE. Vars: SEASON, ALLOWED_ORIGIN.
 */
const KEY = 'today';
const ATTRIBUTION = 'Football data provided by the Football-Data.org API';
const RUNNING = new Set(['IN_PLAY', 'PAUSED', 'EXTRA_TIME', 'PENALTY_SHOOTOUT', 'SUSPENDED']);
const NOT_STARTED = new Set(['SCHEDULED', 'TIMED']);
const STARTED = new Set([...RUNNING, 'FINISHED']);
/** Statuses the dashboard shows; extra time and shoot-outs count as live. */
const SHOWN = { IN_PLAY: 'IN_PLAY', EXTRA_TIME: 'IN_PLAY', PENALTY_SHOOTOUT: 'IN_PLAY', PAUSED: 'PAUSED', FINISHED: 'FINISHED' };
const LEAD_MS = 5 * 60_000;

export const today = (now) => new Date(now).toISOString().slice(0, 10);

/** football-data matches -> the few fields we keep. In play, score.fullTime is the current score. */
export function trim(matches) {
  return matches.map((m) => ({
    id: m.id,
    utcDate: m.utcDate,
    status: m.status,
    home: m.score?.fullTime?.home ?? null,
    away: m.score?.fullTime?.away ?? null,
  }));
}

/**
 * football-data once sent every game of the night back to TIMED with null scores
 * (2026-11-25 20:26 UTC). A started game never really goes back, so keep what we had.
 */
export function keepStarted(prev, next) {
  const old = new Map(prev.map((m) => [m.id, m]));
  return next.map((m) => (NOT_STARTED.has(m.status) && STARTED.has(old.get(m.id)?.status) ? old.get(m.id) : m));
}

/** Call football-data only on a new day, while a game runs, or from 5 min before a kickoff. */
export function needsFetch(stored, now) {
  if (!stored || stored.date !== today(now)) return true;
  return stored.matches.some((m) => RUNNING.has(m.status) || (NOT_STARTED.has(m.status) && Date.parse(m.utcDate) - LEAD_MS <= now));
}

export async function refresh(env, now, fetchFn = fetch) {
  if (!env.FOOTBALL_DATA_TOKEN) throw new Error('FOOTBALL_DATA_TOKEN secret is not set');
  const stored = await env.LIVE.get(KEY, 'json');
  if (!needsFetch(stored, now)) return 'skipped';
  const date = today(now);
  const url = `https://api.football-data.org/v4/competitions/CL/matches?season=${env.SEASON}&dateFrom=${date}&dateTo=${date}`;
  const res = await fetchFn(url, { headers: { 'X-Auth-Token': env.FOOTBALL_DATA_TOKEN } });
  if (!res.ok) throw new Error(`football-data request failed: HTTP ${res.status}`);
  const fetched = trim((await res.json()).matches ?? []);
  const matches = stored?.date === date ? keepStarted(stored.matches, fetched) : fetched;
  // Writes only on change: free KV allows 1,000 writes a day.
  if (stored && stored.date === date && JSON.stringify(stored.matches) === JSON.stringify(matches)) return 'unchanged';
  await env.LIVE.put(KEY, JSON.stringify({ date, updatedAt: new Date(now).toISOString(), matches }));
  return 'updated';
}

function cors(env) {
  return { 'Access-Control-Allow-Origin': env.ALLOWED_ORIGIN, 'Access-Control-Allow-Methods': 'GET, OPTIONS', Vary: 'Origin' };
}

async function serve(request, env) {
  const { pathname } = new URL(request.url);
  if (pathname !== '/') return new Response('Not found', { status: 404 });
  if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: { ...cors(env), 'Access-Control-Max-Age': '86400' } });
  if (request.method !== 'GET') return new Response('Method not allowed', { status: 405, headers: { Allow: 'GET, OPTIONS' } });
  const stored = await env.LIVE.get(KEY, 'json');
  const date = today(Date.now());
  const fresh = stored?.date === date;
  const matches = fresh
    ? stored.matches.filter((m) => m.status in SHOWN).map((m) => ({ id: m.id, status: SHOWN[m.status], home: m.home, away: m.away }))
    : [];
  const body = { date, updatedAt: fresh ? stored.updatedAt : null, matches, attribution: ATTRIBUTION };
  return new Response(JSON.stringify(body), {
    headers: { ...cors(env), 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'public, max-age=30' },
  });
}

export default {
  fetch: serve,
  scheduled(event, env, ctx) {
    ctx.waitUntil(refresh(env, Date.now()));
  },
};

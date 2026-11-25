// node --test live/worker.test.js  (no dependencies)
import assert from 'node:assert/strict';
import { test } from 'node:test';
import worker, { needsFetch, refresh, today, trim } from './worker.js';

const ORIGIN = 'https://pages.example';
const NOW = Date.parse('2026-11-25T20:30:00Z');

function fakeKv(initial) {
  const store = new Map(initial ? [['today', JSON.stringify(initial)]] : []);
  const puts = [];
  return {
    puts,
    store,
    async get(key, type) {
      const v = store.get(key);
      return v === undefined ? null : type === 'json' ? JSON.parse(v) : v;
    },
    async put(key, value) {
      puts.push(key);
      store.set(key, value);
    },
  };
}

const env = (kv = fakeKv()) => ({ FOOTBALL_DATA_TOKEN: 'fd-test-token', SEASON: '2026', ALLOWED_ORIGIN: ORIGIN, LIVE: kv });

const fdMatch = (id, status, home, away, utcDate = '2026-11-25T20:00:00Z') => ({
  id, utcDate, status, lastUpdated: `2026-11-25T20:${String(id % 60).padStart(2, '0')}:00Z`,
  homeTeam: { id: 1 }, awayTeam: { id: 2 }, score: { fullTime: { home, away }, halfTime: { home: null, away: null } },
});

function fakeFetch(matches, status = 200) {
  const calls = [];
  const fn = async (url, init) => {
    calls.push({ url, init });
    return new Response(status === 200 ? JSON.stringify({ matches }) : '{"message":"nope"}', { status });
  };
  return { fn, calls };
}

test('today is the UTC date', () => {
  assert.equal(today(Date.parse('2026-11-25T23:59:59Z')), '2026-11-25');
  assert.equal(today(Date.parse('2026-11-26T00:00:00Z')), '2026-11-26');
});

test('trim keeps only id, kickoff, status and the current score', () => {
  assert.deepEqual(trim([fdMatch(7, 'IN_PLAY', 1, 0)]), [{ id: 7, utcDate: '2026-11-25T20:00:00Z', status: 'IN_PLAY', home: 1, away: 0 }]);
});

test('needsFetch: new day, live game or imminent kickoff only', () => {
  const day = (matches, date = '2026-11-25') => ({ date, updatedAt: 'x', matches });
  const m = (status, utcDate = '2026-11-25T20:00:00Z') => ({ id: 1, utcDate, status, home: null, away: null });
  assert.equal(needsFetch(null, NOW), true);
  assert.equal(needsFetch(day([], '2026-11-24'), NOW), true);
  assert.equal(needsFetch(day([]), NOW), false, 'no CL games today');
  assert.equal(needsFetch(day([m('FINISHED')]), NOW), false, 'all done');
  assert.equal(needsFetch(day([m('POSTPONED')]), NOW), false);
  for (const s of ['IN_PLAY', 'PAUSED', 'EXTRA_TIME', 'PENALTY_SHOOTOUT', 'SUSPENDED']) assert.equal(needsFetch(day([m(s)]), NOW), true, s);
  assert.equal(needsFetch(day([m('TIMED', '2026-11-25T20:34:00Z')]), NOW), true, 'kickoff in 4 min');
  assert.equal(needsFetch(day([m('TIMED', '2026-11-25T20:40:00Z')]), NOW), false, 'kickoff in 10 min');
  assert.equal(needsFetch(day([m('SCHEDULED', '2026-11-25T20:00:00Z')]), NOW), true, 'kickoff passed, status lagging');
});

test('refresh fetches today from football-data with the token and stores the trimmed list', async () => {
  const kv = fakeKv();
  const { fn, calls } = fakeFetch([fdMatch(7, 'IN_PLAY', 1, 0)]);
  assert.equal(await refresh(env(kv), NOW, fn), 'updated');
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, 'https://api.football-data.org/v4/competitions/CL/matches?season=2026&dateFrom=2026-11-25&dateTo=2026-11-25');
  assert.equal(calls[0].init.headers['X-Auth-Token'], 'fd-test-token');
  const saved = JSON.parse(kv.store.get('today'));
  assert.equal(saved.date, '2026-11-25');
  assert.equal(saved.updatedAt, '2026-11-25T20:30:00.000Z');
  assert.deepEqual(saved.matches, trim([fdMatch(7, 'IN_PLAY', 1, 0)]));
});

test('refresh writes KV only when the list changed', async () => {
  const kv = fakeKv();
  await refresh(env(kv), NOW, fakeFetch([fdMatch(7, 'IN_PLAY', 1, 0)]).fn);
  // Same score, newer lastUpdated: no write.
  const same = { ...fdMatch(7, 'IN_PLAY', 1, 0), lastUpdated: '2026-11-25T20:31:00Z' };
  assert.equal(await refresh(env(kv), NOW + 60_000, fakeFetch([same]).fn), 'unchanged');
  assert.equal(kv.puts.length, 1);
  assert.equal(await refresh(env(kv), NOW + 120_000, fakeFetch([fdMatch(7, 'IN_PLAY', 2, 0)]).fn), 'updated');
  assert.equal(kv.puts.length, 2);
});

test('refresh ignores a glitch that sends started games back to not-started', async () => {
  // Seen live on 2026-11-25 20:26 UTC: one response had every game TIMED with null scores.
  const kv = fakeKv();
  await refresh(env(kv), NOW, fakeFetch([fdMatch(7, 'IN_PLAY', 1, 0), fdMatch(8, 'FINISHED', 2, 2), fdMatch(9, 'TIMED', null, null)]).fn);
  const glitch = [fdMatch(7, 'TIMED', null, null), fdMatch(8, 'TIMED', null, null), fdMatch(9, 'TIMED', null, null)];
  assert.equal(await refresh(env(kv), NOW + 60_000, fakeFetch(glitch).fn), 'unchanged');
  assert.equal(kv.puts.length, 1);
  // Real progress still goes through, including a postponement of a game that had not started.
  const next = [fdMatch(7, 'FINISHED', 1, 0), fdMatch(8, 'FINISHED', 2, 2), fdMatch(9, 'POSTPONED', null, null)];
  assert.equal(await refresh(env(kv), NOW + 120_000, fakeFetch(next).fn), 'updated');
  assert.deepEqual(JSON.parse(kv.store.get('today')).matches.map((m) => m.status), ['FINISHED', 'FINISHED', 'POSTPONED']);
});

test('refresh skips football-data when nothing can have changed', async () => {
  const kv = fakeKv({ date: '2026-11-25', updatedAt: 'x', matches: [] });
  const { fn, calls } = fakeFetch([]);
  assert.equal(await refresh(env(kv), NOW, fn), 'skipped');
  assert.equal(calls.length, 0);
});

test('a failed football-data call throws without the token and leaves KV alone', async () => {
  const kv = fakeKv();
  await assert.rejects(refresh(env(kv), NOW, fakeFetch([], 429).fn), (e) => {
    assert.match(e.message, /429/);
    assert.ok(!e.message.includes('fd-test-token'));
    return true;
  });
  assert.equal(kv.puts.length, 0);
});

test('a missing token fails before any request', async () => {
  const { fn, calls } = fakeFetch([]);
  await assert.rejects(refresh({ ...env(), FOOTBALL_DATA_TOKEN: undefined }, NOW, fn), /FOOTBALL_DATA_TOKEN/);
  assert.equal(calls.length, 0);
});

async function get(kv, path = '/', method = 'GET') {
  const res = await worker.fetch(new Request(`https://live.example${path}`, { method }), env(kv));
  return { res, body: res.status === 200 ? await res.json() : null };
}

test('GET / serves live, half-time and finished games with CORS for the Pages origin only', async (t) => {
  t.mock.timers.enable({ apis: ['Date'], now: NOW });
  const kv = fakeKv({
    date: '2026-11-25', updatedAt: '2026-11-25T20:29:00.000Z',
    matches: [
      { id: 1, utcDate: '2026-11-25T20:00:00Z', status: 'IN_PLAY', home: 1, away: 0 },
      { id: 2, utcDate: '2026-11-25T20:00:00Z', status: 'PAUSED', home: 0, away: 0 },
      { id: 3, utcDate: '2026-11-25T17:45:00Z', status: 'FINISHED', home: 2, away: 2 },
      { id: 4, utcDate: '2026-11-25T21:00:00Z', status: 'TIMED', home: null, away: null },
      { id: 5, utcDate: '2026-11-25T20:00:00Z', status: 'EXTRA_TIME', home: 1, away: 1 },
    ],
  });
  const { res, body } = await get(kv);
  assert.equal(res.status, 200);
  assert.equal(res.headers.get('Access-Control-Allow-Origin'), ORIGIN);
  assert.match(res.headers.get('Content-Type'), /application\/json/);
  assert.match(res.headers.get('Cache-Control'), /max-age=30/);
  assert.equal(body.date, '2026-11-25');
  assert.equal(body.updatedAt, '2026-11-25T20:29:00.000Z');
  assert.match(body.attribution, /Football-Data\.org/);
  assert.deepEqual(body.matches, [
    { id: 1, status: 'IN_PLAY', home: 1, away: 0 },
    { id: 2, status: 'PAUSED', home: 0, away: 0 },
    { id: 3, status: 'FINISHED', home: 2, away: 2 },
    { id: 5, status: 'IN_PLAY', home: 1, away: 1 },
  ]);
});

test('GET / is empty when KV holds another day or nothing', async (t) => {
  t.mock.timers.enable({ apis: ['Date'], now: NOW });
  const stale = fakeKv({ date: '2026-11-24', updatedAt: 'x', matches: [{ id: 1, utcDate: 'x', status: 'IN_PLAY', home: 1, away: 0 }] });
  assert.deepEqual((await get(stale)).body.matches, []);
  const { body } = await get(fakeKv());
  assert.deepEqual(body.matches, []);
  assert.equal(body.updatedAt, null);
});

test('OPTIONS answers the preflight; other paths and methods are refused', async () => {
  const pre = await get(fakeKv(), '/', 'OPTIONS');
  assert.equal(pre.res.status, 204);
  assert.equal(pre.res.headers.get('Access-Control-Allow-Origin'), ORIGIN);
  assert.equal((await get(fakeKv(), '/other')).res.status, 404);
  assert.equal((await get(fakeKv(), '/', 'POST')).res.status, 405);
});

test('scheduled handler hands the refresh to waitUntil', async () => {
  const waited = [];
  const real = globalThis.fetch;
  globalThis.fetch = fakeFetch([]).fn;
  try {
    worker.scheduled({ cron: '* 16-23 * * tue-thu', scheduledTime: NOW }, env(), { waitUntil: (p) => waited.push(p) });
    assert.equal(waited.length, 1);
    await waited[0];
  } finally {
    globalThis.fetch = real;
  }
});

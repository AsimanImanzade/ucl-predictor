// node --test scheduler/worker.test.js  (no dependencies)
import assert from 'node:assert/strict';
import { test } from 'node:test';
import worker, { DAILY, dispatch } from './worker.js';

const env = { GITHUB_TOKEN: 'gh-test-token', REPO: 'owner/repo' };

function fakeFetch(status = 204, body = '') {
  const calls = [];
  const fn = async (url, init) => {
    calls.push({ url, init });
    return new Response(status === 204 ? null : body, { status });
  };
  return { fn, calls };
}

test('dispatches update.yml on main', async () => {
  const { fn, calls } = fakeFetch();
  await dispatch(env, '*/15 16-23 * * tue-thu', fn);
  assert.equal(calls.length, 1);
  const { url, init } = calls[0];
  assert.equal(url, 'https://api.github.com/repos/owner/repo/actions/workflows/update.yml/dispatches');
  assert.equal(init.method, 'POST');
  assert.equal(init.headers.Authorization, 'Bearer gh-test-token');
  assert.ok(init.headers['User-Agent']);
  assert.deepEqual(JSON.parse(init.body), { ref: 'main', inputs: {} });
});

test('the daily trigger also refreshes the domestic leagues', async () => {
  const { fn, calls } = fakeFetch();
  await dispatch(env, DAILY, fn);
  assert.deepEqual(JSON.parse(calls[0].init.body), { ref: 'main', inputs: { domestic: 'true' } });
});

test('a failed dispatch throws without the token', async () => {
  const { fn } = fakeFetch(401, '{"message":"Bad credentials"}');
  await assert.rejects(dispatch(env, DAILY, fn), (e) => {
    assert.match(e.message, /401/);
    assert.ok(!e.message.includes(env.GITHUB_TOKEN));
    return true;
  });
});

test('a missing token fails before any request', async () => {
  const { fn, calls } = fakeFetch();
  await assert.rejects(dispatch({ REPO: 'owner/repo' }, DAILY, fn), /GITHUB_TOKEN/);
  assert.equal(calls.length, 0);
});

test('scheduled handler hands the dispatch to waitUntil', async () => {
  const waited = [];
  const real = globalThis.fetch;
  globalThis.fetch = fakeFetch().fn;
  try {
    worker.scheduled({ cron: DAILY }, env, { waitUntil: (p) => waited.push(p) });
    assert.equal(waited.length, 1);
    await waited[0];
  } finally {
    globalThis.fetch = real;
  }
});

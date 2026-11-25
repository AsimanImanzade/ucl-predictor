/**
 * Cloudflare Worker: reliable timer for the GitHub `update` workflow.
 * GitHub's own cron is best-effort (late or dropped runs), so Cloudflare cron
 * triggers call the workflow_dispatch API instead. Secret: GITHUB_TOKEN, a
 * fine-grained token limited to this repo with "Actions: read and write".
 */
export const DAILY = '0 6 * * *';
const WORKFLOW = 'update.yml';

export async function dispatch(env, cron, fetchFn = fetch) {
  if (!env.GITHUB_TOKEN) throw new Error('GITHUB_TOKEN secret is not set');
  const url = `https://api.github.com/repos/${env.REPO}/actions/workflows/${WORKFLOW}/dispatches`;
  const res = await fetchFn(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'ucl-predictor-scheduler',
      'Content-Type': 'application/json',
    },
    // The daily run also re-fetches the domestic leagues (inputs are strings).
    body: JSON.stringify({ ref: 'main', inputs: cron === DAILY ? { domestic: 'true' } : {} }),
  });
  if (res.status !== 204) {
    const detail = (await res.text()).slice(0, 200);
    throw new Error(`workflow dispatch failed: HTTP ${res.status} ${detail}`);
  }
}

export default {
  scheduled(event, env, ctx) {
    ctx.waitUntil(dispatch(env, event.cron));
  },
};

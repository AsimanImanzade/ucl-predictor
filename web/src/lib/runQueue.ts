/**
 * At most one job in flight; while busy, only the newest submitted job waits (older waiting
 * jobs are dropped). Keeps a slow Worker from working through stale what-if runs.
 */
export function createRunQueue<T>(send: (job: T) => void) {
  let busy = false;
  let waiting: { job: T } | null = null;
  return {
    submit(job: T) {
      if (busy) {
        waiting = { job };
        return;
      }
      busy = true;
      send(job);
    },
    /** Call when the in-flight job has answered (result or error). */
    done() {
      if (!busy) return;
      if (waiting) {
        const { job } = waiting;
        waiting = null;
        send(job);
      } else {
        busy = false;
      }
    },
  };
}

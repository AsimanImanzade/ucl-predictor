import { useId } from 'react';
import type { PointsThresholds } from '@uclpred/sim';
import { formatPct } from '../lib/format';
import { evenChance, MIN_SAMPLES, pointsRows } from '../lib/thresholds';
import { ProbCell } from './Prob';
import './PointsNeeded.css';

interface Props {
  thresholds: PointsThresholds;
  /** Live baseline from the same runs and seed: rows then show the change against it. */
  baseline?: PointsThresholds;
  runs: number;
  tone?: 'official' | 'scenario';
  /** Changes on every new result, so the change markers replay. */
  deltaKey?: string;
}

/** For each final points total: how often a club finishing on it made the top 8 and the top 24. */
export function PointsNeeded({ thresholds, baseline, runs, tone = 'official', deltaKey = '' }: Props) {
  const id = useId();
  const rows = pointsRows(thresholds, baseline);
  if (!rows.length) return null;
  const e8 = evenChance(rows, 'top8');
  const e24 = evenChance(rows, 'top24');
  const even = [e8 && `top 8 from ${e8.points} pts (${formatPct(e8.value)})`, e24 && `top 24 from ${e24.points} pts (${formatPct(e24.value)})`].filter(Boolean);
  const anyFew = rows.some((r) => r.top8 === null);
  const anyDelta = rows.some((r) => r.d8 !== null || r.d24 !== null);
  return (
    <section className={`points-needed points-needed--${tone}`} aria-labelledby={id}>
      <h2 id={id}>Points needed</h2>
      <p className="fineprint">
        How often a club that finished the league phase on each points total made the top 8 or the top 24, across all 36 clubs in{' '}
        {runs.toLocaleString('en-GB')} simulations.
      </p>
      {even.length > 0 && <p className="points-needed__key">More likely than not: {even.join(', ')}.</p>}
      <div className="panel points-needed__panel">
        <table className="ptable">
          <caption className="visually-hidden">Chance of a top-8 and a top-24 finish for each final points total</caption>
          <thead>
            <tr>
              <th scope="col">Final points</th>
              <th scope="col">Top 8</th>
              <th scope="col">Top 24</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.points} className={r.top8 === null ? 'is-few' : undefined}>
                <th scope="row">{r.points} pts</th>
                {r.top8 === null || r.top24 === null ? (
                  <td colSpan={2} className="ptable__few">
                    <span aria-hidden="true">—</span>
                    <span className="visually-hidden">Too few simulations finished on {r.points} points</span>
                  </td>
                ) : (
                  <>
                    <td>
                      <ProbCell key={`a${deltaKey}`} value={r.top8} tone={tone} delta={r.d8} />
                    </td>
                    <td>
                      <ProbCell key={`b${deltaKey}`} value={r.top24} tone={tone} delta={r.d24} />
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {(anyFew || anyDelta) && (
        <p className="fineprint table-note">
          {anyDelta && `Changes are against live chances from the same ${runs.toLocaleString('en-GB')} simulations; changes smaller than the simulation noise are not shown. `}
          {anyFew && `A dash means fewer than ${MIN_SAMPLES} simulated finishes on that total, too few to say.`}
        </p>
      )}
    </section>
  );
}

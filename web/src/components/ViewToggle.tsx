import { useSearchParams } from 'react-router';
import type { Manifest } from '../lib/types';
import './ViewToggle.css';

export const SCENARIO = 'scenario';

/** ?view=md02 | live | scenario; anything unknown falls back to live. */
export function useView(manifest: Manifest, allowScenario = false): [string, (v: string) => void] {
  const [params, setParams] = useSearchParams();
  const raw = params.get('view') ?? manifest.liveId;
  const valid = manifest.snapshots.some((s) => s.id === raw) || (allowScenario && raw === SCENARIO);
  const view = valid ? raw : manifest.liveId;
  const set = (v: string) =>
    setParams(
      (p) => {
        if (v === manifest.liveId) p.delete('view');
        else p.set('view', v);
        return p;
      },
      { replace: true, preventScrollReset: true },
    );
  return [view, set];
}

interface Props {
  manifest: Manifest;
  view: string;
  onChange: (v: string) => void;
  allowScenario?: boolean;
}

export function ViewToggle({ manifest, view, onChange, allowScenario }: Props) {
  const pre = manifest.snapshots.find((s) => s.matchday === 0);
  const after = manifest.snapshots.filter((s) => s.matchday !== null && s.matchday > 0);
  const isAfter = after.some((s) => s.id === view);
  const latestAfter = after.at(-1);
  return (
    <div className="view-toggle" role="group" aria-label="Forecast shown">
      {pre && (
        <button type="button" aria-pressed={view === pre.id} onClick={() => onChange(pre.id)}>
          Pre-season
        </button>
      )}
      {latestAfter && (
        <span className={`view-toggle__after${isAfter ? ' is-on' : ''}`}>
          <button type="button" aria-pressed={isAfter} onClick={() => onChange(isAfter ? view : latestAfter.id)}>
            After <span className="wide-only">matchday</span>
            <span className="narrow-only">MD</span>
          </button>
          <label className="visually-hidden" htmlFor="view-md">
            Matchday
          </label>
          <select id="view-md" value={isAfter ? view : latestAfter.id} onChange={(e) => onChange(e.target.value)}>
            {after.map((s) => (
              <option key={s.id} value={s.id}>
                {s.matchday}
              </option>
            ))}
          </select>
        </span>
      )}
      <button type="button" aria-pressed={view === manifest.liveId} onClick={() => onChange(manifest.liveId)}>
        Live
      </button>
      {allowScenario && (
        <button type="button" className="view-toggle__scenario" aria-pressed={view === SCENARIO} onClick={() => onChange(SCENARIO)}>
          <span className="wide-only">My scenario</span>
          <span className="narrow-only">Scenario</span>
        </button>
      )}
    </div>
  );
}

import { useMemo } from 'react';
import { useSearchParams } from 'react-router';
import type { Fixture } from '@uclpred/sim';
import { FixtureRow } from '../components/FixtureRow';
import { useManifest, useSnapshot, useTeams } from '../lib/data';
import { formatDate, formatDay } from '../lib/labels';
import { useLiveScores } from '../lib/liveScores';
import './pages.css';

export function MatchesPage() {
  const manifest = useManifest();
  const live = useSnapshot(manifest.liveId);
  const teams = useTeams();
  const scores = useLiveScores(live.season.fixtures);
  const [params, setParams] = useSearchParams();
  const mds = useMemo(() => [...new Set(live.season.fixtures.map((f) => f.matchday))].sort((a, b) => a - b), [live]);
  const next = mds.find((md) => live.season.fixtures.some((f) => f.matchday === md && !f.played)) ?? mds.at(-1)!;
  const asked = Number(params.get('md'));
  const md = mds.includes(asked) ? asked : next;

  const days = useMemo(() => {
    const fx = live.season.fixtures.filter((f) => f.matchday === md).sort((a, b) => (a.utcDate < b.utcDate ? -1 : a.utcDate > b.utcDate ? 1 : a.id - b.id));
    const out = new Map<string, Fixture[]>();
    for (const f of fx) {
      const d = formatDay(f.utcDate);
      out.set(d, [...(out.get(d) ?? []), f]);
    }
    return [...out.entries()];
  }, [live, md]);
  const played = live.season.fixtures.filter((f) => f.matchday === md && f.played).length;

  return (
    <div className="page">
      <header className="page-head">
        <h1>Matches</h1>
        <p className="fineprint">
          Results and forecasts for all 144 league-phase matches. Kick-off times are in your time zone. Forecasts use live data as of{' '}
          {formatDate(live.meta.asOf)}.
        </p>
        <nav className="md-tabs" aria-label="Matchday">
          {mds.map((n) => (
            <button
              key={n}
              type="button"
              aria-pressed={n === md}
              className={n === next ? 'is-next' : undefined}
              onClick={() => setParams({ md: String(n) }, { replace: true, preventScrollReset: true })}
            >
              <span className="visually-hidden">Matchday </span>
              {n}
            </button>
          ))}
        </nav>
      </header>
      <section aria-labelledby="md-title">
        <div className="md-head">
          <h2 id="md-title">Matchday {md}</h2>
          <span className="fineprint">{played === 0 ? 'Not started' : played === 18 ? 'All results in' : `${played} of 18 played`}</span>
        </div>
        {days.map(([day, fx]) => (
          <div key={day} className="md-day">
            <h3 className="md-day__title">{day}</h3>
            <ul className="fixtures">
              {fx.map((f) => (
                <FixtureRow key={f.id} fixture={f} teams={teams} lambdas={live.lambdas} live={scores.get(f.id)} />
              ))}
            </ul>
          </div>
        ))}
      </section>
    </div>
  );
}

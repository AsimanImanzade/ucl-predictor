import { Suspense, useMemo, useState } from 'react';
import { Link } from 'react-router';
import type { Stage } from '@uclpred/sim';
import { Loading } from '../components/Layout';
import { ProbCell } from '../components/Prob';
import { TeamBadge } from '../components/TeamBadge';
import { useView, ViewToggle } from '../components/ViewToggle';
import { certainty } from '../lib/certainty';
import { useManifest, useSnapshot, useTeams } from '../lib/data';
import { progressLabel } from '../lib/labels';
import { standings } from '../lib/standings';
import '../components/LeagueTable.css';
import './pages.css';

const COLS: { key: Stage; label: string; title: string }[] = [
  { key: 'po', label: 'PO', title: 'Plays the knockout play-off round (finishes 9th to 24th)' },
  { key: 'r16', label: 'R16', title: 'Reaches the round of 16' },
  { key: 'qf', label: 'QF', title: 'Reaches the quarter-finals' },
  { key: 'sf', label: 'SF', title: 'Reaches the semi-finals' },
  { key: 'final', label: 'Final', title: 'Reaches the final' },
  { key: 'winner', label: 'Winner', title: 'Wins the competition' },
];

function OddsTable({ id }: { id: string }) {
  const snap = useSnapshot(id);
  const teams = useTeams();
  const [sort, setSort] = useState<Stage>('winner');
  const rows = useMemo(() => standings(snap.season), [snap]);
  const cert = useMemo(() => new Map(rows.map((r) => [r.teamId, certainty(snap.season, r.teamId, rows)])), [snap, rows]);
  const sorted = useMemo(
    () => [...snap.chances].sort((a, b) => b.reach[sort] - a.reach[sort] || b.reach.winner - a.reach.winner || (a.teamId < b.teamId ? -1 : 1)),
    [snap, sort],
  );
  return (
    <div className="table-panel">
      <div className="table-scroll">
        <table className="ltable">
          <caption className="visually-hidden">Chance of reaching each knockout stage, {snap.meta.label}</caption>
          <thead>
            <tr>
              <th className="col-rank" scope="col">
                <span className="visually-hidden">Order</span>
              </th>
              <th className="col-team" scope="col">Team</th>
              {COLS.map((c) => (
                <th key={c.key} scope="col" aria-sort={sort === c.key ? 'descending' : undefined}>
                  <button type="button" className={`th-sort${sort === c.key ? ' is-on' : ''}`} onClick={() => setSort(c.key)} title={c.title}>
                    {c.label}
                    <span aria-hidden="true">{sort === c.key ? ' ▾' : ''}</span>
                    <span className="visually-hidden">, sort by {c.title.toLowerCase()}</span>
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((c, i) => {
              const t = teams[c.teamId]!;
              const k = cert.get(c.teamId) ?? {};
              const out = k.top24 === 'eliminated' ? ('eliminated' as const) : undefined;
              return (
                <tr key={c.teamId}>
                  <td className="col-rank">{i + 1}</td>
                  <td className="col-team">
                    <Link className="team-link" to={`/team/${c.teamId}`}>
                      <TeamBadge team={t} />
                    </Link>
                  </td>
                  {COLS.map((col) => (
                    <td key={col.key} className="col-prob">
                      <ProbCell value={c.reach[col.key]} certainty={col.key === 'r16' && k.top8 === 'clinched' ? 'clinched' : col.key === 'po' ? undefined : out} />
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function LiveLabel({ id }: { id: string }) {
  const snap = useSnapshot(id);
  return <>Live: {progressLabel(snap.season).toLowerCase()}</>;
}

export function KnockoutPage() {
  const manifest = useManifest();
  const [view, setView] = useView(manifest);
  const label = manifest.snapshots.find((s) => s.id === view)?.label ?? '';
  const liveLabel = view === manifest.liveId ? <LiveLabel id={view} /> : null;
  return (
    <div className="page">
      <header className="page-head">
        <div className="page-head__row">
          <h1>Knockout odds</h1>
          <ViewToggle manifest={manifest} view={view} onChange={setView} />
        </div>
        <p className="snapshot">{liveLabel ?? label}</p>
        <p className="fineprint">
          Every club&rsquo;s chance of reaching each stage. Clubs finishing 9th to 24th play the knockout play-off round; the top 8 go straight to the
          round of 16. The real bracket appears here once the draws are made. Estimates from 50,000 simulations, not certainties.
        </p>
      </header>
      <Suspense fallback={<Loading />}>
        <OddsTable id={view} />
      </Suspense>
    </div>
  );
}

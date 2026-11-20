import { Suspense, useMemo } from 'react';
import type { TeamChances } from '@uclpred/sim';
import { Loading } from '../components/Layout';
import { StandingsTable } from '../components/StandingsTable';
import { SCENARIO, useView, ViewToggle } from '../components/ViewToggle';
import { certainty } from '../lib/certainty';
import { useManifest, useSnapshot, useTeams } from '../lib/data';
import { formatDate, formatStamp, progressLabel } from '../lib/labels';
import { standings } from '../lib/standings';
import { ScenarioTable } from './ScenarioTable';
import './pages.css';

function SnapshotTable({ id }: { id: string }) {
  const snap = useSnapshot(id);
  const teams = useTeams();
  const rows = useMemo(() => standings(snap.season), [snap]);
  const chances = useMemo(() => new Map<string, TeamChances>(snap.chances.map((c) => [c.teamId, c])), [snap]);
  const cert = useMemo(() => new Map(rows.map((r) => [r.teamId, certainty(snap.season, r.teamId, rows)])), [snap, rows]);
  const live = snap.meta.id === 'live';
  return (
    <>
      <p className="snapshot">
        {live ? `Live: ${progressLabel(snap.season).toLowerCase()}` : snap.meta.label}
        <span className="fineprint"> (data as of {live ? formatStamp(snap.meta.asOf) : formatDate(snap.meta.asOf)})</span>
      </p>
      <StandingsTable rows={rows} chances={chances} teams={teams} certainty={cert} caption={`League phase table, ${snap.meta.label}`} />
    </>
  );
}

export function TablePage() {
  const manifest = useManifest();
  const [view, setView] = useView(manifest, true);
  return (
    <div className="page">
      <header className="page-head">
        <div className="page-head__row">
          <h1>League phase</h1>
          <ViewToggle manifest={manifest} view={view} onChange={setView} allowScenario />
        </div>
        <p className="fineprint">
          Points table plus each club&rsquo;s chance of a top-8 finish, a top-24 finish and the title. Estimates from{' '}
          {view === SCENARIO ? '20,000' : '50,000'} simulations, not certainties.
        </p>
      </header>
      <Suspense fallback={<Loading />}>{view === SCENARIO ? <ScenarioTable /> : <SnapshotTable id={view} />}</Suspense>
    </div>
  );
}

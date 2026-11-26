import { Suspense, useMemo } from 'react';
import type { TeamChances } from '@uclpred/sim';
import { Loading } from '../components/Layout';
import { PointsNeeded } from '../components/PointsNeeded';
import { StandingsTable } from '../components/StandingsTable';
import { SCENARIO, useView, ViewToggle } from '../components/ViewToggle';
import { certainty } from '../lib/certainty';
import { useManifest, useSnapshot, useTeams } from '../lib/data';
import { formatDate, formatStamp, progressLabel } from '../lib/labels';
import { useLiveScores } from '../lib/liveScores';
import { asItStands, liveCount, playingNow } from '../lib/liveTable';
import { standings } from '../lib/standings';
import { ScenarioTable } from './ScenarioTable';
import './pages.css';

function SnapshotTable({ id }: { id: string }) {
  const snap = useSnapshot(id);
  const teams = useTeams();
  const live = snap.meta.id === 'live';
  // Only the live view follows games in progress; past snapshots stay as they were.
  const scores = useLiveScores(live ? snap.season.fixtures : NO_FIXTURES);
  const official = useMemo(() => standings(snap.season), [snap]);
  const { running, finished } = live ? liveCount(snap.season, scores) : { running: 0, finished: 0 };
  const inPlay = running + finished;
  const rows = useMemo(() => {
    if (!inPlay) return official;
    // Form stays on finished games only.
    const form = new Map(official.map((r) => [r.teamId, r.form]));
    return standings(asItStands(snap.season, scores)).map((r) => ({ ...r, form: form.get(r.teamId)! }));
  }, [official, snap, scores, inPlay]);
  const playing = useMemo(() => (inPlay ? playingNow(snap.season, scores) : undefined), [snap, scores, inPlay]);
  const chances = useMemo(() => new Map<string, TeamChances>(snap.chances.map((c) => [c.teamId, c])), [snap]);
  // "Qualified" / "Out" only from finished games.
  const cert = useMemo(() => new Map(official.map((r) => [r.teamId, certainty(snap.season, r.teamId, official)])), [snap, official]);
  return (
    <>
      <p className="snapshot">
        {live ? `Live: ${progressLabel(snap.season).toLowerCase()}` : snap.meta.label}
        <span className="fineprint"> (data as of {live ? formatStamp(snap.meta.asOf) : formatDate(snap.meta.asOf)})</span>
      </p>
      {inPlay > 0 && (
        <p className="fineprint live-note">
          As it stands, with {[running && `${running} ${running === 1 ? 'game' : 'games'} in progress`, finished && `${finished} just finished`].filter(Boolean).join(' and ')}
          : points, goals and places use the latest scores, updated every minute, and a red dot marks the clubs playing now. The chances update after
          full time, once the results are official.
        </p>
      )}
      <StandingsTable rows={rows} chances={chances} teams={teams} certainty={cert} playing={playing} caption={`League phase table, ${snap.meta.label}`} />
      {/* Snapshots stored before 2026-11-26 have no thresholds. */}
      {snap.thresholds && <PointsNeeded thresholds={snap.thresholds} runs={snap.meta.runs} />}
    </>
  );
}

const NO_FIXTURES: never[] = [];

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

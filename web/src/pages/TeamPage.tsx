import { useMemo } from 'react';
import { Link, useParams } from 'react-router';
import { HistoryChart, PositionChart } from '../components/Charts';
import { ProbCell, WdlBar } from '../components/Prob';
import { TeamBadge } from '../components/TeamBadge';
import { certainty } from '../lib/certainty';
import { useAllSnapshots, useManifest, useSnapshot, useTeams } from '../lib/data';
import { formatPct } from '../lib/format';
import { formatKickoff, progressLabel } from '../lib/labels';
import { matchProbs } from '../lib/match';
import { standings } from '../lib/standings';
import type { Stage } from '@uclpred/sim';
import './pages.css';
import './TeamPage.css';

const STAGES: { key: Stage; label: string }[] = [
  { key: 'po', label: 'Play-off round' },
  { key: 'r16', label: 'Round of 16' },
  { key: 'qf', label: 'Quarter-finals' },
  { key: 'sf', label: 'Semi-finals' },
  { key: 'final', label: 'Final' },
  { key: 'winner', label: 'Winner' },
];

const ordinal = (n: number) => `${n}${n % 10 === 1 && n !== 11 ? 'st' : n % 10 === 2 && n !== 12 ? 'nd' : n % 10 === 3 && n !== 13 ? 'rd' : 'th'}`;
const shortLabel = (id: string, matchday: number | null) => (id === 'live' ? 'Live' : matchday === 0 ? 'Pre' : `MD${matchday}`);

function History({ teamId }: { teamId: string }) {
  const snaps = useAllSnapshots();
  const series = (f: (c: (typeof snaps)[number]['chances'][number]) => number) =>
    snaps.map((s) => ({ label: shortLabel(s.meta.id, s.meta.matchday), value: f(s.chances.find((c) => c.teamId === teamId)!) }));
  return (
    <section className="section" aria-labelledby="hist-title">
      <h2 id="hist-title">How the chances have moved</h2>
      <p className="fineprint section-note">One forecast before matchday 1, one after each completed matchday, and the live one.</p>
      <div className="history-grid">
        <div className="panel">
          <HistoryChart title="Top 8" points={series((c) => c.top8)} />
        </div>
        <div className="panel">
          <HistoryChart title="Top 24" points={series((c) => c.top24)} />
        </div>
        <div className="panel">
          <HistoryChart title="Winner" points={series((c) => c.reach.winner)} />
        </div>
      </div>
    </section>
  );
}

export function TeamPage() {
  const { id = '' } = useParams();
  const manifest = useManifest();
  const live = useSnapshot(manifest.liveId);
  const teams = useTeams();
  const team = teams[id];
  const rows = useMemo(() => standings(live.season), [live]);
  if (!team) {
    return (
      <div className="page page-state">
        <h1>Club not found</h1>
        <p>
          That club is not in this season&rsquo;s league phase. <Link to="/">See the table</Link>.
        </p>
      </div>
    );
  }
  const row = rows.find((r) => r.teamId === id)!;
  const c = live.chances.find((x) => x.teamId === id)!;
  const cert = certainty(live.season, id, rows);
  const elo = live.ratings?.[id];
  const fixtures = live.season.fixtures.filter((f) => f.homeId === id || f.awayId === id).sort((a, b) => a.matchday - b.matchday);
  const outCert = cert.top24 === 'eliminated' ? 'eliminated' : undefined;
  const stageCert = (s: Stage) => (s === 'r16' && cert.top8 === 'clinched' ? 'clinched' : s === 'po' && cert.top8 === 'clinched' ? undefined : outCert);

  return (
    <div className="page">
      <header className="team-head">
        <TeamBadge team={team} size={72} label="none" />
        <div>
          <h1>{team.name}</h1>
          <p className="muted">
            {team.fullName}
            {team.venue ? `, ${team.venue}` : ''}
          </p>
        </div>
      </header>

      <dl className="stat-tiles">
        <div className="stat">
          <dt>League position</dt>
          <dd>
            <span className="stat__value">{row.played ? ordinal(row.rank) : '–'}</span>
            <span className="stat__note">
              {row.pts} pts from {row.played} {row.played === 1 ? 'match' : 'matches'}
            </span>
          </dd>
        </div>
        <div className="stat">
          <dt>Expected final points</dt>
          <dd>
            <span className="stat__value num">{c.expectedPoints.toFixed(1)}</span>
            <span className="stat__note">average over 50,000 simulations</span>
          </dd>
        </div>
        {elo !== undefined && (
          <div className="stat">
            <dt>Elo rating</dt>
            <dd>
              <span className="stat__value num">{Math.round(elo)}</span>
              <span className="stat__note">our own league-aware Elo</span>
            </dd>
          </div>
        )}
        <div className="stat">
          <dt>UEFA coefficient</dt>
          <dd>
            <span className="stat__value num">{team.coefficient.toFixed(1)}</span>
            <span className="stat__note">five-season club total</span>
          </dd>
        </div>
      </dl>

      <section className="section" aria-labelledby="chances-title">
        <h2 id="chances-title">Chances now</h2>
        <p className="fineprint section-note">
          Live: {progressLabel(live.season).toLowerCase()}. Estimates from 50,000 simulations, not certainties.
        </p>
        <ul className="stage-list panel">
          <li>
            <span className="stage-list__label">Top 8</span>
            <ProbCell value={c.top8} certainty={cert.top8} />
          </li>
          <li>
            <span className="stage-list__label">Top 24</span>
            <ProbCell value={c.top24} certainty={cert.top8 === 'clinched' ? 'clinched' : cert.top24} />
          </li>
          {STAGES.map((s) => (
            <li key={s.key}>
              <span className="stage-list__label">{s.key === 'po' ? 'Plays the play-off round' : s.key === 'winner' ? 'Wins the competition' : `Reaches the ${s.label.toLowerCase()}`}</span>
              <ProbCell value={c.reach[s.key]} certainty={stageCert(s.key)} />
            </li>
          ))}
        </ul>
      </section>

      <History teamId={id} />

      <section className="section" aria-labelledby="pos-title">
        <h2 id="pos-title">Where they could finish</h2>
        <div className="panel">
          <PositionChart position={c.position} highlight={row.played ? row.rank : undefined} />
        </div>
      </section>

      <section className="section" aria-labelledby="fx-title">
        <h2 id="fx-title">League-phase matches</h2>
        <ul className="team-fixtures">
          {fixtures.map((f) => {
            const isHome = f.homeId === id;
            const opp = teams[isHome ? f.awayId : f.homeId]!;
            const m = f.played ? null : matchProbs(live.lambdas, f.homeId, f.awayId);
            const res = f.played ? (f.homeGoals! === f.awayGoals! ? 'D' : f.homeGoals! > f.awayGoals! === isHome ? 'W' : 'L') : null;
            return (
              <li key={f.id} className="team-fx panel">
                <span className="team-fx__md">MD{f.matchday}</span>
                <span className="team-fx__opp">
                  <span className="team-fx__venue">{isHome ? 'Home' : 'Away'} v</span>
                  <Link to={`/team/${opp.id}`}>
                    <TeamBadge team={opp} />
                  </Link>
                </span>
                <span className="team-fx__when fineprint">{formatKickoff(f.utcDate)}</span>
                {f.played ? (
                  <Link to={`/match/${f.id}`} className={`team-fx__result team-fx__result--${res}`}>
                    <span className="visually-hidden">{res === 'W' ? 'Won' : res === 'D' ? 'Drew' : 'Lost'} </span>
                    <span className="num">
                      {f.homeGoals}&ndash;{f.awayGoals}
                    </span>
                  </Link>
                ) : (
                  <Link to={`/match/${f.id}`} className="team-fx__odds" aria-label={`${team.name} v ${opp.name}: win ${formatPct(isHome ? m!.home : m!.away)}, draw ${formatPct(m!.draw)}, loss ${formatPct(isHome ? m!.away : m!.home)}`}>
                    {/* From this club's side: win on the left, loss on the right. */}
                    <WdlBar home={isHome ? m!.home : m!.away} draw={m!.draw} away={isHome ? m!.away : m!.home} homeLabel="Win" awayLabel="Loss" />
                  </Link>
                )}
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}

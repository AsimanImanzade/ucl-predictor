import { Link, useParams } from 'react-router';
import { Heatmap } from '../components/Heatmap';
import { WdlBar } from '../components/Prob';
import { TeamBadge } from '../components/TeamBadge';
import { formatPct } from '../lib/format';
import { snapshotBefore, useManifest, useSnapshot, useTeams } from '../lib/data';
import { formatDate, formatDay, formatTime } from '../lib/labels';
import { matchProbs } from '../lib/match';
import './pages.css';
import './MatchPage.css';

function Forecast({ snapshotId, homeId, awayId, actual }: { snapshotId: string; homeId: string; awayId: string; actual: [number, number] | null }) {
  const snap = useSnapshot(snapshotId);
  const teams = useTeams();
  const home = teams[homeId]!;
  const away = teams[awayId]!;
  const m = matchProbs(snap.lambdas, homeId, awayId);
  const exact = actual ? m.grid[Math.min(actual[0], 5)]?.[Math.min(actual[1], 5)] : undefined;
  const outcome = actual ? (actual[0] > actual[1] ? m.home : actual[0] === actual[1] ? m.draw : m.away) : undefined;
  const live = snap.meta.id === 'live';
  return (
    <section className="section" aria-labelledby="forecast-title">
      <h2 id="forecast-title">{actual ? 'Pre-match forecast' : 'Forecast'}</h2>
      <p className="fineprint forecast-source">
        {live ? `Live forecast, data as of ${formatDate(snap.meta.asOf)}.` : `From the ${snap.meta.label.toLowerCase()} forecast, data as of ${formatDate(snap.meta.asOf)}.`}
        {actual && outcome !== undefined && exact !== undefined && (
          <>
            {' '}
            The model gave the actual outcome {formatPct(outcome)}
            {actual[0] <= 5 && actual[1] <= 5 ? ` and the exact score ${formatPct(exact)}` : ''}.
          </>
        )}
      </p>
      <div className="forecast-grid">
        <div className="panel forecast-main">
          <WdlBar home={m.home} draw={m.draw} away={m.away} homeLabel={home.name} awayLabel={away.name} />
          <dl className="xg">
            <div>
              <dt>Expected goals</dt>
              <dd className="num">
                {m.lambdaHome.toFixed(2)} &ndash; {m.lambdaAway.toFixed(2)}
              </dd>
            </div>
          </dl>
          <div>
            <h3 className="likely-title">Most likely scores</h3>
            <ol className="likely-scores">
              {m.top.map((s, i) => (
                <li key={i}>
                  <span className="likely-scores__score num">
                    {s.home}&ndash;{s.away}
                  </span>
                  <span className="likely-scores__p num">{formatPct(s.p)}</span>
                </li>
              ))}
            </ol>
          </div>
        </div>
        <div className="panel">
          <h3 className="likely-title">Every score</h3>
          <Heatmap grid={m.grid} homeLabel={home.name} awayLabel={away.name} />
        </div>
      </div>
    </section>
  );
}

export function MatchPage() {
  const { id } = useParams();
  const manifest = useManifest();
  const live = useSnapshot(manifest.liveId);
  const teams = useTeams();
  const f = live.season.fixtures.find((x) => String(x.id) === id);
  if (!f) {
    return (
      <div className="page page-state">
        <h1>Match not found</h1>
        <p>
          There is no league-phase match with that number. <Link to="/matches">See all matches</Link>.
        </p>
      </div>
    );
  }
  const home = teams[f.homeId]!;
  const away = teams[f.awayId]!;
  const forecastId = snapshotBefore(manifest, f.utcDate) ?? manifest.liveId;
  const actual: [number, number] | null = f.played ? [f.homeGoals!, f.awayGoals!] : null;
  return (
    <div className="page">
      <p className="fineprint">
        <Link to={`/matches?md=${f.matchday}`}>Matchday {f.matchday}</Link>
      </p>
      <header className="scoreboard">
        <Link to={`/team/${home.id}`} className="scoreboard__team">
          <TeamBadge team={home} size={44} label="none" />
          <span className="scoreboard__name">{home.name}</span>
        </Link>
        <div className="scoreboard__mid">
          {actual ? (
            <span className="scoreboard__score num">
              {actual[0]}&ndash;{actual[1]}
            </span>
          ) : (
            <span className="scoreboard__time num">{formatTime(f.utcDate)}</span>
          )}
          <span className="fineprint">{actual ? 'Full time' : 'Kick-off, your time'}</span>
        </div>
        <Link to={`/team/${away.id}`} className="scoreboard__team scoreboard__team--away">
          <TeamBadge team={away} size={44} label="none" />
          <span className="scoreboard__name">{away.name}</span>
        </Link>
      </header>
      <h1 className="visually-hidden">
        {home.name} v {away.name}
      </h1>
      <p className="match-meta">
        {formatDay(f.utcDate)}
        {home.venue ? `, ${home.venue}` : ''}
      </p>
      <Forecast snapshotId={forecastId} homeId={f.homeId} awayId={f.awayId} actual={actual} />
    </div>
  );
}

import { Link } from 'react-router';
import type { Fixture, Lambdas } from '@uclpred/sim';
import { formatPct } from '../lib/format';
import type { LiveScore } from '../lib/liveScores';
import { formatTime } from '../lib/labels';
import { matchProbs } from '../lib/match';
import type { TeamsFile } from '../lib/types';
import { LiveBadge } from './LiveBadge';
import { WdlBar } from './Prob';
import { TeamBadge } from './TeamBadge';
import './FixtureRow.css';

interface Props {
  fixture: Fixture;
  teams: TeamsFile;
  /** Live lambdas for upcoming fixtures. */
  lambdas: Lambdas;
  /** Live score from the Worker; ignored once live.json counts the game. */
  live?: LiveScore;
}

export function FixtureRow({ fixture: f, teams, lambdas, live: liveScore }: Props) {
  const home = teams[f.homeId]!;
  const away = teams[f.awayId]!;
  const m = f.played ? null : matchProbs(lambdas, f.homeId, f.awayId);
  const live = f.played ? undefined : liveScore;
  const score = f.played ? ([f.homeGoals, f.awayGoals] as const) : live ? ([live.home, live.away] as const) : null;
  const label = `${home.name} v ${away.name}${live ? `, ${live.status === 'FINISHED' ? 'full-time' : 'live'} score ${live.home}–${live.away}` : ''}, match details`;
  return (
    <li className={`fx${f.played ? ' fx--played' : ''}${live && live.status !== 'FINISHED' ? ' fx--live' : ''}`}>
      <span className="fx__time">{live ? <LiveBadge status={live.status} /> : formatTime(f.utcDate)}</span>
      <span className="fx__team fx__team--home">
        <TeamBadge team={home} />
      </span>
      <Link className="fx__score" to={`/match/${f.id}`} aria-label={label}>
        {score ? (
          <span className="num">
            {score[0]}&ndash;{score[1]}
          </span>
        ) : (
          <span className="fx__v">v</span>
        )}
      </Link>
      <span className="fx__team fx__team--away">
        <TeamBadge team={away} />
      </span>
      {m && (
        <span className="fx__odds">
          <WdlBar home={m.home} draw={m.draw} away={m.away} homeLabel={home.name} awayLabel={away.name} compact />
          <span className="fx__likely">
            Likeliest:{' '}
            {m.top.map((s, i) => (
              <span key={i} className="fx__likely-item">
                <span className="num">
                  {s.home}&ndash;{s.away}
                </span>{' '}
                <span className="fx__likely-p num">{formatPct(s.p)}</span>
              </span>
            ))}
          </span>
        </span>
      )}
    </li>
  );
}

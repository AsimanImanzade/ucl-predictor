import { Link } from 'react-router';
import type { TeamChances, TeamId } from '@uclpred/sim';
import type { TeamCertainty } from '../lib/certainty';
import type { StandingRow } from '../lib/standings';
import type { TeamsFile } from '../lib/types';
import { useFlip } from '../lib/useFlip';
import { PitchMarkings } from './Frame';
import { FormPills } from './Form';
import { ProbCell } from './Prob';
import { TeamBadge } from './TeamBadge';
import './LeagueTable.css';

export interface RowDeltas {
  top8: number | null;
  top24: number | null;
  winner: number | null;
}

interface Props {
  rows: StandingRow[];
  chances: Map<TeamId, TeamChances>;
  teams: TeamsFile;
  certainty?: Map<TeamId, TeamCertainty>;
  tone?: 'official' | 'scenario';
  deltas?: Map<TeamId, RowDeltas>;
  /** Changes when a new scenario result arrives, so the delta fade replays. */
  deltaKey?: string | number;
  caption: string;
  /** Narrow panel: points and chances only. */
  compact?: boolean;
}

const zone = (rank: number) => (rank <= 8 ? 'top8' : rank <= 24 ? 'playoff' : 'out');
const signed = (n: number) => (n > 0 ? `+${n}` : n < 0 ? `−${-n}` : '0');

export function StandingsTable({ rows, chances, teams, certainty, tone = 'official', deltas, deltaKey, caption, compact }: Props) {
  const ref = useFlip<HTMLTableSectionElement>(rows.map((r) => r.teamId).join());
  return (
    <div className="table-panel">
      <PitchMarkings />
      <div className="table-scroll">
        <table className={`ltable${compact ? ' ltable--compact' : ''}`}>
          <caption className="visually-hidden">{caption}</caption>
          <thead>
            <tr>
              <th className="col-rank" scope="col">
                <abbr title="Position">#</abbr>
              </th>
              <th className="col-team" scope="col">Team</th>
              <th scope="col" className="hide-sm"><abbr title="Played">P</abbr></th>
              <th scope="col" className="hide-sm"><abbr title="Won">W</abbr></th>
              <th scope="col" className="hide-sm"><abbr title="Drawn">D</abbr></th>
              <th scope="col" className="hide-sm"><abbr title="Lost">L</abbr></th>
              <th scope="col" className="hide-sm hide-md"><abbr title="Goals for">GF</abbr></th>
              <th scope="col" className="hide-sm hide-md"><abbr title="Goals against">GA</abbr></th>
              <th scope="col" className="hide-compact"><abbr title="Goal difference">GD</abbr></th>
              <th scope="col"><abbr title="Points">Pts</abbr></th>
              <th scope="col" className="col-gap hide-sm">Form</th>
              <th scope="col" className="col-gap">Top 8</th>
              <th scope="col">Top 24</th>
              <th scope="col">Winner</th>
            </tr>
          </thead>
          <tbody ref={ref}>
            {rows.map((r) => {
              const c = chances.get(r.teamId);
              const t = teams[r.teamId]!;
              const cert = certainty?.get(r.teamId) ?? {};
              const d = deltas?.get(r.teamId);
              const top24Cert = cert.top8 === 'clinched' ? 'clinched' : cert.top24;
              const outCert = cert.top24 === 'eliminated' ? 'eliminated' : undefined;
              return (
                <tr key={r.teamId} data-key={r.teamId} data-zone={zone(r.rank)}>
                  <td className="col-rank">{r.rank}</td>
                  <td className="col-team">
                    <Link className="team-link" to={`/team/${r.teamId}`}>
                      <TeamBadge team={t} />
                    </Link>
                  </td>
                  <td className="muted hide-sm">{r.played}</td>
                  <td className="muted hide-sm">{r.won}</td>
                  <td className="muted hide-sm">{r.drawn}</td>
                  <td className="muted hide-sm">{r.lost}</td>
                  <td className="muted hide-sm hide-md">{r.gf}</td>
                  <td className="muted hide-sm hide-md">{r.ga}</td>
                  <td className="muted hide-compact">{signed(r.gd)}</td>
                  <td className="col-pts">{r.pts}</td>
                  <td className="col-gap hide-sm">
                    <FormPills form={r.form} />
                  </td>
                  {c ? (
                    <>
                      <td className="col-gap col-prob">
                        <ProbCell key={`a${deltaKey}`} value={c.top8} certainty={cert.top8} tone={tone} delta={d?.top8} />
                      </td>
                      <td className="col-prob">
                        <ProbCell key={`b${deltaKey}`} value={c.top24} certainty={top24Cert} tone={tone} delta={d?.top24} />
                      </td>
                      <td className="col-prob">
                        <ProbCell key={`c${deltaKey}`} value={c.reach.winner} certainty={outCert} tone={tone} delta={d?.winner} />
                      </td>
                    </>
                  ) : (
                    <td className="col-gap" colSpan={3} />
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="zone-key">
        <span className="zone-key__item">
          <span className="zone-key__swatch zone-key__swatch--top8" /> Top 8: straight to the round of 16
        </span>
        <span className="zone-key__item">
          <span className="zone-key__swatch zone-key__swatch--playoff" /> 9 to 24: knockout play-off
        </span>
        <span className="zone-key__item">25 to 36: out</span>
      </div>
    </div>
  );
}

import { useMemo } from 'react';
import { Link } from 'react-router';
import type { TeamChances } from '@uclpred/sim';
import { DroppedNotice } from '../components/DroppedNotice';
import { StandingsTable, type RowDeltas } from '../components/StandingsTable';
import { useManifest, useSnapshot, useTeams } from '../lib/data';
import { shownDelta } from '../lib/delta';
import { useLiveScores } from '../lib/liveScores';
import { playingNow, usedGuessCount, withLive } from '../lib/liveTable';
import { applyGuesses } from '../lib/scenario';
import { useReconciledScenario } from '../lib/scenarioStore';
import { standings } from '../lib/standings';
import { useScenarioSim } from '../lib/useScenarioSim';

export function ScenarioTable() {
  const manifest = useManifest();
  const live = useSnapshot(manifest.liveId);
  const teams = useTeams();
  const { guesses, dropped } = useReconciledScenario(live.season);
  const scores = useLiveScores(live.season.fixtures);
  const scenario = useMemo(() => withLive(guesses, live.season, scores), [guesses, live.season, scores]);
  const playing = useMemo(() => playingNow(live.season, scores), [live.season, scores]);
  const sim = useScenarioSim(live, scenario);
  const count = Object.keys(scenario).length;
  const mine = usedGuessCount(guesses, scenario);
  const fromLive = count - mine;
  const parts = [
    mine > 0 && `${mine} ${mine === 1 ? 'score' : 'scores'} you entered`,
    fromLive > 0 && `${fromLive} live ${fromLive === 1 ? 'score' : 'scores'}`,
  ].filter(Boolean);
  const rows = useMemo(() => standings(applyGuesses(live.season, scenario)), [live, scenario]);

  const { chances, deltas } = useMemo(() => {
    const res = sim.result;
    const base = sim.baseline;
    if (!res) return { chances: null, deltas: undefined };
    const ch = new Map<string, TeamChances>(res.chances.map((c) => [c.teamId, c]));
    if (!base) return { chances: ch, deltas: undefined };
    const b = new Map(base.chances.map((c) => [c.teamId, c]));
    const d = new Map<string, RowDeltas>();
    for (const c of res.chances) {
      const o = b.get(c.teamId)!;
      d.set(c.teamId, {
        top8: shownDelta(c.top8, o.top8, res.runs),
        top24: shownDelta(c.top24, o.top24, res.runs),
        winner: shownDelta(c.reach.winner, o.reach.winner, res.runs),
      });
    }
    return { chances: ch, deltas: d };
  }, [sim.result, sim.baseline]);

  if (count === 0) {
    return (
      <>
        <DroppedNotice dropped={dropped} season={live.season} teams={teams} />
        <div className="panel empty">
          <p>You have not entered any scores yet. Pick results for upcoming matches and this table shows where they leave every club.</p>
          <Link className="btn btn--primary" to="/what-if">
            Enter scores
          </Link>
        </div>
      </>
    );
  }

  return (
    <>
      <DroppedNotice dropped={dropped} season={live.season} teams={teams} />
      <p className="snapshot">
        My scenario: live data plus {parts.join(' and ')}.{' '}
        <Link to="/what-if" className="fineprint">
          Edit scores
        </Link>
      </p>
      {sim.error && (
        <p className="notice" role="alert">
          The simulation stopped: {sim.error}
        </p>
      )}
      {chances ? (
        <StandingsTable
          rows={rows}
          chances={chances}
          teams={teams}
          tone="scenario"
          deltas={deltas}
          deltaKey={sim.result?.asOf + String(sim.ms)}
          caption="League phase table with your scenario"
          playing={playing}
        />
      ) : (
        <p className="fineprint" aria-live="polite">
          Simulating your scenario…
        </p>
      )}
      <p className="fineprint table-note">Changes are against live chances from the same 20,000 simulations; changes smaller than the simulation noise are not shown.</p>
    </>
  );
}

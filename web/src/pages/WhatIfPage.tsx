import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import type { Fixture, TeamChances } from '@uclpred/sim';
import { DroppedNotice } from '../components/DroppedNotice';
import { LiveBadge } from '../components/LiveBadge';
import { StandingsTable, type RowDeltas } from '../components/StandingsTable';
import { TeamBadge } from '../components/TeamBadge';
import { useManifest, useSnapshot, useTeams } from '../lib/data';
import { shownDelta } from '../lib/delta';
import { formatDelta } from '../lib/format';
import { formatDate, formatKickoff } from '../lib/labels';
import { useLiveScores, type LiveScore } from '../lib/liveScores';
import { playingNow, usedGuessCount, withLive } from '../lib/liveTable';
import { applyGuesses, decodeGuesses, encodeGuesses, MAX_GOALS, reconcile, type Guess, type Guesses } from '../lib/scenario';
import { scenarioStore, useReconciledScenario } from '../lib/scenarioStore';
import { standings } from '../lib/standings';
import type { TeamsFile } from '../lib/types';
import { useScenarioSim } from '../lib/useScenarioSim';
import './pages.css';
import './WhatIfPage.css';

function GoalInput({ value, onChange, label }: { value: string; onChange: (v: string) => void; label: string }) {
  return (
    <input
      className="goal-input num"
      type="text"
      inputMode="numeric"
      pattern="[0-9]*"
      maxLength={2}
      placeholder="–"
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value.replace(/\D/g, '').slice(0, 2))}
      onFocus={(e) => e.target.select()}
    />
  );
}

interface GuessRowProps {
  f: Fixture;
  teams: TeamsFile;
  /** The user's own score. */
  guess?: Guess;
  /** Live score: pre-fills a game in play; locks the game at full time. */
  live?: LiveScore;
  onChange: (g: Guess | null) => void;
}

function GuessRow({ f, teams, guess, live, onChange }: GuessRowProps) {
  const home = teams[f.homeId]!;
  const away = teams[f.awayId]!;
  const shown = guess ?? (live ? { homeGoals: live.home, awayGoals: live.away } : undefined);
  const [h, setH] = useState(shown ? String(shown.homeGoals) : '');
  const [a, setA] = useState(shown ? String(shown.awayGoals) : '');
  const inputs = useRef<HTMLSpanElement>(null);
  const restore = () => {
    setH(shown ? String(shown.homeGoals) : '');
    setA(shown ? String(shown.awayGoals) : '');
  };
  // Follow outside changes (reset, shared link, a dropped guess, a goal in a live game),
  // but never under the user's fingers: a half-typed score waits for blur.
  useEffect(() => {
    if (!inputs.current?.contains(document.activeElement)) restore();
  }, [shown?.homeGoals, shown?.awayGoals]); // eslint-disable-line react-hooks/exhaustive-deps

  const commit = (nh: string, na: string) => {
    const hg = Number(nh);
    const ag = Number(na);
    if (nh !== '' && na !== '' && hg <= MAX_GOALS && ag <= MAX_GOALS) onChange({ homeGoals: hg, awayGoals: ag });
    else if (nh === '' && na === '') onChange(null);
  };

  const fullTime = !f.played && live?.status === 'FINISHED';
  if (f.played || fullTime) {
    return (
      <li className="guess guess--locked">
        <span className="guess__team guess__team--home">
          <TeamBadge team={home} />
        </span>
        <span className="guess__locked num" title="Played: the real result is used">
          {f.played ? f.homeGoals : live!.home}&ndash;{f.played ? f.awayGoals : live!.away}
        </span>
        <span className="guess__team">
          <TeamBadge team={away} />
        </span>
        <span className="guess__meta fineprint">
          {fullTime ? (
            <>
              <LiveBadge status="FINISHED" /> Full time, result locked
            </>
          ) : (
            'Played, result locked'
          )}
        </span>
      </li>
    );
  }
  const inPlay = live && !f.played;
  return (
    <li className={`guess${guess ? ' guess--set' : ''}${inPlay ? ' guess--live' : ''}`}>
      <span className="guess__team guess__team--home">
        <TeamBadge team={home} />
      </span>
      <span
        className="guess__inputs"
        ref={inputs}
        onBlur={(e) => {
          // Leaving the row with a box blank shows what the scenario uses again (your score or the live one).
          if (!e.currentTarget.contains(e.relatedTarget as Node | null) && (h === '' || a === '')) restore();
        }}
      >
        <GoalInput
          label={`${home.name} goals`}
          value={h}
          onChange={(v) => {
            setH(v);
            commit(v, a);
          }}
        />
        <span aria-hidden="true">&ndash;</span>
        <GoalInput
          label={`${away.name} goals`}
          value={a}
          onChange={(v) => {
            setA(v);
            commit(h, v);
          }}
        />
      </span>
      <span className="guess__team">
        <TeamBadge team={away} />
      </span>
      <span className="guess__meta fineprint">
        {inPlay ? (
          <>
            <LiveBadge status={live.status} /> {guess ? `real score ${live.home}–${live.away}` : 'live score, type to change it'}
          </>
        ) : (
          formatKickoff(f.utcDate)
        )}
        {guess && (
          <button
            type="button"
            className="link-btn"
            onClick={() => onChange(null)}
            aria-label={inPlay ? `Back to the live score for ${home.name} v ${away.name}` : `Clear guess for ${home.name} v ${away.name}`}
          >
            {inPlay ? 'Use live score' : 'Clear'}
          </button>
        )}
      </span>
    </li>
  );
}

export function WhatIfPage() {
  const manifest = useManifest();
  const live = useSnapshot(manifest.liveId);
  const teams = useTeams();
  const [params, setParams] = useSearchParams();
  const { guesses, dropped } = useReconciledScenario(live.season);
  const [sharedNote, setSharedNote] = useState<{ count: number; previous: Guesses } | null>(null);
  const [copied, setCopied] = useState<'idle' | 'copied' | 'failed'>('idle');

  // A shared link (?s=...) replaces the scenario once; Undo restores the previous one.
  const shared = params.get('s');
  useEffect(() => {
    if (shared === null) return;
    const { kept, dropped: d } = reconcile(decodeGuesses(shared), live.season);
    const previous = scenarioStore.get().guesses;
    scenarioStore.setGuesses(kept);
    scenarioStore.addDropped(d);
    setSharedNote({ count: Object.keys(kept).length, previous });
    setParams((p) => {
      p.delete('s');
      return p;
    }, { replace: true });
  }, [shared, live.season, setParams]);

  const scores = useLiveScores(live.season.fixtures);
  // Games in play count at their live score unless you typed one; full time locks them.
  const scenario = useMemo(() => withLive(guesses, live.season, scores), [guesses, live.season, scores]);
  const playing = useMemo(() => playingNow(live.season, scores), [live.season, scores]);
  const sim = useScenarioSim(live, scenario);
  const count = Object.keys(guesses).length;
  const used = Object.keys(scenario).length;
  const mineUsed = usedGuessCount(guesses, scenario);
  const setGuess = (id: number, g: Guess | null) => {
    const next = { ...scenarioStore.get().guesses };
    if (g) next[id] = g;
    else delete next[id];
    scenarioStore.setGuesses(next);
  };

  const groups = useMemo(() => {
    const open = new Set(live.season.fixtures.filter((f) => !f.played).map((f) => f.matchday));
    return [...open]
      .sort((a, b) => a - b)
      .map((md) => ({
        md,
        fixtures: live.season.fixtures.filter((f) => f.matchday === md).sort((a, b) => (a.utcDate < b.utcDate ? -1 : a.utcDate > b.utcDate ? 1 : a.id - b.id)),
      }));
  }, [live]);

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

  const mover = useMemo(() => {
    if (!deltas || !used) return null;
    let best: { id: string; label: string; d: number } | null = null;
    for (const [id, d] of deltas) {
      for (const [label, v] of [['top 8', d.top8], ['top 24', d.top24], ['title', d.winner]] as const) {
        if (v !== null && (!best || Math.abs(v) > Math.abs(best.d))) best = { id, label, d: v };
      }
    }
    return best;
  }, [deltas, used]);

  const copyLink = async () => {
    const url = `${window.location.origin}/what-if?s=${encodeGuesses(guesses)}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied('copied');
    } catch {
      setCopied('failed');
      window.prompt('Copy this link', url);
    }
    setTimeout(() => setCopied('idle'), 2500);
  };

  return (
    <div className="page">
      <header className="page-head">
        <h1>What-if</h1>
        <p className="lead">
          Enter scores for matches that have not been played. The rest of the competition is simulated 20,000 times in your browser, and the table
          shows how each club&rsquo;s chances change against live.
        </p>
        <p className="fineprint">
          Live data as of {formatDate(live.meta.asOf)}. Played matches are locked to their real results. Games in play start at their live score,
          which you can change, and lock at full time. Your scores are saved in this browser.
        </p>
      </header>

      <DroppedNotice dropped={dropped} season={live.season} teams={teams} />
      {sharedNote && (
        <div className="notice" role="status">
          <p>
            Loaded a shared scenario with {sharedNote.count} {sharedNote.count === 1 ? 'score' : 'scores'}. It replaced the scores you had saved.
          </p>
          <button
            type="button"
            className="btn btn--quiet"
            onClick={() => {
              scenarioStore.setGuesses(sharedNote.previous);
              setSharedNote(null);
            }}
          >
            Undo
          </button>
        </div>
      )}

      <div className="whatif">
        <section className="whatif__editor" aria-label="Your scores">
          <div className="whatif__toolbar">
            <span className="fineprint">
              {mineUsed === 0 ? 'No scores entered yet' : `${mineUsed} ${mineUsed === 1 ? 'score' : 'scores'} entered`}
            </span>
            <button type="button" className="btn" onClick={copyLink} disabled={count === 0}>
              {copied === 'copied' ? 'Link copied' : 'Copy link'}
            </button>
            <button type="button" className="btn btn--quiet" onClick={() => scenarioStore.setGuesses({})} disabled={count === 0}>
              Reset
            </button>
          </div>
          {groups.map((g) => (
            <div key={g.md} className="md-day">
              <h2 className="whatif__md">Matchday {g.md}</h2>
              <ul className="guesses">
                {g.fixtures.map((f) => (
                  <GuessRow key={f.id} f={f} teams={teams} guess={guesses[f.id]} live={scores.get(f.id)} onChange={(x) => setGuess(f.id, x)} />
                ))}
              </ul>
            </div>
          ))}
          <div className="whatif__bar" aria-live="polite">
            <p>
              {used === 0 ? (
                'Enter a score to see the chances move.'
              ) : sim.running ? (
                'Simulating…'
              ) : mover ? (
                <>
                  Biggest change: <strong>{teams[mover.id]?.name}</strong> {mover.label} {formatDelta(mover.d)} points
                </>
              ) : (
                'No change bigger than the simulation noise.'
              )}
            </p>
            <a className="btn" href="#scenario-results">
              See table
            </a>
          </div>
        </section>

        <section className="whatif__results" id="scenario-results" aria-label="Your scenario" aria-busy={sim.running}>
          <div className="whatif__results-head">
            <h2>Your scenario</h2>
            <span className="fineprint" aria-live="polite">
              {sim.error
                ? `The simulation stopped: ${sim.error}`
                : sim.running
                  ? 'Simulating…'
                  : sim.ms !== null
                    ? `20,000 runs in ${(sim.ms / 1000).toFixed(1)} s`
                    : ''}
            </span>
          </div>
          {chances ? (
            <StandingsTable
              rows={rows}
              chances={chances}
              teams={teams}
              tone="scenario"
              deltas={used ? deltas : undefined}
              deltaKey={String(sim.ms)}
              caption="League phase table with your scores"
              playing={playing}
              compact
            />
          ) : (
            <p className="fineprint">Simulating…</p>
          )}
          <p className="fineprint table-note">
            Changes are against live chances from the same 20,000 simulations; changes smaller than the simulation noise are not shown. A red dot
            marks the clubs playing now.{' '}
            <Link to="/?view=scenario">Open the full table</Link>.
          </p>
        </section>
      </div>
    </div>
  );
}

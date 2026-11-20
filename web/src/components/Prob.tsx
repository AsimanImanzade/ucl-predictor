import { formatDelta, formatPct, type Certainty } from '../lib/format';
import './Prob.css';

interface MeterProps {
  value: number;
  certainty?: Certainty;
  /** "scenario" draws in the beam accent: numbers from the user's what-if. */
  tone?: 'official' | 'scenario';
  delta?: number | null;
}

/** A probability as text with a thin meter underneath. The number is the primary read. */
export function ProbCell({ value, certainty, tone = 'official', delta }: MeterProps) {
  const width = Math.max(0, Math.min(1, value)) * 100;
  return (
    <span className={`prob prob--${tone}`}>
      <span className="prob__row">
        {delta != null && <Delta value={delta} />}
        <span className="prob__value">{formatPct(value, certainty)}</span>
      </span>
      <span className="prob__track" aria-hidden="true">
        <span className="prob__fill" style={{ width: `${width}%` }} />
      </span>
    </span>
  );
}

/** Change vs live in percentage points. Sign and arrow carry the direction, colour reinforces it. */
export function Delta({ value }: { value: number }) {
  const text = formatDelta(value);
  if (text === null) return null;
  const up = value > 0;
  return (
    <span className={`delta delta--${up ? 'rise' : 'fall'}`}>
      <span aria-hidden="true">{up ? '▲' : '▼'}</span>
      {text}
      <span className="visually-hidden"> points vs live</span>
    </span>
  );
}

interface WdlProps {
  home: number;
  draw: number;
  away: number;
  homeLabel: string;
  awayLabel: string;
  /** Thin bar with numbers only (fixture lists). */
  compact?: boolean;
}

/** Win / draw / loss as one positional bar: home left, draw centre, away right, each labelled. */
export function WdlBar({ home, draw, away, homeLabel, awayLabel, compact }: WdlProps) {
  const seg = [
    { key: 'home', p: home, label: homeLabel },
    { key: 'draw', p: draw, label: 'Draw' },
    { key: 'away', p: away, label: awayLabel },
  ];
  return (
    <div className={`wdl${compact ? ' wdl--compact' : ''}`} role="img" aria-label={`${homeLabel} win ${formatPct(home)}, draw ${formatPct(draw)}, ${awayLabel} win ${formatPct(away)}`}>
      <div className="wdl__bar" aria-hidden="true">
        {seg.map((s) => (
          <span key={s.key} className={`wdl__seg wdl__seg--${s.key}`} style={{ flexGrow: s.p }} />
        ))}
      </div>
      <div className="wdl__labels" aria-hidden="true">
        {seg.map((s) => (
          <span key={s.key} className={`wdl__label wdl__label--${s.key}`}>
            <span className="wdl__pct">{formatPct(s.p)}</span>
            <span className="wdl__who">{s.label}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

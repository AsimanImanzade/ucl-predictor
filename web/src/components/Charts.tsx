import { formatPct } from '../lib/format';
import './Charts.css';

export interface HistoryPoint {
  label: string;
  value: number;
}

/** One measure over the snapshots: its own y-axis from 0, direct labels on the first and last points. */
export function HistoryChart({ title, points }: { title: string; points: HistoryPoint[] }) {
  const W = 300;
  const H = 150;
  const pad = { l: 34, r: 44, t: 14, b: 26 };
  const max = Math.max(...points.map((p) => p.value));
  const top = max <= 0.05 ? 0.05 : max <= 0.2 ? 0.2 : max <= 0.5 ? 0.5 : 1;
  const x = (i: number) => pad.l + (i * (W - pad.l - pad.r)) / Math.max(1, points.length - 1);
  const y = (v: number) => pad.t + (1 - v / top) * (H - pad.t - pad.b);
  const path = points.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join('');
  const ticks = [0, top / 2, top];
  const last = points.at(-1)!;
  return (
    <figure className="chart">
      <figcaption className="chart__title">{title}</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${title}: ${points.map((p) => `${p.label} ${formatPct(p.value)}`).join(', ')}`}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} className="chart__grid" />
            <text x={pad.l - 6} y={y(t) + 4} className="chart__tick" textAnchor="end">
              {Math.round(t * 100)}%
            </text>
          </g>
        ))}
        {points.map((p, i) => (
          <text key={p.label} x={x(i)} y={H - 8} className="chart__tick" textAnchor="middle">
            {p.label}
          </text>
        ))}
        <path d={path} className="chart__line" />
        {points.map((p, i) => (
          <circle key={p.label} cx={x(i)} cy={y(p.value)} r={i === points.length - 1 ? 4.5 : 3.5} className="chart__dot">
            <title>{`${p.label}: ${formatPct(p.value)}`}</title>
          </circle>
        ))}
        <text x={x(points.length - 1) + 8} y={y(last.value) + 4} className="chart__value">
          {formatPct(last.value)}
        </text>
      </svg>
    </figure>
  );
}

/** P(final league position) as 36 thin bars; zones by shade and by the axis notes. */
export function PositionChart({ position, highlight }: { position: number[]; highlight?: number }) {
  const W = 640;
  const H = 170;
  const pad = { l: 8, r: 8, t: 22, b: 30 };
  const n = position.length;
  const max = Math.max(...position, 0.0001);
  const bw = (W - pad.l - pad.r) / n;
  const best = position.indexOf(max);
  const zone = (k: number) => (k < 8 ? 'top8' : k < 24 ? 'playoff' : 'out');
  return (
    <figure className="chart chart--wide">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Most likely final position ${best + 1} (${formatPct(max)})`}>
        {position.map((p, k) => {
          const h = (p / max) * (H - pad.t - pad.b);
          return (
            <rect
              key={k}
              x={pad.l + k * bw + 1}
              y={H - pad.b - h}
              width={bw - 2}
              height={Math.max(h, p > 0 ? 1 : 0)}
              rx={2}
              className={`chart__bar chart__bar--${zone(k)}${k + 1 === highlight ? ' is-current' : ''}`}
            >
              <title>{`Position ${k + 1}: ${formatPct(p)}`}</title>
            </rect>
          );
        })}
        <text x={pad.l + best * bw + bw / 2} y={H - pad.b - (H - pad.t - pad.b) - 6} textAnchor="middle" className="chart__value">
          {formatPct(max)}
        </text>
        <line x1={pad.l + 8 * bw} x2={pad.l + 8 * bw} y1={pad.t - 4} y2={H - pad.b + 4} className="chart__zone-line" />
        <line x1={pad.l + 24 * bw} x2={pad.l + 24 * bw} y1={pad.t - 4} y2={H - pad.b + 4} className="chart__zone-line" />
        {[1, 8, 9, 24, 25, 36].map((k) => (
          <text key={k} x={pad.l + (k - 1) * bw + bw / 2} y={H - 10} textAnchor="middle" className="chart__tick">
            {k}
          </text>
        ))}
      </svg>
      <figcaption className="fineprint">Chance of each final league-phase position. Lines mark the top-8 and top-24 cut-offs.</figcaption>
    </figure>
  );
}

export interface CalibrationBin {
  lo: number;
  hi: number;
  n: number;
  meanPred: number | null;
  observed: number | null;
}

/** Reliability diagram: predicted home-win chance vs how often the home side won; diagonal = perfect. */
export function CalibrationChart({ bins }: { bins: CalibrationBin[] }) {
  const S = 300;
  const pad = { l: 40, r: 12, t: 12, b: 36 };
  const w = S - pad.l - pad.r;
  const h = S - pad.t - pad.b;
  const x = (v: number) => pad.l + v * w;
  const y = (v: number) => pad.t + (1 - v) * h;
  const pts = bins.filter((b): b is CalibrationBin & { meanPred: number; observed: number } => b.n > 0 && b.meanPred !== null && b.observed !== null);
  const ticks = [0, 0.25, 0.5, 0.75, 1];
  return (
    <figure className="chart chart--square">
      <svg viewBox={`0 0 ${S} ${S}`} role="img" aria-label="Calibration: predicted home-win chance against observed home-win rate, by bin">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={x(0)} x2={x(1)} y1={y(t)} y2={y(t)} className="chart__grid" />
            <text x={pad.l - 6} y={y(t) + 4} textAnchor="end" className="chart__tick">
              {t * 100}%
            </text>
            <text x={x(t)} y={S - pad.b + 16} textAnchor="middle" className="chart__tick">
              {t * 100}%
            </text>
          </g>
        ))}
        <line x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} className="chart__zone-line" />
        <path d={pts.map((b, i) => `${i ? 'L' : 'M'}${x(b.meanPred)},${y(b.observed)}`).join('')} className="chart__line" />
        {pts.map((b) => (
          <circle key={b.lo} cx={x(b.meanPred)} cy={y(b.observed)} r={Math.max(4, Math.min(9, Math.sqrt(b.n) / 3))} className="chart__dot">
            <title>{`Predicted ${(b.meanPred * 100).toFixed(1)}%, observed ${(b.observed * 100).toFixed(1)}% (${b.n} matches)`}</title>
          </circle>
        ))}
        <text x={x(0.5)} y={S - 4} textAnchor="middle" className="chart__tick">
          Predicted home-win chance
        </text>
        <text transform={`translate(10 ${y(0.5)}) rotate(-90)`} textAnchor="middle" className="chart__tick">
          Home side won
        </text>
      </svg>
    </figure>
  );
}

import { formatPct } from '../lib/format';
import './Heatmap.css';

/** Sequential blue ramp for a dark surface: low values recede toward the panel, high values glow. */
const LOW = [0x1b, 0x2e, 0x61];
const HIGH = [0xcd, 0xe2, 0xfb];

function shade(t: number): { bg: string; ink: string } {
  const c = LOW.map((lo, i) => Math.round(lo + (HIGH[i]! - lo) * t));
  return { bg: `rgb(${c.join(',')})`, ink: t > 0.55 ? 'var(--night)' : 'var(--floodlight)' };
}

interface Props {
  grid: number[][];
  homeLabel: string;
  awayLabel: string;
}

/** Score heatmap: home goals down, away goals across; every cell carries its value. */
export function Heatmap({ grid, homeLabel, awayLabel }: Props) {
  const max = Math.max(...grid.flat());
  const n = grid.length;
  const label = (k: number) => (k === n - 1 ? `${k}+` : String(k));
  return (
    <div className="heatmap">
      <table>
        <caption className="visually-hidden">
          Probability of each exact score, {homeLabel} goals by row, {awayLabel} goals by column
        </caption>
        <thead>
          <tr>
            <th scope="col" className="heatmap__corner">
              <span className="heatmap__axis heatmap__axis--home">{homeLabel}</span>
              <span className="heatmap__axis heatmap__axis--away">{awayLabel}</span>
            </th>
            {grid[0]!.map((_, a) => (
              <th key={a} scope="col">
                {label(a)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {grid.map((row, h) => (
            <tr key={h}>
              <th scope="row">{label(h)}</th>
              {row.map((p, a) => {
                const { bg, ink } = shade(Math.sqrt(p / max));
                return (
                  <td key={a} style={{ background: bg, color: ink }} title={`${label(h)}–${label(a)}: ${formatPct(p)}`}>
                    {formatPct(p)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

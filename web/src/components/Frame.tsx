import type { ReactNode } from 'react';
import { Link } from 'react-router';
import './Frame.css';

/** Deterministic sparse starfield: a fixed LCG so stars never move between renders. */
function stars(count: number): { x: number; y: number; r: number; o: number }[] {
  let s = 20262027;
  const next = () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 2 ** 32;
  };
  return Array.from({ length: count }, () => ({
    x: next() * 1000,
    y: next() * 600,
    r: 0.5 + next() * 0.9,
    o: 0.18 + next() * 0.5,
  }));
}

const STARS = stars(64);

export function Sky() {
  return (
    <div className="sky" aria-hidden="true">
      <svg viewBox="0 0 1000 600" preserveAspectRatio="xMidYMid slice">
        {STARS.map((st, i) => (
          <circle key={i} cx={st.x} cy={st.y} r={st.r} fill="#f5f8ff" opacity={st.o} />
        ))}
      </svg>
    </div>
  );
}

/** Faint halfway line and centre circle behind a table, about 4% opacity. */
export function PitchMarkings() {
  return (
    <svg className="pitch" viewBox="0 0 400 300" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
      <g fill="none" stroke="#f5f8ff" strokeWidth="1.5">
        <line x1="200" y1="0" x2="200" y2="300" />
        <circle cx="200" cy="150" r="60" />
        <circle cx="200" cy="150" r="2.5" fill="#f5f8ff" />
      </g>
    </svg>
  );
}

export function Mark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect x="7" y="4" width="18" height="11" rx="2" fill="#14244f" stroke="#c9d3e6" strokeWidth="1.2" />
      <g fill="#f5f8ff">
        {[11.5, 16, 20.5].flatMap((cx) => [7.8, 11.6].map((cy) => <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="1.8" />))}
      </g>
      <path d="M13 28 16 15.5 19 28M14.2 23h3.6" fill="none" stroke="#c9d3e6" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  );
}

export function SiteHeader({ nav }: { nav?: ReactNode }) {
  return (
    <header className="site-header">
      <div className="site-header__inner">
        <Link className="brand" to="/">
          <Mark />
          <span className="brand__text">
            <span className="brand__name">Floodlit</span>
            <span className="brand__desc">2026/27 Champions League forecasts</span>
          </span>
        </Link>
        {nav}
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="site-footer__inner">
        <p>Unofficial fan project, not affiliated with UEFA or the clubs.</p>
        <p>
          Football data provided by the{' '}
          <a href="https://www.football-data.org/" rel="noopener">
            Football-Data.org API
          </a>
          .
        </p>
      </div>
    </footer>
  );
}

/** Generic kit colours for football-data.org `clubColors` names (not club-specific shades). */
const NAMED: Record<string, string> = {
  black: '#15171c',
  white: '#f4f6fa',
  red: '#d01f2f',
  blue: '#1f4fbf',
  'navy blue': '#14295e',
  'dark blue': '#102a6b',
  'sky blue': '#78b7e6',
  'light blue': '#8cc4ec',
  claret: '#7b1e3a',
  maroon: '#7a1f2b',
  yellow: '#f5c400',
  gold: '#c9a227',
  orange: '#f07c1b',
  green: '#138a43',
  purple: '#5b2a86',
};

export const FALLBACK_COLOR = '#5d6c94';

/** "Red / Blue / White" -> up to two hex colours for the kill-switch chip. */
export function parseClubColors(raw: string | null | undefined): string[] {
  const out = (raw ?? '')
    .split('/')
    .map((s) => NAMED[s.trim().toLowerCase()])
    .filter((c): c is string => c !== undefined)
    .slice(0, 2);
  return out.length > 0 ? out : [FALLBACK_COLOR];
}

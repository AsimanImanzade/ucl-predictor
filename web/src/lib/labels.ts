import type { Season } from '@uclpred/sim';

/** "Before matchday 1", "After matchday 4", "During matchday 5 (9 of 18 played)". */
export function progressLabel(season: Season): string {
  const mds = [...new Set(season.fixtures.map((f) => f.matchday))].sort((a, b) => a - b);
  let complete = 0;
  for (const md of mds) {
    const fx = season.fixtures.filter((f) => f.matchday === md);
    const played = fx.filter((f) => f.played).length;
    if (played === fx.length) {
      complete = md;
      continue;
    }
    if (played > 0) return `During matchday ${md} (${played} of ${fx.length} played)`;
    break;
  }
  if (complete === 0) return 'Before matchday 1';
  if (complete === mds.at(-1)) return 'League phase complete';
  return `After matchday ${complete}`;
}

const kickoffFmt = new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
const dayFmt = new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long' });
const dateFmt = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
const timeFmt = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit' });

/** Kick-off in the viewer's own time zone. */
export const formatKickoff = (utc: string) => kickoffFmt.format(new Date(utc));
export const formatDay = (utc: string) => dayFmt.format(new Date(utc));
export const formatDate = (utc: string) => dateFmt.format(new Date(utc));
export const formatTime = (utc: string) => timeFmt.format(new Date(utc));

const stampFmt = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' });
/** A data timestamp with its time zone ("10 Nov 2026, 20:05 GMT+4"). */
export const formatStamp = (utc: string) => stampFmt.format(new Date(utc));

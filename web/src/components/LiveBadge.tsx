import type { LiveStatus } from '../lib/liveScores';
import './LiveBadge.css';

const LABEL: Record<LiveStatus, { short: string; long: string; kind: string }> = {
  IN_PLAY: { short: 'LIVE', long: 'Live', kind: 'live' },
  PAUSED: { short: 'HT', long: 'Half time', kind: 'live' },
  FINISHED: { short: 'FT', long: 'Full time', kind: 'ft' },
};

/** Red pill while the game is on (LIVE / HT), quiet outline once it ends (FT). */
export function LiveBadge({ status }: { status: LiveStatus }) {
  const l = LABEL[status];
  return (
    <span className={`live-badge live-badge--${l.kind}`}>
      <span aria-hidden="true">{l.short}</span>
      <span className="visually-hidden">{l.long}</span>
    </span>
  );
}

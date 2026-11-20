import { useState } from 'react';
import { SHOW_CRESTS } from '../lib/config';
import './TeamBadge.css';

export interface BadgeTeam {
  name: string;
  /** Unique 3-letter code shown with the colour chip. */
  code: string;
  crest: string;
  colors: string[];
}

interface Props {
  team: BadgeTeam;
  /** What to print next to the mark. */
  label?: 'name' | 'code' | 'none';
  size?: number;
  /** Override the build-time kill switch (used by the design sample). */
  showCrests?: boolean;
}

/** Crest, or (kill switch off / image failed) a two-tone colour chip plus the short code. */
export function TeamBadge({ team, label = 'name', size = 22, showCrests = SHOW_CRESTS }: Props) {
  const [failed, setFailed] = useState(false);
  const crest = showCrests && !failed && team.crest !== '';
  const [c1, c2 = c1] = team.colors;
  return (
    <span className="badge">
      {crest ? (
        <img
          className="badge__crest"
          src={team.crest}
          width={size}
          height={size}
          alt=""
          decoding="async"
          onError={() => setFailed(true)}
        />
      ) : (
        <span
          className="badge__chip"
          aria-hidden="true"
          style={{ width: size, height: size, background: `linear-gradient(135deg, ${c1} 0 50%, ${c2} 50% 100%)` }}
        />
      )}
      {!crest && label === 'name' && team.code.toLowerCase() !== team.name.toLowerCase() && (
        <span className="badge__code">{team.code}</span>
      )}
      {label === 'name' && <span className="badge__name">{team.name}</span>}
      {label === 'code' && <span className="badge__code badge__code--solo">{team.code}</span>}
      {label === 'none' && <span className="visually-hidden">{team.name}</span>}
    </span>
  );
}

import type { Season } from '@uclpred/sim';
import type { DroppedGuess } from '../lib/scenario';
import { scenarioStore } from '../lib/scenarioStore';
import type { TeamsFile } from '../lib/types';

/** Says which saved guesses were removed because the real match has been played. */
export function DroppedNotice({ dropped, season, teams }: { dropped: DroppedGuess[]; season: Season; teams: TeamsFile }) {
  if (!dropped.length) return null;
  const byId = new Map(season.fixtures.map((f) => [f.id, f]));
  return (
    <div className="notice" role="status">
      <div>
        <p>
          <strong>
            {dropped.length === 1 ? 'One of your guesses was removed' : `${dropped.length} of your guesses were removed`}
          </strong>{' '}
          because the real match has been played. Real results always replace guesses.
        </p>
        <ul className="dropped-list">
          {dropped.map((d) => {
            const f = byId.get(d.fixtureId);
            const name = (id?: string) => (id ? (teams[id]?.name ?? id) : '?');
            return (
              <li key={d.fixtureId}>
                {name(f?.homeId)} v {name(f?.awayId)}: your guess {d.guess.homeGoals}&ndash;{d.guess.awayGoals}, result{' '}
                {d.actual.homeGoals}&ndash;{d.actual.awayGoals}
              </li>
            );
          })}
        </ul>
      </div>
      <button type="button" className="btn btn--quiet" onClick={() => scenarioStore.dismissDropped()}>
        Dismiss
      </button>
    </div>
  );
}

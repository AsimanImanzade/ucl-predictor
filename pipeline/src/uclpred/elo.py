"""Point-in-time Elo ratings built from 90-minute results.

Matches are processed in a single chronological pass sorted by (date, match_id).
Matches sharing an identical timestamp are processed sequentially in match_id
order, so a later one sees the earlier one's result (deterministic). Ratings
queried "as of" t use only matches with kickoff strictly before t.
"""

from bisect import bisect_left
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd


@dataclass
class EloParams:
    k: float = 20.0
    home_adv: float = 60.0
    init_top: float = 1500.0
    init_second: float = 1350.0
    init_unknown: float = 1400.0


def expected_home(r_home: float, r_away: float, home_adv: float) -> float:
    return 1.0 / (1.0 + 10 ** ((r_away - r_home - home_adv) / 400.0))


def mov_multiplier(goal_diff: int) -> float:
    gd = abs(goal_diff)
    if gd <= 1:
        return 1.0
    if gd == 2:
        return 1.5
    return (11 + gd) / 8


@dataclass
class EloResult:
    pre: pd.DataFrame
    # team -> (sorted kickoff datetimes, rating after each match)
    _dates: dict[str, list] = field(default_factory=dict, repr=False)
    _ratings: dict[str, list[float]] = field(default_factory=dict, repr=False)

    def rating_as_of(self, team_id: str, as_of: datetime) -> float | None:
        """Rating after the team's latest match with kickoff strictly < as_of."""
        dates = self._dates.get(team_id)
        if not dates:
            return None
        i = bisect_left(dates, pd.Timestamp(as_of))
        return self._ratings[team_id][i - 1] if i else None

    def ratings_as_of(self, as_of: datetime) -> dict[str, float]:
        out = {}
        for team in self._dates:
            r = self.rating_as_of(team, as_of)
            if r is not None:
                out[team] = r
        return out


def run_elo(matches: pd.DataFrame, params: EloParams | None = None) -> EloResult:
    params = params or EloParams()
    df = matches[matches["status"] == "FINISHED"]
    df = df.sort_values(["date", "match_id"], kind="stable")
    cur: dict[str, float] = {}
    comp_teams: dict[str, set[str]] = {}
    country_teams: dict[str, set[str]] = {}
    dates: dict[str, list] = {}
    ratings: dict[str, list[float]] = {}
    pre_rows = []

    def seed(team: str, comp: str) -> float:
        if comp.startswith("uefa."):
            peers = country_teams.get(team.split("-", 1)[0], ())
            if len(peers) >= 3:
                return sum(cur[t] for t in peers) / len(peers)
            return params.init_unknown
        if comp.endswith(".2"):
            return params.init_second
        if comp.endswith(".1"):
            peers = comp_teams.get(comp, ())
            if len(peers) >= 5:
                return sum(cur[t] for t in peers) / len(peers)
        return params.init_top

    cols = zip(
        df["match_id"], df["date"], df["competition"], df["home_id"], df["away_id"],
        df["home_goals"].to_numpy(dtype="int64"), df["away_goals"].to_numpy(dtype="int64"),
        df["neutral"], strict=True,
    )  # fmt: skip
    for mid, date, comp, h, a, hg, ag, neutral in cols:
        new = [t for t in (h, a) if t not in cur]
        seeds = {t: seed(t, comp) for t in new}  # both seeded before registering either
        for t, r in seeds.items():
            cur[t] = r
            dates[t] = []
            ratings[t] = []
            country_teams.setdefault(t.split("-", 1)[0], set()).add(t)
        for t in (h, a):
            comp_teams.setdefault(comp, set()).add(t)
        rh, ra = cur[h], cur[a]
        pre_rows.append((mid, rh, ra))
        exp = expected_home(rh, ra, 0.0 if neutral else params.home_adv)
        score = 1.0 if hg > ag else 0.5 if hg == ag else 0.0
        delta = params.k * mov_multiplier(hg - ag) * (score - exp)
        cur[h], cur[a] = rh + delta, ra - delta
        for t in (h, a):
            dates[t].append(date)
            ratings[t].append(cur[t])
    pre = pd.DataFrame(pre_rows, columns=["match_id", "home_elo_pre", "away_elo_pre"])
    return EloResult(pre=pre, _dates=dates, _ratings=ratings)

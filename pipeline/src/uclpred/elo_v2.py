"""League-aware Elo (elo-v2).

rating(club, t) = L[league(club, t)] + o[club]

Domestic matches update offsets only. European matches between clubs of
different leagues move the league levels by g * delta and the offsets by
(1 - g) * delta, which lets a league's strength be learned from its European
results. A club that changes league keeps its total rating (continuity).

Point-in-time semantics match v1: strictly before as_of, sorted by
(date, match_id). Histories of club offsets, club leagues and league levels
are stored so that rating_as_of is correct for clubs that did not play (their
total moves implicitly when their league level moves).
"""

from bisect import bisect_left
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from uclpred.elo import EloResult, expected_home, mov_multiplier


@dataclass
class EloV2Params:
    k: float = 20.0
    k_euro: float = 1.5
    g: float = 0.7
    home_adv: float = 60.0
    init_top: float = 1500.0
    init_second: float = 1350.0
    init_unknown: float = 1400.0


@dataclass
class EloV2Result(EloResult):
    # club -> (dates, values) of offset / league code; league -> (dates, levels)
    _off: dict[str, tuple[list, list]] = field(default_factory=dict, repr=False)
    _lg: dict[str, tuple[list, list]] = field(default_factory=dict, repr=False)
    _lvl: dict[str, tuple[list, list]] = field(default_factory=dict, repr=False)

    @staticmethod
    def _at(hist: tuple[list, list] | None, ts: pd.Timestamp):
        if not hist:
            return None
        i = bisect_left(hist[0], ts)
        return hist[1][i - 1] if i else None

    def rating_as_of(self, team_id: str, as_of: datetime) -> float | None:
        ts = pd.Timestamp(as_of)
        off = self._at(self._off.get(team_id), ts)
        lg = self._at(self._lg.get(team_id), ts)
        if off is None or lg is None:
            return None
        lvl = self._at(self._lvl.get(lg), ts)
        return None if lvl is None else lvl + off

    def league_levels_as_of(self, as_of: datetime) -> dict[str, float]:
        ts = pd.Timestamp(as_of)
        out = {}
        for lg, hist in self._lvl.items():
            v = self._at(hist, ts)
            if v is not None:
                out[lg] = v
        return out


def run_elo_v2(matches: pd.DataFrame, params: EloV2Params | None = None) -> EloV2Result:
    p = params or EloV2Params()
    df = matches[matches["status"] == "FINISHED"]
    df = df.sort_values(["date", "match_id"], kind="stable")

    level: dict[str, float] = {}
    off: dict[str, float] = {}
    league_of: dict[str, str] = {}
    country_clubs: dict[str, list[str]] = {}
    dates: dict[str, list] = {}
    ratings: dict[str, list[float]] = {}
    off_h: dict[str, tuple[list, list]] = {}
    lg_h: dict[str, tuple[list, list]] = {}
    lvl_h: dict[str, tuple[list, list]] = {}
    pre_rows = []

    def total(t: str) -> float:
        return level[league_of[t]] + off[t]

    def set_level(lg: str, val: float, date) -> None:
        level[lg] = val
        hist = lvl_h.setdefault(lg, ([], []))
        hist[0].append(date)
        hist[1].append(val)

    def ensure_level(lg: str, cty: str, date) -> None:
        if lg in level:
            return
        peers = country_clubs.get(cty, ())
        if len(peers) >= 3:
            val = sum(total(t) for t in peers) / len(peers)
        elif lg.endswith(".1"):
            val = p.init_top
        elif lg.endswith(".2"):
            val = p.init_second
        elif lg.endswith(".x"):
            val = p.init_unknown
        else:
            val = p.init_top
        set_level(lg, val, date)

    def set_league(t: str, lg: str, date) -> None:
        league_of[t] = lg
        hist = lg_h.setdefault(t, ([], []))
        hist[0].append(date)
        hist[1].append(lg)

    def set_off(t: str, val: float, date) -> None:
        off[t] = val
        hist = off_h.setdefault(t, ([], []))
        hist[0].append(date)
        hist[1].append(val)

    cols = zip(
        df["match_id"], df["date"], df["competition"], df["home_id"], df["away_id"],
        df["home_goals"].to_numpy(dtype="int64"), df["away_goals"].to_numpy(dtype="int64"),
        df["neutral"], strict=True,
    )  # fmt: skip
    for mid, date, comp, h, a, hg, ag, neutral in cols:
        euro = comp.startswith("uefa.")
        for t in (h, a):
            cty = t.split("-", 1)[0]
            if t not in off:
                lg = f"{cty}.x" if euro else comp
                ensure_level(lg, cty, date)
                dates[t] = []
                ratings[t] = []
                set_league(t, lg, date)
                set_off(t, 0.0, date)
                country_clubs.setdefault(cty, []).append(t)
            elif not euro and league_of[t] != comp:
                ensure_level(comp, cty, date)
                new_off = total(t) - level[comp]
                set_league(t, comp, date)
                set_off(t, new_off, date)
        rh, ra = total(h), total(a)
        pre_rows.append((mid, rh, ra))
        exp = expected_home(rh, ra, 0.0 if neutral else p.home_adv)
        score = 1.0 if hg > ag else 0.5 if hg == ag else 0.0
        delta = (
            p.k * (p.k_euro if euro else 1.0) * mov_multiplier(hg - ag) * (score - exp)
        )
        if euro and league_of[h] != league_of[a]:
            lh, la = league_of[h], league_of[a]
            set_level(lh, level[lh] + p.g * delta, date)
            set_level(la, level[la] - p.g * delta, date)
            delta_off = (1.0 - p.g) * delta
        else:
            delta_off = delta
        set_off(h, off[h] + delta_off, date)
        set_off(a, off[a] - delta_off, date)
        for t in (h, a):
            dates[t].append(date)
            ratings[t].append(total(t))
    pre = pd.DataFrame(pre_rows, columns=["match_id", "home_elo_pre", "away_elo_pre"])
    return EloV2Result(
        pre=pre, _dates=dates, _ratings=ratings, _off=off_h, _lg=lg_h, _lvl=lvl_h
    )

"""Data coverage audit: duplicate-team detection and the per-team coverage report."""

import difflib
from itertools import combinations

import pandas as pd

RECENT_SEASONS = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]
LAST3 = ["2023-24", "2024-25", "2025-26"]
CURRENT = "2026-27"
_HEADER = (
    "| Team | Team id | Matches | Last 3 seasons | First match "
    "| Current domestic source | Domestic seasons 21-26 | Coefficient |"
)


def _is_domestic(comp: pd.Series) -> pd.Series:
    return ~comp.str.startswith("uefa.")


def duplicate_candidates(df: pd.DataFrame) -> list[tuple[str, str]]:
    """Pairs of ids (same country prefix) with similar names that never meet."""
    ids = pd.unique(pd.concat([df["home_id"], df["away_id"]]))
    met = set(zip(df["home_id"], df["away_id"], strict=True))
    met |= {(b, a) for a, b in met}
    by_country: dict[str, list[str]] = {}
    for i in sorted(ids):
        by_country.setdefault(i.split("-", 1)[0], []).append(i)
    out = []
    for group in by_country.values():
        for a, b in combinations(group, 2):
            if (a, b) in met:
                continue
            ca, cb = a.split("-", 1)[1], b.split("-", 1)[1]
            ta, tb = set(ca.split("-")), set(cb.split("-"))
            if (
                ta <= tb
                or tb <= ta
                or difflib.SequenceMatcher(None, ca, cb).ratio() >= 0.85
            ):
                out.append((a, b))
    return out


def cross_country_duplicates(df: pd.DataFrame) -> list[tuple[str, str]]:
    """Id pairs with an identical slug after the country prefix but different prefixes."""
    ids = pd.unique(pd.concat([df["home_id"], df["away_id"]]))
    by_slug: dict[str, list[str]] = {}
    for i in sorted(ids):
        slug = i.split("-", 1)[1]
        by_slug.setdefault(slug, []).append(i)
    return [
        (a, b)
        for group in by_slug.values()
        for a, b in combinations(group, 2)
        if a.split("-", 1)[0] != b.split("-", 1)[0]
    ]


def season_matrix(df: pd.DataFrame) -> str:
    """Markdown matrix of row counts: rows = competition, columns = season."""
    counts = df.groupby(["competition", "season"]).size().unstack(fill_value=0)
    seasons = list(counts.columns)
    lines = [
        "| Competition | " + " | ".join(seasons) + " |",
        "|---|" + "---:|" * len(seasons),
    ]
    for comp, row in counts.iterrows():
        lines.append(f"| {comp} | " + " | ".join(str(int(v)) for v in row) + " |")
    return "\n".join(lines)


def team_stats(df: pd.DataFrame, team_id: str) -> dict:
    m = df[(df["home_id"] == team_id) | (df["away_id"] == team_id)]
    dom = m[_is_domestic(m["competition"])]
    cur = dom[dom["season"] == CURRENT]
    if (cur["source"] == "football-data").any():
        cur_src = "football-data"
    elif (cur["source"] == "openfootball").any():
        cur_src = "openfootball"
    else:
        cur_src = "missing"
    return {
        "matches": len(m),
        "last3": int(m["season"].isin(LAST3).sum()),
        "first": m["date"].min().strftime("%Y-%m-%d") if len(m) else "-",
        "dom_seasons": int(
            dom["season"].isin(RECENT_SEASONS).groupby(dom["season"]).any().sum()
        )
        if len(dom)
        else 0,
        "current_domestic": cur_src,
    }


def coverage_report(
    df: pd.DataFrame, cl_teams: list[dict], coefs: pd.DataFrame
) -> str:
    from uclpred.teams import TeamResolver

    resolver = TeamResolver()
    coef_ids = set(coefs["team_id"]) if len(coefs) else set()
    lines = [
        "# Data coverage (36 teams, Champions League 2026/27)",
        "",
        _HEADER,
        "|---|---|---:|---:|---|---|---:|---|",
    ]
    missing = []
    for t in sorted(cl_teams, key=lambda t: t["name"]):
        tid = resolver.resolve(t["area"]["code"], t["name"])
        s = team_stats(df, tid)
        has_coef = "yes" if tid in coef_ids else "no"
        if s["current_domestic"] == "missing":
            missing.append(t["name"])
        lines.append(
            f"| {t['name']} | {tid} | {s['matches']} | {s['last3']} | {s['first']} | "
            f"{s['current_domestic']} | {s['dom_seasons']} | {has_coef} |"
        )
    lines += [
        "",
        f"Teams with missing current-season domestic data ({len(missing)}): "
        + (", ".join(missing) or "none"),
        "",
    ]
    lines += ["Matches per competition and season:", "", season_matrix(df), ""]
    xdup = cross_country_duplicates(df)
    lines += [
        f"Cross-country duplicate ids ({len(xdup)}): "
        + (", ".join(f"{a} / {b}" for a, b in xdup) or "none"),
        "",
    ]
    return "\n".join(lines)

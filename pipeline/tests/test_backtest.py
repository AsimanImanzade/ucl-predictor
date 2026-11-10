import numpy as np
import pandas as pd
import pytest

import uclpred.backtest as bt
from uclpred.backtest import (
    bootstrap_delta_rps,
    monthly_checkpoints,
    score,
    walk_forward,
)
from uclpred.models.metrics import brier, log_loss, rps


def _ts(s):
    return pd.Timestamp(s, tz="UTC")


def test_checkpoints_cover_summer_and_august_finals():
    dates = pd.Series([_ts("2019-07-09"), _ts("2019-09-17"), _ts("2020-08-23")])
    cps = monthly_checkpoints(dates)
    assert cps[0] == _ts("2019-07-01")
    assert cps[-1] == _ts("2020-09-01")
    assert len(cps) == 15
    assert all(c.tz is not None and c.day == 1 and c.hour == 0 for c in cps)
    for d in dates:
        assert sum(cps[i] <= d < cps[i + 1] for i in range(len(cps) - 1)) == 1


def _matches():
    rows = []
    specs = [
        ("m1", "2019-07-09", "uefa.cl", "a", "b", 1, 0, False),
        ("m2", "2019-07-31", "uefa.el", "b", "a", 2, 2, False),
        ("m3", "2019-09-01", "uefa.cl", "a", "c", 0, 3, True),  # exactly on a checkpoint
        ("m4", "2019-11-05", "uefa.cl", "c", "b", 1, 1, False),
        ("m5", "2019-08-10", "en.1", "a", "b", 5, 0, False),  # domestic: not evaluated
        ("m6", "2020-08-23", "uefa.cl", "b", "c", 3, 1, True),  # August final, other season
        ("m7", "2019-12-01", "uefa.cl", "a", "b", None, None, False),  # not finished
    ]
    for mid, d, comp, h, a, hg, ag, neu in specs:
        rows.append({
            "match_id": mid, "date": _ts(d), "season": "2019-20", "competition": comp,
            "home_id": h, "away_id": a, "home_goals": hg, "away_goals": ag,
            "neutral": neu, "status": "FINISHED" if hg is not None else "SCHEDULED",
        })  # fmt: skip
    df = pd.DataFrame(rows)
    df["home_goals"] = df["home_goals"].astype("Int64")
    df["away_goals"] = df["away_goals"].astype("Int64")
    return df


class _Stub:
    def predict_match(self, home_id, away_id, neutral=False):
        m = np.zeros((11, 11))
        m[1, 0] = 0.5  # home win
        m[0, 0] = 0.3  # draw
        m[0, 1] = 0.2  # away win
        return m


def test_walk_forward_never_uses_match_on_or_after_checkpoint(monkeypatch):
    calls = []

    def fake_fit(matches, elo, as_of, alpha=0.005, **kw):
        calls.append(as_of)
        return _Stub()

    monkeypatch.setattr(bt, "fit_baseline", fake_fit)
    m = _matches()
    out = walk_forward(m, None, ["2019-20"], 0.005)

    assert list(out.columns) == ["match_id", "season", "p_home", "p_draw", "p_away", "outcome"]
    assert list(out["match_id"]) == ["m1", "m2", "m3", "m4", "m6"]
    assert list(out["outcome"]) == [0, 1, 2, 1, 0]
    assert np.allclose(out[["p_home", "p_draw", "p_away"]].sum(axis=1), 1.0)
    # one fit per window with eval matches: Jul, Sep, Nov, Aug-2020
    assert [str(c.date()) for c in calls] == ["2019-07-01", "2019-09-01", "2019-11-01", "2020-08-01"]
    cps = monthly_checkpoints(m.loc[m["match_id"].isin(out["match_id"]), "date"])
    dates = m.set_index("match_id")["date"]
    for mid in out["match_id"]:
        d = dates[mid]
        fit_asof = max(c for c in calls if c <= d)
        nxt = min(c for c in cps if c > fit_asof)
        assert fit_asof <= d < nxt


def _preds(ids, probs, outcomes):
    p = np.asarray(probs)
    return pd.DataFrame({
        "match_id": ids, "season": "s", "p_home": p[:, 0], "p_draw": p[:, 1],
        "p_away": p[:, 2], "outcome": outcomes,
    })  # fmt: skip


def test_bootstrap_deterministic_and_aligned():
    rng = np.random.default_rng(0)
    p = rng.dirichlet([2, 2, 2], size=60)
    q = rng.dirichlet([2, 2, 2], size=60)
    y = rng.integers(0, 3, size=60)
    ids = [f"m{i}" for i in range(60)]
    a, b = _preds(ids, p, y), _preds(ids[::-1], q[::-1], y[::-1])
    r1 = bootstrap_delta_rps(a, b)
    r2 = bootstrap_delta_rps(a, b)
    assert r1 == r2
    mean, lo, hi = r1
    assert lo <= mean <= hi
    assert mean == pytest.approx(rps(q, y) - rps(p, y))
    with pytest.raises(ValueError, match="match_id"):
        bootstrap_delta_rps(a, _preds(ids[:-1] + ["zzz"], q, y))


def test_per_match_rps_mean_equals_rps():
    rng = np.random.default_rng(3)
    p = rng.dirichlet([2, 2, 2], size=40)
    y = rng.integers(0, 3, size=40)
    assert bt._per_match_rps(p, y).mean() == pytest.approx(rps(p, y))


def test_score_keys():
    p = np.array([[0.5, 0.3, 0.2], [0.2, 0.3, 0.5], [0.4, 0.4, 0.2]])
    y = np.array([0, 1, 2])
    s = score(_preds(["a", "b", "c"], p, y))
    assert set(s) == {"rps", "log_loss", "brier", "n"}
    assert s["n"] == 3
    assert s["rps"] == pytest.approx(rps(p, y))
    assert s["log_loss"] == pytest.approx(log_loss(p, y))
    assert s["brier"] == pytest.approx(brier(p, y))

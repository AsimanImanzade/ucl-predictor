import pandas as pd
import pytest

import uclpred.backtest as bt
from uclpred.backtest import run_grid, select_params


def _grid_df(rows):
    return pd.DataFrame(
        [
            {"k": 20.0, "k_euro": 1.5, "g": 0.7, "alpha": 0.002, "rps": 0.2, "log_loss": 1.0,
             "brier": 0.6, "league_gap": 0.0, **r}
            for r in rows
        ]
    )  # fmt: skip


def test_select_lowest_rps():
    df = _grid_df([{"k": 16.0, "rps": 0.21}, {"k": 20.0, "rps": 0.19}, {"k": 24.0, "rps": 0.20}])
    assert select_params(df)["k"] == 20.0


def test_select_tie_goes_to_smaller_gap():
    df = _grid_df([
        {"k": 16.0, "rps": 0.1900, "league_gap": 0.08},
        {"k": 20.0, "rps": 0.1903, "league_gap": -0.01},
        {"k": 24.0, "rps": 0.1950, "league_gap": 0.0},
    ])  # fmt: skip
    got = select_params(df)
    assert got["k"] == 20.0
    assert got["home_adv"] == 60.0
    assert set(got) >= {"k", "k_euro", "g", "home_adv", "alpha"}


def test_select_full_tie_is_deterministic():
    rows = [{"k": 24.0}, {"k": 16.0}, {"k": 20.0}]
    a = select_params(_grid_df(rows))
    b = select_params(_grid_df(rows[::-1]))
    assert a == b and a["k"] == 16.0


def test_run_grid_shape_and_elo_reuse(monkeypatch):
    calls = {"elo": 0, "gap": 0}

    class _R:
        pre = pd.DataFrame({"match_id": [], "home_elo_pre": [], "away_elo_pre": []})

    def fake_elo(m, p):
        calls["elo"] += 1
        return _R()

    def fake_gap(m, pre, ha, **kw):
        calls["gap"] += 1
        return 0.05, 3

    def fake_wf(m, elo, seasons, alpha):
        return pd.DataFrame({
            "match_id": ["a", "b"], "season": ["2019-20"] * 2,
            "p_home": [0.5, 0.2], "p_draw": [0.3, 0.3], "p_away": [0.2, 0.5],
            "outcome": [0, 2],
        })  # fmt: skip

    monkeypatch.setattr(bt, "run_elo_v2", fake_elo)
    monkeypatch.setattr(bt, "league_gap", fake_gap)
    monkeypatch.setattr(bt, "walk_forward", fake_wf)
    grid = {"k": [16.0, 20.0], "k_euro": [1.5], "g": [0.7], "alpha": [0.002]}
    df = run_grid(pd.DataFrame(), ["2019-20"], grid)
    assert len(df) == 2
    assert {"k", "k_euro", "g", "alpha", "rps", "log_loss", "brier", "league_gap"} <= set(df.columns)
    assert calls == {"elo": 2, "gap": 2}
    assert (df["league_gap"] == 0.05).all()

    grid["alpha"] = [0.0005, 0.005]
    calls.update(elo=0, gap=0)
    df = run_grid(pd.DataFrame(), ["2019-20"], grid)
    assert len(df) == 4 and calls == {"elo": 2, "gap": 2}


def test_params_roundtrip(tmp_path, monkeypatch):
    p = tmp_path / "model_params.json"
    monkeypatch.setattr(bt, "PARAMS_PATH", p)
    with pytest.raises(FileNotFoundError):
        bt.load_model_params()
    p.write_text('{"elo-dc-v2": {"alpha": 0.002}}')
    assert bt.load_model_params()["elo-dc-v2"]["alpha"] == 0.002

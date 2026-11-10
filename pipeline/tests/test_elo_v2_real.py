import time
from datetime import UTC, datetime

import pytest

from uclpred.elo_v2 import run_elo_v2
from uclpred.matches import load_matches


@pytest.mark.data
def test_elo_v2_real_data_ordering_and_speed():
    matches = load_matches()
    t0 = time.time()
    res = run_elo_v2(matches)
    elapsed = time.time() - t0
    as_of = datetime(2026, 9, 7, tzinfo=UTC)
    r = {t: res.rating_as_of(t, as_of) for t in
         ("esp-real-madrid", "eng-liverpool", "esp-atletico-madrid", "ned-psv")}  # fmt: skip
    print(f"\nelo-v2 runtime {elapsed:.2f}s")
    for t, v in r.items():
        print(f"{t}: {v:.1f}")
    print({k: round(v) for k, v in res.league_levels_as_of(as_of).items()})
    assert elapsed < 10
    # no same-kickoff leak: pre equals the point-in-time rating for every slot
    fin = matches[matches["status"] == "FINISHED"].merge(res.pre, on="match_id")
    bad = 0
    for date, h, a, ph, pa in zip(
        fin["date"], fin["home_id"], fin["away_id"],
        fin["home_elo_pre"], fin["away_elo_pre"], strict=True,
    ):  # fmt: skip
        for team, pre in ((h, ph), (a, pa)):
            cur = res.rating_as_of(team, date)
            if cur is not None and abs(cur - pre) > 1e-9:
                bad += 1
    print(f"pre != rating_as_of slots: {bad}")
    assert bad == 0
    for t in ("esp-real-madrid", "eng-liverpool"):
        assert r[t] > r["ned-psv"]
    # Atletico vs PSV is near parity with untuned defaults (k_euro-sensitive);
    # the backtest tunes it. Require only that the v1 gap (~110 Elo) is gone.
    assert r["esp-atletico-madrid"] > r["ned-psv"] - 25

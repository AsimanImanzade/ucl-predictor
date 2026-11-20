import numpy as np
import pandas as pd
import pytest

from uclpred import evaluate_v21 as ev


def test_gate_boundaries_pass():
    assert ev.gate_results(0.03, 0.003, 0.006) == {"G1": True, "G2": True, "G3": True}
    assert ev.gate_results(-0.03, 0.003, 0.006)["G1"] is True


def test_gate_boundaries_fail():
    assert ev.gate_results(0.030000001, 0.003, 0.006)["G1"] is False
    assert ev.gate_results(-0.030000001, 0.003, 0.006)["G1"] is False
    assert ev.gate_results(0.0, 0.003 + 1e-9, 0.006)["G2"] is False
    assert ev.gate_results(0.0, 0.003, 0.006 + 1e-9)["G3"] is False


def test_holdout_window():
    assert ev.HOLDOUT == (
        pd.Timestamp("2026-09-07", tz="UTC"),
        pd.Timestamp("2026-11-09", tz="UTC"),
    )


def stub(g1=0.01, g2=0.001, g3=0.002):
    return {
        "settings": {
            "elo": {"k": 24, "k_euro": 2.0, "g": 0.9, "g_pseudo": 0.0, "home_adv": 60},
            "alpha": 0.005,
            "rating_sigma": 0,
        },
        "g1": {"v21": g1, "v1": -0.16, "n": 100},
        "g2": {
            "mean": 0.0,
            "lo": -0.001,
            "hi": g2,
            "rps_v1": 0.2,
            "rps_v21": 0.2,
            "n": 500,
        },
        "g3": {
            "mean": 0.0,
            "lo": -0.001,
            "hi": g3,
            "rps_v1": 0.2,
            "rps_v21": 0.2,
            "n": 300,
        },
        "calib": {
            ev.CAL_LABEL: {"v1": (0.45, 0.46), "v2.1": (0.44, 0.46)},
            ev.HOLD_LABEL: {"v1": (0.45, 0.47), "v2.1": (0.44, 0.47)},
        },
        "g3_by_comp": [
            {"competition": "en.1", "n": 10, "rps_v1": 0.2, "rps_v21": 0.21}
        ],
        "tournament": [
            {"season": "2024-25", "model": "elo-dc-v1", "stage_log_loss": 1.5},
            {"season": "2025-26", "model": "elo-dc-v1", "stage_log_loss": 1.6},
            {"season": "2024-25", "model": "elo-dc-v2.1", "stage_log_loss": 1.4},
            {"season": "2025-26", "model": "elo-dc-v2.1", "stage_log_loss": 1.5},
        ],
    }


def test_report_sections_in_order_and_pass_verdict():
    md = ev.render_report(stub(), [])
    heads = [ln for ln in md.splitlines() if ln.startswith("## ")]
    assert heads == [
        "## Verdict",
        "## Settings",
        "## Gates",
        "## Diagnostics",
        "## Run log",
    ]
    assert "G1–G3: PASS — pending user review (G4)" in md
    assert "381a8a8" in md
    assert "pending user review" in md
    assert "\\|gap(v2.1)\\| ≤ 0.03" in md
    assert "n=100" in md and "+0.002000000" in md
    assert "uefa.* 2022-26" in md


def test_report_fail_verdict_lists_gates():
    md = ev.render_report(stub(g1=0.5, g3=0.01), ["x"])
    assert "FAIL (G1, G3) — v1 stays default" in md
    assert "G1–G3: PASS" not in md


def test_display_cannot_contradict_verdict():
    # 1e-9 over the G2 threshold must be visible at the displayed precision
    md = ev.render_report(stub(g2=0.003 + 1e-7), [])
    assert "+0.003000100" in md and "FAIL (G2)" in md
    assert "| G2 | +0.003000100 (ΔRPS CI upper) | ≤ +0.003 | FAIL |" in md


def test_tournament_pending_and_error():
    r = stub()
    r["tournament"] = None
    assert "pending" in ev.render_report(r, [])
    r["tournament_error"] = "CalledProcessError: pnpm"
    assert "ERROR (not gating): CalledProcessError: pnpm" in ev.render_report(r, [])


def test_run_lines_numbering_and_verbatim(tmp_path):
    p = tmp_path / "r.md"
    assert ev.next_run_number(p) == 1
    first = "- 2026-11-10T00:00:00Z abc1234 run 1 started"
    second = "- 2026-11-10T00:01:00Z run 1 result: G1 +0.01 PASS (custom text) trailing"
    p.write_text(ev.render_report(stub(), [first, second]))
    assert ev.existing_run_lines(p) == [first, second]
    assert ev.next_run_number(p) == 2
    # a failure line with text after "run N" still counts
    p.write_text(p.read_text() + ev.failure_line(2, "boom\nx") + "\n")
    assert ev.next_run_number(p) == 3


def test_run_line_formats():
    s = ev.start_line(2, "abc-dirty", "bug fix")
    assert s.endswith("abc-dirty run 2 started (reason: bug fix)")
    r = ev.result_line(1, stub(g2=0.003 + 1e-7))
    assert "G1 +0.010000000 PASS" in r and "G2 +0.003000100 FAIL" in r
    assert "verdict: FAIL (G2) — v1 stays default" in r


def test_check_settings_aborts_on_drift():
    ok = {"elo-dc-v2.1": {**ev.PREREG_SETTINGS}}
    ev.check_settings(ok)
    import copy

    for mut in (
        lambda e: e["elo"].update(k=25),
        lambda e: e["elo"].update(g_pseudo=0.1),
        lambda e: e.update(alpha=0.0005),
        lambda e: e.update(rating_sigma=70),
        lambda e: e.pop("rating_sigma"),
    ):
        bad = {"elo-dc-v2.1": copy.deepcopy(ev.PREREG_SETTINGS)}
        mut(bad["elo-dc-v2.1"])
        with pytest.raises(ValueError, match="pre-registration"):
            ev.check_settings(bad)
    with pytest.raises(ValueError):
        ev.check_settings({})


def test_holdout_count_boundaries():
    d = pd.to_datetime(
        [
            "2026-09-06T23:59:59Z",
            "2026-09-07T00:00:00Z",
            "2026-11-08T23:59:59Z",
            "2026-11-09T00:00:00Z",
        ]
    )
    m = pd.DataFrame({"date": d, "status": "FINISHED"})
    assert ev.holdout_count(m) == 2
    assert ev.holdout_count(m.assign(status="SCHEDULED")) == 0


def _wiring(monkeypatch, v21_worse=True):
    import uclpred.backtest as bt
    import uclpred.elo as elo_mod
    import uclpred.elo_v2 as elo2_mod
    from uclpred.models import metrics

    class FakeElo:
        def __init__(self, tag):
            self.tag = tag
            self.pre = tag

    e1, e21 = FakeElo("v1"), FakeElo("v21")
    monkeypatch.setattr(elo_mod, "run_elo", lambda m: e1)
    monkeypatch.setattr(elo2_mod, "run_elo_v2", lambda m, p: e21)
    gap_calls = []

    def fake_gap(matches, pre, home_adv, from_season=None, to_season=None):
        gap_calls.append((pre, home_adv, from_season, to_season))
        return {"v1": (-0.16, 7), "v21": (0.01, 5)}[pre]

    monkeypatch.setattr(metrics, "league_gap", fake_gap)
    monkeypatch.setattr(ev, "tournament_rows", lambda runs: [])
    n = 40
    ids = [f"m{i}" for i in range(n)]
    matches = pd.DataFrame({"match_id": ids, "competition": ["en.1"] * n})
    outs = np.zeros(n, dtype=int)  # all home wins
    good = np.tile([0.8, 0.1, 0.1], (n, 1))
    bad = np.tile([0.2, 0.3, 0.5], (n, 1))
    calls = []

    def fake_wf(m, elo, seasons, alpha, **kw):
        calls.append({"tag": elo.tag, "seasons": seasons, "alpha": alpha, **kw})
        p = bad if (elo.tag == "v21" and v21_worse) else good
        return pd.DataFrame({
            "match_id": ids, "season": "2025-26", "p_home": p[:, 0],
            "p_draw": p[:, 1], "p_away": p[:, 2], "outcome": outs,
        })  # fmt: skip

    monkeypatch.setattr(bt, "walk_forward", fake_wf)
    return matches, calls, gap_calls


PARAMS = {"elo-dc-v2.1": {**ev.PREREG_SETTINGS}}


def test_compute_v21_pins_preregistered_arguments(monkeypatch):
    matches, calls, gap_calls = _wiring(monkeypatch)
    res = ev.compute_v21(matches, PARAMS)
    assert len(calls) == 4
    by = {(c["tag"], c.get("window") is None): c for c in calls}
    for tag, alpha in (("v1", 0.005), ("v21", 0.005)):
        q = by[(tag, True)]
        assert q["seasons"] == ["2022-23", "2023-24", "2024-25", "2025-26"]
        assert q["alpha"] == alpha
        assert q.get("prefixes", ("uefa.",)) == ("uefa.",)
        h = by[(tag, False)]
        assert h["seasons"] is None and h["prefixes"] is None
        assert h["window"] == ev.HOLDOUT and h["alpha"] == alpha
    assert {c[0]: c[1:] for c in gap_calls} == {
        "v1": (60, "2022-23", "2025-26"),
        "v21": (60, "2022-23", "2025-26"),
    }
    assert res["g1"] == {"v21": 0.01, "v1": -0.16, "n": 5}
    assert res["g3"]["n"] == 40 and res["g3_by_comp"][0]["competition"] == "en.1"
    # direction is v2.1 - v1: v2.1 strictly worse -> positive delta
    assert res["g2"]["mean"] > 0 and res["g3"]["mean"] > 0
    assert res["g2"]["rps_v21"] > res["g2"]["rps_v1"]
    assert "FAIL (G2, G3)" in ev.render_report(res, ["- t sha run 1"])


def test_compute_v21_tournament_error_is_recorded(monkeypatch):
    matches, _, _ = _wiring(monkeypatch)

    def boom(runs):
        raise RuntimeError("pnpm exploded")

    monkeypatch.setattr(ev, "tournament_rows", boom)
    res = ev.compute_v21(matches, PARAMS)
    assert res["tournament"] is None and "pnpm exploded" in res["tournament_error"]
    assert "pnpm exploded" in ev.render_report(res, [])


G4_BLOCK = "## G4 review\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n### Live\n\nrun 9 text"
CTX_BLOCK = "## G4 context (post-hoc, non-gating)\n\n### Sub\n\nrun 7 in prose"
RUN1 = "- 2026-11-10T00:00:00Z abc1234 run 1 started"


def test_run_lines_stop_at_next_heading(tmp_path):
    p = tmp_path / "r.md"
    p.write_text(
        f"# t\n\n## Run log\n\n{RUN1}\n\n{CTX_BLOCK}\n\n- stray run 8 line\n",
        encoding="utf-8",
    )
    assert ev.existing_run_lines(p) == [RUN1]
    assert ev.next_run_number(p) == 2


def test_subheading_is_not_a_split_point(tmp_path):
    p = tmp_path / "r.md"
    p.write_text(f"# t\n\n## Run log\n\n{RUN1}\n\n### Note\n\n- sub run 2 line\n")
    assert ev.existing_run_lines(p) == [RUN1, "### Note", "- sub run 2 line"]
    assert [h for h, _ in ev._sections("## A\n\n### B\n\nx\n\n## C\n")] == ["A", "C"]


def test_rerender_keeps_extras_above_run_log(tmp_path):
    p = tmp_path / "r.md"
    p.write_text(ev.render_report(stub(), [RUN1], [G4_BLOCK, CTX_BLOCK]), encoding="utf-8")
    extra = ev.preserved_sections(p)
    assert extra == [G4_BLOCK, CTX_BLOCK]
    p.write_text(
        ev.render_report(stub(), [RUN1, "- run 2"], extra), encoding="utf-8"
    )
    text = p.read_text(encoding="utf-8")
    assert G4_BLOCK in text and CTX_BLOCK in text
    heads = [h for h, _ in ev._sections(text)]
    assert heads[-3:] == [
        "G4 review",
        "G4 context (post-hoc, non-gating)",
        "Run log",
    ]
    assert ev.preserved_sections(p) == extra


def test_append_run_line_inside_run_log_when_not_last(tmp_path):
    p = tmp_path / "r.md"
    before = f"# t\n\n## Run log\n\n{RUN1}\n\n{G4_BLOCK}\n\n{CTX_BLOCK}\n"
    p.write_text(before, encoding="utf-8")
    ev.append_run_line(p, "- y run 2 started")
    assert ev.existing_run_lines(p) == [RUN1, "- y run 2 started"]
    assert ev.preserved_sections(p) == [G4_BLOCK, CTX_BLOCK]
    after = p.read_text(encoding="utf-8")
    assert after.endswith(f"{G4_BLOCK}\n\n{CTX_BLOCK}\n")
    assert after.index("run 2 started") < after.index("## G4 review")


def test_start_line_collapses_multiline_reason():
    s = ev.start_line(2, "abc", "a\nb\n  c")
    assert s.endswith("run 2 started (reason: a b c)")
    assert "\n" not in s


def test_write_json_carries_run_and_head(tmp_path):
    import json

    md, js = tmp_path / "r.md", tmp_path / "r.json"
    ev._write(stub(), ["- x run 1"], md, js, 3, "abc1234-dirty")
    d = json.loads(js.read_text(encoding="utf-8"))
    assert d["run"] == 3 and d["head"] == "abc1234-dirty" and "g1" in d

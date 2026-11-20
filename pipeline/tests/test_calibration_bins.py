import json

import pandas as pd

from uclpred.calibration_bins import bins_payload


def _preds():
    return pd.DataFrame({
        "match_id": [1, 2, 3, 4],
        "season": ["2022-23"] * 4,
        "p_home": [0.05, 0.45, 0.55, 0.95],
        "p_draw": [0.25] * 4,
        "p_away": [0.7, 0.3, 0.2, 0.0],
        "outcome": [2, 0, 1, 0],
    })  # fmt: skip


def test_bins_payload_shape_and_counts():
    out = bins_payload(_preds(), model="elo-dc-v2.1", scope="uefa.* 2022-26")
    assert out["model"] == "elo-dc-v2.1"
    assert out["scope"] == "uefa.* 2022-26"
    assert out["n"] == 4
    assert len(out["bins"]) == 10
    assert sum(b["n"] for b in out["bins"]) == 4
    b4 = out["bins"][4]
    assert (b4["lo"], b4["hi"], b4["n"], b4["meanPred"], b4["observed"]) == (
        0.4,
        0.5,
        1,
        0.45,
        1.0,
    )


def test_empty_bins_are_null_not_nan():
    out = bins_payload(_preds(), model="m", scope="s")
    empty = out["bins"][2]
    assert empty["n"] == 0 and empty["meanPred"] is None and empty["observed"] is None
    json.dumps(out, allow_nan=False)

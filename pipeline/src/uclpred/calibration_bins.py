"""Binned home-win calibration for the dashboard's Methodology page (descriptive, not a gate)."""

import json
import math
from pathlib import Path

import pandas as pd

from uclpred.models.metrics import calibration_table

SCOPE = "uefa.* 2022-26"


def _num(x: float, nd: int = 4) -> float | None:
    return (
        None
        if x is None or (isinstance(x, float) and math.isnan(x))
        else round(float(x), nd)
    )


def bins_payload(preds: pd.DataFrame, model: str, scope: str, bins: int = 10) -> dict:
    cal = calibration_table(
        preds["p_home"].to_numpy(), (preds["outcome"] == 0).to_numpy(), bins=bins
    )
    return {
        "model": model,
        "scope": scope,
        "n": len(preds),
        "bins": [
            {
                "lo": round(float(r.bin_lo), 2),
                "hi": round(float(r.bin_hi), 2),
                "n": int(r.n),
                "meanPred": _num(r.mean_pred),
                "observed": _num(r.observed),
            }
            for r in cal.itertuples()
        ],
    }


def run_calibration_bins(out: Path) -> str:
    """Walk-forward elo-dc-v2.1 predictions on the report seasons (same scope as the
    pre-registered evaluation), binned by home-win probability."""
    from uclpred.backtest import walk_forward
    from uclpred.config import REFERENCE
    from uclpred.elo_v2 import EloV2Params, run_elo_v2
    from uclpred.evaluate_v21 import REPORT_SEASONS
    from uclpred.matches import load_matches

    params = json.loads((REFERENCE / "model_params.json").read_text(encoding="utf-8"))
    entry = params["elo-dc-v2.1"]
    matches = load_matches()
    elo = run_elo_v2(matches, EloV2Params(**entry["elo"]))
    preds = walk_forward(matches, elo, REPORT_SEASONS, entry["alpha"])
    payload = bins_payload(preds, model="elo-dc-v2.1", scope=SCOPE)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return f"{payload['n']} predictions in {sum(b['n'] > 0 for b in payload['bins'])} bins -> {out}"

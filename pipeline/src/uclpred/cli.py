"""uclpred command line."""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv

from uclpred.config import MODEL_NAME, ROOT, SEASON, SEASONS


def _ingest(args: argparse.Namespace) -> int:
    if args.processed_only:
        from uclpred.ingest.run import write_processed_cl

        for p in write_processed_cl():
            print(f"wrote {p}")
        return 0
    token = _token()
    if not token:
        return 2
    from uclpred.ingest.run import run_ingest

    run_ingest(token)
    return 0


def _token() -> str | None:
    """FOOTBALL_DATA_TOKEN from the environment or .env. Never printed."""
    load_dotenv(ROOT / ".env")
    token = os.environ.get("FOOTBALL_DATA_TOKEN")
    if not token:
        print(
            "error: FOOTBALL_DATA_TOKEN is not set (put it in .env at the repo root)",
            file=sys.stderr,
        )
    return token


def _refresh(args: argparse.Namespace) -> int:
    token = _token()
    if not token:
        return 2
    from uclpred.ingest.football_data import FootballDataClient
    from uclpred.refresh import run_refresh, write_github_output

    res = run_refresh(FootballDataClient(token, force=True), domestic=args.domestic)
    print(f"changed: {', '.join(res.changed) or 'nothing'}")
    print(f"snapshots due: {', '.join(s for s, _ in res.due) or 'none'}")
    write_github_output(res.any)
    return 0


def _update(_args: argparse.Namespace) -> int:
    from uclpred.update import run_update

    print(f"built: {', '.join(run_update())}")
    return 0


def _coefficients(args: argparse.Namespace) -> int:
    from uclpred.ingest.uefa_coefficients import fetch_coefficients, save_coefficients

    df = fetch_coefficients(args.season_year)
    save_coefficients(df)
    print(f"coefficients {args.season_year}: {len(df)} clubs")
    return 0


def _coverage(_args: argparse.Namespace) -> int:
    from uclpred.ingest.run import run_coverage

    print(run_coverage())
    return 0


def resolve_as_of(value: str, season: str):
    from datetime import UTC, datetime

    from uclpred.config import SEASONS

    if value == "now":
        return datetime.now(UTC).replace(microsecond=0)
    if value == "preseason":
        return SEASONS[season]["preseason_as_of"]
    as_of = datetime.fromisoformat(value)
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=UTC)
    return as_of


def _export(args: argparse.Namespace) -> int:
    from pathlib import Path

    from uclpred.export import run_export

    as_of = resolve_as_of(args.as_of, args.season)
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    print(run_export(as_of, out, args.season, args.model))
    return 0


def _backtest(_args: argparse.Namespace) -> int:
    from uclpred.backtest import run_backtest

    run_backtest()
    return 0


def _tournament_check(args: argparse.Namespace) -> int:
    from uclpred.tournament_check import run_tournament_check

    run_tournament_check(args.runs)
    return 0


def _evaluate_v21(args: argparse.Namespace) -> int:
    from uclpred.evaluate_v21 import run_evaluate_v21

    run_evaluate_v21(reason=args.reason)
    return 0


def _calibration_bins(args: argparse.Namespace) -> int:
    from uclpred.calibration_bins import run_calibration_bins
    from uclpred.config import REPORTS

    print(run_calibration_bins(REPORTS / "calibration-bins-v21.json"))
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="uclpred")
    sub = parser.add_subparsers(dest="command", required=True)
    i = sub.add_parser(
        "ingest", help="fetch all sources and build data/processed/matches.parquet"
    )
    i.add_argument(
        "--processed-only",
        action="store_true",
        help="no network: only rebuild data/processed/cl_{year}_{fd,teams}.json from cached raw",
    )
    i.set_defaults(func=_ingest)
    r = sub.add_parser(
        "refresh",
        help="fast: re-fetch the current CL season (live, no same-day cache) into data/processed",
    )
    r.add_argument(
        "--domestic",
        action="store_true",
        help="also re-fetch the current domestic seasons (done anyway when a snapshot is due)",
    )
    r.set_defaults(func=_refresh)
    sub.add_parser(
        "update",
        help="no network: export live + due mdNN, run the 50k sims, assemble web/public/data",
    ).set_defaults(func=_update)
    c = sub.add_parser(
        "coefficients", help="fetch UEFA club coefficients into data/reference"
    )
    c.add_argument("--season-year", type=int, required=True)
    c.set_defaults(func=_coefficients)
    sub.add_parser(
        "coverage", help="write reports/coverage.md and list duplicate team candidates"
    ).set_defaults(func=_coverage)
    e = sub.add_parser("export", help="write season.json and lambdas.json snapshot")
    e.add_argument(
        "--as-of", required=True, help="ISO date/time (UTC), 'now' or 'preseason'"
    )
    e.add_argument("--season", default=SEASON, choices=sorted(SEASONS))
    e.add_argument(
        "--model", default=MODEL_NAME, choices=["elo-dc-v1", "elo-dc-v2", "elo-dc-v2.1"]
    )  # fixed list; names must be keys in model_params.json
    e.add_argument("--out", required=True, help="output dir (relative to repo root)")
    e.set_defaults(func=_export)
    sub.add_parser(
        "backtest",
        help="grid-search elo-dc-v2, write model_params.json and calibration report",
    ).set_defaults(func=_backtest)
    t = sub.add_parser(
        "tournament-check",
        help="simulate past seasons, score stage probabilities, choose rating_sigma",
    )
    t.add_argument("--runs", type=int, default=50000)
    t.set_defaults(func=_tournament_check)
    ev = sub.add_parser(
        "evaluate-v21",
        help="run the pre-registered v2.1 gates and write reports/v21-evaluation.md",
    )
    ev.add_argument(
        "--reason", help="why this run happens (required when a previous run exists)"
    )
    ev.set_defaults(func=_evaluate_v21)
    sub.add_parser(
        "calibration-bins",
        help="binned home-win calibration of elo-dc-v2.1 -> reports/calibration-bins-v21.json",
    ).set_defaults(func=_calibration_bins)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

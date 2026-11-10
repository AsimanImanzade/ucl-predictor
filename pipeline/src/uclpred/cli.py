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
    load_dotenv(ROOT / ".env")
    token = os.environ.get("FOOTBALL_DATA_TOKEN")
    if not token:
        print(
            "error: FOOTBALL_DATA_TOKEN is not set (put it in .env at the repo root)",
            file=sys.stderr,
        )
        return 2
    from uclpred.ingest.run import run_ingest

    run_ingest(token)
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
    e.add_argument("--model", default=MODEL_NAME, choices=["elo-dc-v1", "elo-dc-v2"])
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
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

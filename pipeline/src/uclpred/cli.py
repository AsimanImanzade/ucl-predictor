"""uclpred command line."""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv

from uclpred.config import ROOT


def _ingest(_args: argparse.Namespace) -> int:
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


def _export(args: argparse.Namespace) -> int:
    from datetime import UTC, datetime
    from pathlib import Path

    from uclpred.export import run_export

    if args.as_of == "now":
        as_of = datetime.now(UTC).replace(microsecond=0)
    else:
        as_of = datetime.fromisoformat(args.as_of)
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=UTC)
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    print(run_export(as_of, out))
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="uclpred")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser(
        "ingest", help="fetch all sources and build data/processed/matches.parquet"
    ).set_defaults(func=_ingest)
    c = sub.add_parser(
        "coefficients", help="fetch UEFA club coefficients into data/reference"
    )
    c.add_argument("--season-year", type=int, required=True)
    c.set_defaults(func=_coefficients)
    sub.add_parser(
        "coverage", help="write reports/coverage.md and list duplicate team candidates"
    ).set_defaults(func=_coverage)
    e = sub.add_parser("export", help="write season.json and lambdas.json snapshot")
    e.add_argument("--as-of", required=True, help="ISO date/time (UTC) or 'now'")
    e.add_argument("--out", required=True, help="output dir (relative to repo root)")
    e.set_defaults(func=_export)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

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


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="uclpred")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser(
        "ingest", help="fetch all sources and build data/processed/matches.parquet"
    ).set_defaults(func=_ingest)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

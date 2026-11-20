"""Team identity resolution: one canonical team id across all data sources."""

import csv
import re
import unicodedata
from pathlib import Path

from uclpred.config import REFERENCE

ISO3_TO_FIFA: dict[str, str] = {
    "DEU": "GER",
    "GRC": "GRE",
    "NLD": "NED",
    "CHE": "SUI",
    "DNK": "DEN",
    "HRV": "CRO",
    "BGR": "BUL",
    "PRT": "POR",
    # football-data labels; Monaco plays in the French league, so FRA is intentional.
    "MCO": "FRA",
    "SER": "SRB",
}

LEAGUE_COUNTRY: dict[str, str] = {
    "en": "ENG",
    "sco": "SCO",
    "de": "GER",
    "es": "ESP",
    "fr": "FRA",
    "it": "ITA",
    "nl": "NED",
    "pt": "POR",
    "at": "AUT",
    "be": "BEL",
    "gr": "GRE",
    "tr": "TUR",
}

DEFAULT_ALIASES_PATH = REFERENCE / "team_aliases.csv"

STOP_TOKENS = frozenset(
    [
        "fc",
        "cf",
        "sc",
        "ac",
        "afc",
        "ssc",
        "sk",
        "fk",
        "kv",
        "club",
        "de",
        "da",
        "the",
        "cd",
        "sl",
        "pae",
        "bsc",
        "as",
        "rc",
        "osc",
        "sv",
        "ud",
        "sd",
        "nk",
        "hnk",
        "gnk",
        "pfc",
        "kf",
        "if",
        "ff",
        "bk",
    ]
)


_TRANSLIT = str.maketrans(
    {
        "ø": "o",
        "æ": "ae",
        "œ": "oe",
        "ł": "l",
        "đ": "d",
        "ð": "d",
        "þ": "th",
        "ß": "ss",
        "ı": "i",
    }
)


def core_name(name: str) -> str:
    """Normalise a club name: strip accents, lowercase, drop noise tokens."""
    text = unicodedata.normalize("NFKD", name.lower().translate(_TRANSLIT))
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    tokens = [t for t in text.split() if not t.isdigit() and t not in STOP_TOKENS]
    return " ".join(tokens)


class TeamResolver:
    def __init__(self, aliases_path: Path = DEFAULT_ALIASES_PATH):
        self._aliases: dict[tuple[str, str], str] = {}
        with open(aliases_path, newline="", encoding="utf-8-sig") as f:
            for n, row in enumerate(csv.DictReader(f), start=2):
                if not row["country"].strip():
                    raise ValueError(f"{aliases_path}:{n}: empty country")
                key = (self._fifa(row["country"]), core_name(row["variant_core"]))
                if key in self._aliases:
                    raise ValueError(f"{aliases_path}:{n}: duplicate alias {key}")
                self._aliases[key] = core_name(row["canonical_core"])

    @staticmethod
    def _fifa(country: str) -> str:
        code = country.strip().upper()
        if not code:
            raise ValueError("empty country code")
        return ISO3_TO_FIFA.get(code, code)

    def core(self, country: str, name: str) -> str:
        core = core_name(name)
        if not core:
            raise ValueError(f"empty team name: {name!r}")
        return self._aliases.get((self._fifa(country), core), core)

    def resolve(self, country: str, name: str) -> str:
        slug = self.core(country, name).replace(" ", "-")
        return f"{self._fifa(country).lower()}-{slug}"

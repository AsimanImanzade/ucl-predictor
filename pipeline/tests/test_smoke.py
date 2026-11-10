from uclpred.config import PRESEASON_AS_OF


def test_preseason_as_of_is_utc_iso() -> None:
    assert PRESEASON_AS_OF.isoformat() == "2026-09-07T00:00:00+00:00"


def test_euro_seasons_include_current():
    from uclpred.ingest.run import EURO_SEASONS

    assert EURO_SEASONS[-1] == "2026-27"

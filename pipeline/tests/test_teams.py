import pytest

from uclpred.teams import TeamResolver, core_name


@pytest.fixture
def resolver(tmp_path):
    p = tmp_path / "aliases.csv"
    p.write_text(
        "country,variant_core,canonical_core\nPOR,sport lisboa e benfica,benfica\n"
    )
    return TeamResolver(p)


def test_core_name_accents_and_stopwords():
    assert (
        core_name("Club Atlético de Madrid")
        == core_name("Atlético Madrid")
        == "atletico madrid"
    )
    assert core_name("Real Madrid CF") == "real madrid"
    assert (
        core_name("ŠK Slovan Bratislava")
        == core_name("Slovan Bratislava")
        == "slovan bratislava"
    )
    assert core_name("Stade Brestois 29") == "stade brestois"
    assert core_name("PAE AEK") == "aek"
    assert core_name("Lille OSC") == "lille"


def test_alias_resolves_to_same_id(resolver):
    assert resolver.resolve("POR", "Sport Lisboa e Benfica") == "por-benfica"
    assert resolver.resolve("POR", "SL Benfica") == "por-benfica"


def test_iso3_country_mapped(resolver):
    assert resolver.resolve("DEU", "FC Bayern München") == "ger-bayern-munchen"
    assert resolver.resolve("GER", "FC Bayern München") == "ger-bayern-munchen"


def test_empty_name_raises(resolver):
    with pytest.raises(ValueError):
        resolver.resolve("GER", "")
    with pytest.raises(ValueError):
        resolver.resolve("GER", "FC")

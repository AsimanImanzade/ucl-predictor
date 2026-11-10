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


def test_core_name_transliterates_non_decomposable_letters():
    assert core_name("FK Bodø/Glimt") == "bodo glimt"
    assert core_name("Łódź") == "lodz"
    assert core_name("Kasımpaşa") == "kasimpasa"


def test_resolve_bodo_glimt(resolver):
    assert resolver.resolve("NOR", "FK Bodø/Glimt") == "nor-bodo-glimt"


def test_monaco_and_crvena_zvezda_country_codes_merge(resolver):
    assert resolver.resolve("MCO", "AS Monaco FC") == resolver.resolve(
        "FRA", "AS Monaco"
    )
    assert resolver.resolve("SER", "FK Crvena Zvezda") == resolver.resolve(
        "SRB", "Crvena Zvezda"
    )


def _csv(tmp_path, body, encoding="utf-8"):
    p = tmp_path / "a.csv"
    p.write_bytes(("country,variant_core,canonical_core\n" + body).encode(encoding))
    return p


def test_alias_csv_with_bom(tmp_path):
    p = tmp_path / "a.csv"
    p.write_bytes(
        b"\xef\xbb\xbfcountry,variant_core,canonical_core\nPOR,sl benfica,benfica\n"
    )
    assert TeamResolver(p).resolve("POR", "SL Benfica") == "por-benfica"


def test_alias_csv_iso3_country_normalised(tmp_path):
    r = TeamResolver(_csv(tmp_path, "PRT,sport lisboa e benfica,benfica\n"))
    assert r.resolve("POR", "Sport Lisboa e Benfica") == "por-benfica"


def test_alias_csv_non_normalised_variant(tmp_path):
    r = TeamResolver(_csv(tmp_path, "por,Sport Lisboa e Benfica FC,Benfica\n"))
    assert r.resolve("POR", "Sport Lisboa e Benfica") == "por-benfica"


def test_alias_csv_duplicate_row_raises(tmp_path):
    body = "POR,sport lisboa e benfica,benfica\nPRT,Sport Lisboa e Benfica,benfica\n"
    with pytest.raises(ValueError, match="duplicate"):
        TeamResolver(_csv(tmp_path, body))


def test_alias_csv_empty_country_raises(tmp_path):
    with pytest.raises(ValueError, match="country"):
        TeamResolver(_csv(tmp_path, " ,sport lisboa e benfica,benfica\n"))


def test_resolve_empty_country_raises(resolver):
    with pytest.raises(ValueError, match="country"):
        resolver.resolve("", "Arsenal")


def test_olympiacos_and_paphos_aliases_unify():
    r = TeamResolver()
    assert r.resolve("GRE", "Olympiacos FC") == "gre-olympiakos-piraeus"
    assert r.resolve("GRE", "Olympiakos SFP") == "gre-olympiakos-piraeus"
    assert r.resolve("CYP", "Pafos FC") == r.resolve("CYP", "Paphos FC") == "cyp-paphos"
    assert r.resolve("DEN", "F.C. Copenhagen") == "den-kobenhavn"

from pipeline.clean import normalize_name, resolve_or_create

from app.models import Horse


def test_normalize_strips_suffix_case_punct():
    assert normalize_name("Belle Isle (NZ)") == "belle isle"
    assert normalize_name("  Belle  Isle ") == "belle isle"
    assert normalize_name("Belle-Isle") == "belle isle"
    assert normalize_name("The Quick Fox") == "quick fox"


def test_normalize_accents():
    assert normalize_name("Café Noir") == "cafe noir"


def test_resolve_or_create_is_idempotent(db):
    a = resolve_or_create(db, Horse, "Belle Isle (NZ)")
    b = resolve_or_create(db, Horse, "belle isle")
    c = resolve_or_create(db, Horse, "BELLE-ISLE")
    db.commit()
    assert a.id == b.id == c.id


def test_resolve_or_create_distinct_names(db):
    a = resolve_or_create(db, Horse, "Alpha Star")
    b = resolve_or_create(db, Horse, "Beta Star")
    db.commit()
    assert a.id != b.id

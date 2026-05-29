import json

from compliance_agent.packs import load_bundled_packs, load_pack


def test_load_bundled_license_pack_validates():
    packs = load_bundled_packs()
    ids = {p.id for p in packs}
    assert "license-core" in ids
    pack = next(p for p in packs if p.id == "license-core")
    ob_ids = {o.id for o in pack.obligations}
    assert {"lic-gpl-incompat", "lic-apache-notice"} <= ob_ids
    # Every obligation carries a verbatim citation (spec invariant).
    for o in pack.obligations:
        assert o.source.clause_quote.strip()
        assert o.source.url_or_section.strip()


def test_load_pack_from_path(tmp_path):
    data = {
        "id": "p1",
        "domain": "license",
        "provenance": "public",
        "source_doc": "x",
        "source_version": "v1",
        "compiled_at": "2026-05-28",
        "obligations": [],
    }
    f = tmp_path / "p.json"
    f.write_text(json.dumps(data))
    pack = load_pack(str(f))
    assert pack.id == "p1" and pack.obligations == []

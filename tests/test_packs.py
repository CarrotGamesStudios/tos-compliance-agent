import json

import pytest

from compliance_agent.errors import ProjectScanError
from compliance_agent.models import PolicyPack
from compliance_agent.packs import (
    load_active_packs,
    load_bundled_packs,
    load_pack,
    save_pack,
    validate_pack_id,
)


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


def test_all_bundled_packs_present_and_valid():
    # load_bundled_packs validates every obligation's applies_when predicate on load.
    ids = {p.id for p in load_bundled_packs()}
    assert {"license-core", "privacy-core", "ai-aup-core", "api-tos-core"} <= ids


def test_every_bundled_obligation_has_citation_and_domain_matches():
    for pack in load_bundled_packs():
        for o in pack.obligations:
            assert o.source.clause_quote.strip() and o.source.url_or_section.strip()
            assert o.domain == pack.domain


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


def _empty_pack(pack_id):
    return PolicyPack(
        id=pack_id,
        domain="license",
        provenance="public",
        source_doc="d",
        source_version="v",
        compiled_at="2026-05-28",
        obligations=[],
    )


def test_load_active_packs_includes_user_dir(tmp_path, monkeypatch):
    # A user-compiled pack in $COMPLIANCE_PACKS_DIR is enforced alongside the bundled ones.
    save_pack(str(tmp_path), _empty_pack("my-custom-pack"))
    monkeypatch.setenv("COMPLIANCE_PACKS_DIR", str(tmp_path))
    ids = {p.id for p in load_active_packs()}
    assert "license-core" in ids  # bundled still present
    assert "my-custom-pack" in ids  # user pack now enforced


def test_load_active_packs_user_overrides_bundled(tmp_path, monkeypatch):
    save_pack(str(tmp_path), _empty_pack("license-core"))  # same id as bundled
    monkeypatch.setenv("COMPLIANCE_PACKS_DIR", str(tmp_path))
    packs = [p for p in load_active_packs() if p.id == "license-core"]
    assert len(packs) == 1 and packs[0].obligations == []  # user version wins


def test_save_pack_rejects_traversal_id(tmp_path):
    with pytest.raises(ProjectScanError):
        save_pack(str(tmp_path), _empty_pack("../../evil"))


def test_validate_pack_id_rejects_separators():
    with pytest.raises(ProjectScanError):
        validate_pack_id("foo/bar")
    assert validate_pack_id("gpl-3.0") == "gpl-3.0"


def test_load_active_packs_warns_on_bad_dir(monkeypatch, capsys, tmp_path):
    bogus = tmp_path / "not-a-dir"
    bogus.write_text("x")  # a file, not a directory
    monkeypatch.setenv("COMPLIANCE_PACKS_DIR", str(bogus))
    packs = load_active_packs()
    assert {p.id for p in packs} == {p.id for p in load_bundled_packs()}  # falls back to bundled
    assert "is not a directory" in capsys.readouterr().err

import json

from compliance_agent.compiler.schema import (
    CompiledObligation,
    CompiledSource,
    CompilerOutput,
)
from compliance_agent.models import Check, Fix
from compliance_agent.refresh import refresh_packs
from compliance_agent.sources import LocalSourceStore

CLAUSE = "You must retain all attribution notices in a NOTICE file"


class FakeModelClient:
    def generate_structured(self, *, prompt, schema, model):
        # Always emits one valid obligation whose clause is present in CLAUSE-bearing docs.
        return CompilerOutput(
            obligations=[
                CompiledObligation(
                    id="x-1",
                    domain="license",
                    source=CompiledSource(clause_quote=CLAUSE, url_or_section="§4"),
                    applies_when={"dep_license_in": ["Apache-2.0"]},
                    requirement="r",
                    check=Check(
                        kind="deterministic",
                        analyzer="missing_notice",
                        params={"attribution_licenses": ["Apache-2.0"]},
                    ),
                    severity="medium",
                    fix=Fix(kind="auto", codemod="add_notice_entries", guidance="g"),
                )
            ]
        )


def _make_store(tmp_path, text):
    (tmp_path / "doc.txt").write_text(text)
    (tmp_path / "sources.json").write_text(
        json.dumps(
            [{"id": "apache-notice", "domain": "license", "file": "doc.txt", "url_base": "u"}]
        )
    )
    return LocalSourceStore(str(tmp_path))


def test_refresh_compiles_then_skips_unchanged_then_detects_drift(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    packs_dir = tmp_path / "packs"
    store = _make_store(src_dir, f"Section 4. {CLAUSE}.")
    client = FakeModelClient()

    # First run: compiles the doc (upstream drift = True since nothing existed).
    r1 = refresh_packs(store, client, str(packs_dir), compiled_at="2026-05-28")
    assert [c["id"] for c in r1["changed"]] == ["apache-notice"]
    assert r1["upstream_drift"] is True
    assert (packs_dir / "apache-notice.json").is_file()

    # Second run, unchanged source: no recompile, no drift.
    r2 = refresh_packs(store, client, str(packs_dir), compiled_at="2026-05-28")
    assert r2["changed"] == []
    assert r2["unchanged"] == ["apache-notice"]
    assert r2["upstream_drift"] is False

    # Edit the source document -> content hash changes -> upstream drift -> recompile.
    store2 = _make_store(src_dir, f"Section 4 (revised 2026). {CLAUSE}.")
    r3 = refresh_packs(store2, client, str(packs_dir), compiled_at="2026-05-28")
    assert [c["id"] for c in r3["changed"]] == ["apache-notice"]
    assert r3["upstream_drift"] is True

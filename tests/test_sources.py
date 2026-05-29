import json

import pytest

from compliance_agent.errors import ProjectScanError
from compliance_agent.sources import LocalSourceStore


def test_local_source_store_reads_manifest_and_files(tmp_path):
    (tmp_path / "gpl.txt").write_text("GPL text")
    (tmp_path / "sources.json").write_text(
        json.dumps(
            [
                {
                    "id": "gpl-3.0",
                    "domain": "license",
                    "file": "gpl.txt",
                    "url_base": "https://gnu.org",
                    "provenance": "public",
                }
            ]
        )
    )
    docs = LocalSourceStore(str(tmp_path)).list_documents()
    assert len(docs) == 1
    assert docs[0].id == "gpl-3.0"
    assert docs[0].text == "GPL text"
    assert docs[0].domain == "license"


def test_local_source_store_loads_contract_domain(tmp_path):
    (tmp_path / "dpa.txt").write_text("Sub-processors must be authorized in writing.")
    (tmp_path / "sources.json").write_text(
        json.dumps(
            [{"id": "acme-dpa", "domain": "contract", "file": "dpa.txt", "provenance": "internal"}]
        )
    )
    docs = LocalSourceStore(str(tmp_path)).list_documents()
    assert docs[0].domain == "contract" and docs[0].provenance == "internal"
    assert "Sub-processors" in docs[0].text


def test_local_source_store_missing_manifest_raises(tmp_path):
    with pytest.raises(ProjectScanError):
        LocalSourceStore(str(tmp_path)).list_documents()


def test_local_source_store_missing_file_raises(tmp_path):
    (tmp_path / "sources.json").write_text(
        json.dumps([{"id": "x", "domain": "license", "file": "nope.txt"}])
    )
    with pytest.raises(ProjectScanError):
        LocalSourceStore(str(tmp_path)).list_documents()


def test_local_source_store_non_dict_entry_raises_cleanly(tmp_path):
    # A malformed manifest with a non-dict entry must raise ProjectScanError, not AttributeError.
    (tmp_path / "sources.json").write_text(json.dumps(["not-a-dict-entry"]))
    with pytest.raises(ProjectScanError):
        LocalSourceStore(str(tmp_path)).list_documents()

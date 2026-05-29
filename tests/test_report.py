import json

from compliance_agent.models import Evidence, Finding, ProjectModel
from compliance_agent.report import to_json, to_markdown


def _findings():
    return [
        Finding(
            obligation_id="lic-gpl-incompat",
            domain="license",
            severity="high",
            status="violation",
            evidence=[Evidence(file="pyproject.toml", snippet="gpllib (GPL-3.0)")],
            citation={"clause_quote": "You may convey...", "url_or_section": "GPL-3.0 §5"},
            remediation={"kind": "manual", "guidance": "Replace dep."},
            confidence=1.0,
        )
    ]


def test_to_json_is_parseable_and_complete():
    payload = json.loads(to_json(_findings(), ProjectModel(hash="h", root="/p")))
    assert payload["summary"]["violations"] == 1
    assert payload["findings"][0]["obligation_id"] == "lic-gpl-incompat"


def test_to_markdown_includes_citation_and_evidence():
    md = to_markdown(_findings(), unscanned=[{"file": "dist:x", "reason": "not found"}])
    assert "lic-gpl-incompat" in md
    assert "GPL-3.0 §5" in md  # citation present
    assert "gpllib (GPL-3.0)" in md  # evidence present
    assert "dist:x" in md  # unscanned surfaced, not hidden


def test_to_markdown_clean_project():
    assert "No compliance findings" in to_markdown([], unscanned=[])

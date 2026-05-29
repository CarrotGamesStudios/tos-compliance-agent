from compliance_agent.models import (
    Baseline,
    Check,
    Dependency,
    Evidence,
    Finding,
    Fix,
    Obligation,
    PolicyPack,
    ProjectModel,
    Source,
)


def test_obligation_roundtrips_through_json():
    ob = Obligation(
        id="lic-gpl-incompat",
        domain="license",
        source=Source(
            doc="gpl-3.0",
            provenance="public",
            version="spdx-2026",
            clause_quote="You may convey a covered work...",
            url_or_section="GPL-3.0 §5",
        ),
        applies_when={"all": [{"has_dep_license": "GPL-3.0"}]},
        requirement="GPL-3.0 deps require the project to be GPL-compatible.",
        check=Check(
            kind="deterministic",
            analyzer="gpl_incompatibility",
            params={"incompatible_licenses": ["GPL-3.0"]},
        ),
        severity="high",
        fix=Fix(kind="manual", guidance="Replace the dependency or relicense."),
    )
    dumped = ob.model_dump_json()
    again = Obligation.model_validate_json(dumped)
    assert again == ob


def test_project_model_defaults():
    pm = ProjectModel(hash="abc", root="/tmp/p")
    assert pm.dependencies == []
    assert pm.notice_file_present is False
    assert pm.project_license is None


def test_finding_carries_citation():
    f = Finding(
        obligation_id="x",
        domain="license",
        severity="high",
        status="violation",
        evidence=[Evidence(file="pyproject.toml", line=None, snippet="dep: somelib")],
        citation={"clause_quote": "q", "url_or_section": "GPL-3.0 §5"},
        remediation={"kind": "manual", "guidance": "g"},
        confidence=1.0,
    )
    assert f.citation["url_or_section"] == "GPL-3.0 §5"


def test_policy_pack_and_baseline_construct():
    pack = PolicyPack(
        id="p",
        domain="license",
        provenance="public",
        source_doc="d",
        source_version="v",
        compiled_at="2026-05-28",
        obligations=[],
    )
    assert pack.obligations == []
    base = Baseline(project_model_hash="h", findings=[])
    assert base.policy_pack_versions == {}
    assert Dependency(name="x").license == "UNKNOWN"

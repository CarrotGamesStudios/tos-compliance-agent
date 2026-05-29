from compliance_agent.drift import compute_drift, finding_key, load_baseline, save_baseline
from compliance_agent.models import Baseline, Evidence, Finding


def _finding(ob_id, snippet):
    return Finding(
        obligation_id=ob_id,
        domain="license",
        severity="high",
        status="violation",
        evidence=[Evidence(file="pyproject.toml", snippet=snippet)],
        citation={"clause_quote": "q", "url_or_section": "s"},
        remediation={"kind": "manual", "guidance": "g"},
        confidence=1.0,
    )


def test_finding_key_stable_and_distinct():
    a = _finding("lic-gpl-incompat", "gpllib (GPL-3.0)")
    b = _finding("lic-gpl-incompat", "otherlib (GPL-3.0)")
    assert finding_key(a) == finding_key(_finding("lic-gpl-incompat", "gpllib (GPL-3.0)"))
    assert finding_key(a) != finding_key(b)


def test_compute_drift_reports_new_and_resolved():
    base = Baseline(
        project_model_hash="h0", findings=[_finding("lic-gpl-incompat", "gpllib (GPL-3.0)")]
    )
    current = [_finding("lic-apache-notice", "missing attribution for: apachelib")]
    delta = compute_drift(current, base)
    assert [f.obligation_id for f in delta["new"]] == ["lic-apache-notice"]
    assert [f.obligation_id for f in delta["resolved"]] == ["lic-gpl-incompat"]


def test_compute_drift_against_none_baseline_all_new():
    current = [_finding("lic-gpl-incompat", "gpllib (GPL-3.0)")]
    delta = compute_drift(current, None)
    assert len(delta["new"]) == 1 and delta["resolved"] == []


def _gpl_finding(*deps):
    return Finding(
        obligation_id="lic-gpl-incompat",
        domain="license",
        severity="high",
        status="violation",
        evidence=[Evidence(file="pyproject.toml", snippet=d) for d in deps],
        citation={"clause_quote": "q", "url_or_section": "s"},
        remediation={"kind": "manual", "guidance": "g"},
        confidence=1.0,
    )


def test_adding_a_dep_does_not_spuriously_resolve_original():
    base = Baseline(project_model_hash="h", findings=[_gpl_finding("gpllib (GPL-3.0)")])
    current = [_gpl_finding("gpllib (GPL-3.0)", "otherlib (GPL-3.0)")]
    delta = compute_drift(current, base)
    # The original GPL violation is NOT resolved (gpllib still offends); the growing
    # violation is reported as new because it introduced a new evidence row.
    assert delta["resolved"] == []
    assert [f.obligation_id for f in delta["new"]] == ["lic-gpl-incompat"]


def _notice_finding(*deps):
    return Finding(
        obligation_id="lic-apache-notice",
        domain="license",
        severity="medium",
        status="violation",
        evidence=[Evidence(file="NOTICE", snippet=f"missing attribution for: {d}") for d in deps],
        citation={"clause_quote": "q", "url_or_section": "s"},
        remediation={"kind": "auto", "guidance": "g"},
        confidence=1.0,
    )


def test_notice_finding_adding_dep_does_not_resolve_original():
    # Regression for the round-3 agy finding: per-dep NOTICE evidence keeps drift granular.
    base = Baseline(project_model_hash="h", findings=[_notice_finding("apachelib")])
    current = [_notice_finding("apachelib", "newapache")]
    delta = compute_drift(current, base)
    assert delta["resolved"] == []
    assert [f.obligation_id for f in delta["new"]] == ["lic-apache-notice"]


def test_removing_only_dep_resolves_finding():
    base = Baseline(project_model_hash="h", findings=[_gpl_finding("gpllib (GPL-3.0)")])
    delta = compute_drift([], base)
    assert [f.obligation_id for f in delta["resolved"]] == ["lic-gpl-incompat"]
    assert delta["new"] == []


def test_baseline_roundtrip(tmp_path):
    path = tmp_path / "baseline.json"
    base = Baseline(
        project_model_hash="h1",
        policy_pack_versions={"license-core": "2026-05-28"},
        findings=[_finding("lic-gpl-incompat", "gpllib (GPL-3.0)")],
    )
    save_baseline(str(path), base)
    loaded = load_baseline(str(path))
    assert loaded == base
    assert load_baseline(str(tmp_path / "missing.json")) is None

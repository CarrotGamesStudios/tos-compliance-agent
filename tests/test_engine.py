from compliance_agent.engine import evaluate
from compliance_agent.models import Dependency, ProjectModel
from compliance_agent.packs import load_bundled_packs


def test_evaluate_flags_gpl_and_notice_violations():
    model = ProjectModel(
        hash="h",
        root="/p",
        project_license="MIT",
        dependencies=[
            Dependency(name="gpllib", license="GPL-3.0"),
            Dependency(name="apachelib", license="Apache-2.0"),
        ],
        notice_file_present=False,
    )
    findings = evaluate(model, load_bundled_packs())
    by_id = {f.obligation_id: f for f in findings}

    assert "lic-gpl-incompat" in by_id
    assert by_id["lic-gpl-incompat"].status == "violation"
    assert by_id["lic-gpl-incompat"].confidence == 1.0
    assert by_id["lic-gpl-incompat"].citation["url_or_section"].startswith("https://www.gnu.org")
    assert by_id["lic-gpl-incompat"].remediation["kind"] == "manual"

    assert "lic-apache-notice" in by_id
    assert by_id["lic-apache-notice"].remediation["kind"] == "auto"


def test_evaluate_clean_project_has_no_findings():
    model = ProjectModel(
        hash="h",
        root="/p",
        project_license="MIT",
        dependencies=[Dependency(name="ok", license="MIT")],
        notice_file_present=True,
    )
    assert evaluate(model, load_bundled_packs()) == []

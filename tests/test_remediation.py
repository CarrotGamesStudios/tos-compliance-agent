import pytest

from compliance_agent.models import Dependency, Evidence, Finding, ProjectModel
from compliance_agent.remediation import apply_fix, generate_notice_content


def _model(tmp_path, notice=False):
    if notice:
        (tmp_path / "NOTICE").write_text("Existing.\n")
    return ProjectModel(
        hash="h",
        root=str(tmp_path),
        project_license="MIT",
        dependencies=[
            Dependency(name="apachelib", license="Apache-2.0"),
            Dependency(name="ok", license="MIT"),
        ],
        notice_file_present=notice,
    )


def _notice_finding():
    return Finding(
        obligation_id="lic-apache-notice",
        domain="license",
        severity="medium",
        status="violation",
        evidence=[Evidence(file="NOTICE", snippet="missing")],
        citation={"clause_quote": "q", "url_or_section": "s"},
        remediation={"kind": "auto", "codemod": "add_notice_entries", "guidance": "g"},
        confidence=1.0,
    )


def test_generate_notice_lists_attribution_deps(tmp_path):
    content = generate_notice_content(_model(tmp_path), _notice_finding())
    assert "apachelib" in content and "Apache-2.0" in content
    assert "ok" not in content  # MIT dep not an attribution dep


def test_apply_fix_writes_notice_file(tmp_path):
    model = _model(tmp_path)
    path = apply_fix(model, _notice_finding())
    assert (tmp_path / "NOTICE").is_file()
    assert "apachelib" in (tmp_path / "NOTICE").read_text()
    assert path.endswith("NOTICE")


def test_apply_fix_refuses_manual_finding(tmp_path):
    model = _model(tmp_path)
    manual = _notice_finding()
    manual.remediation = {"kind": "manual", "guidance": "g"}
    with pytest.raises(ValueError):
        apply_fix(model, manual)


def test_generate_notice_preserves_existing_content(tmp_path):
    model = _model(tmp_path)
    model.notice_text = "NOTICE\n\nCopyright 2026 Acme Corp. All rights reserved.\n"
    content = generate_notice_content(model, _notice_finding())
    assert "Acme Corp" in content  # custom attribution preserved, not clobbered
    assert "apachelib" in content  # new entry appended


def test_generate_notice_does_not_duplicate_existing_entry(tmp_path):
    model = _model(tmp_path)
    model.notice_text = "NOTICE\n- apachelib (Apache-2.0)\n"
    content = generate_notice_content(model, _notice_finding())
    assert content.count("apachelib") == 1  # already listed -> not appended again


def test_generate_notice_honors_pack_attribution_licenses(tmp_path):
    model = _model(tmp_path)
    model.dependencies.append(
        type(model.dependencies[0])(name="mpllib", license="MPL-2.0")
    )
    finding = _notice_finding()
    finding.remediation["params"] = {"attribution_licenses": ["MPL-2.0"]}
    content = generate_notice_content(model, finding)
    assert "mpllib" in content and "apachelib" not in content


def test_apply_fix_refuses_symlink_escape(tmp_path):
    from compliance_agent.errors import ProjectScanError

    outside = tmp_path / "outside"
    outside.mkdir()
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "pyproject.toml").write_text('[project]\nname="p"\nlicense="MIT"\n')
    # NOTICE is a symlink pointing outside the project root.
    (proj / "NOTICE").symlink_to(outside / "evil.txt")
    model = _model(proj)
    model.root = str(proj)
    with pytest.raises(ProjectScanError):
        apply_fix(model, _notice_finding())

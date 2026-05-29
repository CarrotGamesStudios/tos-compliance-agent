from compliance_agent.mcp_server import (
    _apply,
    _scan,
    explain_obligation,
    list_policy_packs,
    needs_confirmation,
    scan_project,
)
from compliance_agent.models import Finding


def _write_project(tmp_path, deps, project_license="MIT"):
    dep_str = ", ".join(f'"{d}>=1.0"' for d in deps)
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname="demo"\nlicense="{project_license}"\ndependencies=[{dep_str}]\n'
    )


class _Lookup:
    def __init__(self, table):
        self.table = table

    def get(self, name):
        return self.table.get(name)


def test_scan_project_returns_structured_findings(tmp_path):
    _write_project(tmp_path, ["apachelib"])
    result = _scan(str(tmp_path), dist_lookup=_Lookup({"apachelib": ("Apache-2.0", [], None)}))
    assert result["summary"]["violations"] == 1
    assert result["findings"][0]["obligation_id"] == "lic-apache-notice"


def test_explain_obligation_returns_citation():
    info = explain_obligation("lic-gpl-incompat")
    assert info["citation"]["url_or_section"].startswith("https://www.gnu.org")
    assert info["requirement"]


def test_list_policy_packs_includes_license_core():
    packs = list_policy_packs()
    assert any(p["id"] == "license-core" for p in packs)


def test_public_scan_tool_returns_error_on_bad_path():
    # The public tool takes only `path` (no dist_lookup seam) and returns a structured error.
    result = scan_project("/nonexistent/path/xyz")
    assert "error" in result


def test_apply_deterministic_fix_without_confirm(tmp_path):
    _write_project(tmp_path, ["apachelib"])
    lookup = _Lookup({"apachelib": ("Apache-2.0", [], None)})
    out = _apply(str(tmp_path), "lic-apache-notice", confirm=False, dist_lookup=lookup)
    assert out.get("applied") is True  # deterministic (confidence 1.0) applies without confirm
    assert (tmp_path / "NOTICE").is_file()


def test_apply_manual_finding_is_refused(tmp_path):
    _write_project(tmp_path, ["gpllib"])
    lookup = _Lookup(
        {
            "gpllib": (
                None,
                ["License :: OSI Approved :: GNU General Public License v3 (GPLv3)"],
                None,
            )
        }
    )
    out = _apply(str(tmp_path), "lic-gpl-incompat", confirm=False, dist_lookup=lookup)
    assert "error" in out and out.get("applied") is not True


def _synthetic_finding(confidence):
    return Finding(
        obligation_id="x",
        domain="ai_aup",
        severity="high",
        status="violation",
        evidence=[],
        citation={"clause_quote": "q", "url_or_section": "s"},
        remediation={"kind": "auto", "codemod": "noop"},
        confidence=confidence,
    )


def test_confirm_gate_blocks_llm_proposed_without_confirm():
    # Future LLM-proposed auto-fix (confidence < 1.0): blocked unless confirm=True.
    assert needs_confirmation(_synthetic_finding(0.7), confirm=False) is True
    assert needs_confirmation(_synthetic_finding(0.7), confirm=True) is False


def test_confirm_gate_allows_deterministic():
    # Deterministic (confidence == 1.0) applies without confirm.
    assert needs_confirmation(_synthetic_finding(1.0), confirm=False) is False


def test_select_port_valid_and_fallbacks():
    from compliance_agent.mcp_server import select_port

    assert select_port("9090") == 9090
    assert select_port(None) == 8080
    assert select_port("not-a-number") == 8080
    assert select_port("0") == 8080  # out of range
    assert select_port("70000") == 8080  # out of range
    assert select_port("-5") == 8080


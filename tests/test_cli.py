import pytest

from compliance_agent.cli import main


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


def test_scan_reports_violation_and_returns_nonzero(tmp_path, capsys):
    _write_project(tmp_path, ["apachelib"])
    lookup = _Lookup({"apachelib": ("Apache-2.0", [], None)})
    code = main(["scan", str(tmp_path)], dist_lookup=lookup)
    out = capsys.readouterr().out
    assert "lic-apache-notice" in out
    assert code == 1  # violations -> non-zero exit


def test_scan_clean_project_returns_zero(tmp_path, capsys):
    _write_project(tmp_path, ["ok"])
    code = main(["scan", str(tmp_path)], dist_lookup=_Lookup({"ok": (None, [], "MIT")}))
    assert code == 0
    assert "No compliance findings" in capsys.readouterr().out


def test_fix_apply_creates_notice_and_then_clean(tmp_path, capsys):
    _write_project(tmp_path, ["apachelib"])
    lookup = _Lookup({"apachelib": ("Apache-2.0", [], None)})
    fix_code = main(["fix", str(tmp_path), "--apply"], dist_lookup=lookup)
    assert (tmp_path / "NOTICE").is_file()
    assert fix_code == 0
    # Re-scan now clean for the notice obligation.
    assert main(["scan", str(tmp_path)], dist_lookup=lookup) == 0


def test_missing_pyproject_exits_with_friendly_error(tmp_path, capsys):
    code = main(["scan", str(tmp_path)])  # empty dir, no pyproject.toml
    assert code == 2
    assert "no pyproject.toml" in capsys.readouterr().err


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "compliance-agent" in capsys.readouterr().out

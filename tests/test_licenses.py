from compliance_agent.scanners.licenses import build_project_model, license_from_metadata


def test_prefers_license_expression():
    assert license_from_metadata("Apache-2.0", [], None) == "Apache-2.0"


def test_falls_back_to_classifier():
    out = license_from_metadata(
        None, ["License :: OSI Approved :: GNU General Public License v3 (GPLv3)"], None
    )
    assert out == "GPL-3.0"


def test_falls_back_to_short_license_field():
    assert license_from_metadata(None, [], "MIT") == "MIT"


def test_multiline_license_field_is_unknown():
    body = "Permission is hereby granted, free of charge,\nto any person obtaining a copy..."
    assert license_from_metadata(None, [], body) == "UNKNOWN"


def test_overlong_single_line_license_field_is_unknown():
    long_text = "Permission is hereby granted free of charge to any person obtaining a copy"
    assert len(long_text) > 64
    assert license_from_metadata(None, [], long_text) == "UNKNOWN"


def test_spdx_expression_with_spaces_is_kept():
    assert license_from_metadata("Apache-2.0 OR MIT", [], None) == "Apache-2.0 OR MIT"


def test_informal_name_is_normalized():
    assert license_from_metadata(None, [], "Apache 2.0") == "Apache-2.0"


def test_nothing_is_unknown():
    assert license_from_metadata(None, [], None) == "UNKNOWN"


class FakeLookup:
    """Stand-in for importlib.metadata: name -> (license_expression, classifiers, license_field)."""

    def __init__(self, table):
        self.table = table

    def get(self, name):
        return self.table.get(name)


def test_build_project_model_resolves_dep_licenses(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="demo"\nlicense="MIT"\n'
        'dependencies=["gpllib>=1.0","apachelib>=2.0"]\n'
    )
    lookup = FakeLookup(
        {
            "gpllib": (
                None,
                ["License :: OSI Approved :: GNU General Public License v3 (GPLv3)"],
                None,
            ),
            "apachelib": ("Apache-2.0", [], None),
        }
    )
    pm = build_project_model(str(tmp_path), dist_lookup=lookup)

    assert pm.project_license == "MIT"
    licenses = {d.name: d.license for d in pm.dependencies}
    assert licenses == {"gpllib": "GPL-3.0", "apachelib": "Apache-2.0"}
    assert pm.notice_file_present is False
    assert pm.hash  # non-empty


def test_build_project_model_flags_unknown_lookup_as_unscanned(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="demo"\nlicense="MIT"\ndependencies=["ghostlib>=1.0"]\n'
    )
    pm = build_project_model(str(tmp_path), dist_lookup=FakeLookup({}))
    assert pm.dependencies[0].license == "UNKNOWN"
    assert pm.unscanned and pm.unscanned[0]["file"] == "dist:ghostlib"


def test_build_project_model_detects_notice_file(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname="demo"\nlicense="MIT"\n')
    (tmp_path / "NOTICE").write_text("attributions\n")
    pm = build_project_model(str(tmp_path), dist_lookup=FakeLookup({}))
    assert pm.notice_file_present is True
    assert pm.notice_text == "attributions\n"


def test_build_project_model_captures_code_facts(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname="demo"\nlicense="MIT"\n')
    (tmp_path / "app.py").write_text(
        "import logging\nimport stripe\n"
        "def f(email):\n    logging.info(email)\n"
    )
    pm = build_project_model(str(tmp_path), dist_lookup=FakeLookup({}))
    assert "stripe" in pm.imports
    assert len(pm.pii_log_sites) == 1 and "email" in pm.pii_log_sites[0].snippet


def test_build_project_model_raises_on_missing_pyproject(tmp_path):
    import pytest

    from compliance_agent.errors import ProjectScanError

    with pytest.raises(ProjectScanError):
        build_project_model(str(tmp_path), dist_lookup=FakeLookup({}))


def test_build_project_model_raises_on_malformed_pyproject(tmp_path):
    import pytest

    from compliance_agent.errors import ProjectScanError

    (tmp_path / "pyproject.toml").write_text("this is = = not valid toml [[[")
    with pytest.raises(ProjectScanError):
        build_project_model(str(tmp_path), dist_lookup=FakeLookup({}))

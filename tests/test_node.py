import json

import pytest

from compliance_agent.engine import evaluate
from compliance_agent.errors import ProjectScanError
from compliance_agent.packs import load_bundled_packs
from compliance_agent.scanners.licenses import build_project_model
from compliance_agent.scanners.node import (
    build_node_model,
    license_from_package_json,
    parse_package_json,
)


class _PkgLookup:
    def __init__(self, table):
        self.table = table

    def get(self, name):
        return self.table.get(name)


def test_license_from_package_json_forms():
    assert license_from_package_json({"license": "MIT"}) == "MIT"
    assert license_from_package_json({"license": {"type": "Apache-2.0"}}) == "Apache-2.0"
    assert license_from_package_json({"licenses": [{"type": "GPL-3.0"}]}) == "GPL-3.0"
    assert license_from_package_json({}) == "UNKNOWN"


def test_parse_package_json_collects_all_dep_sections():
    text = json.dumps(
        {
            "name": "demo",
            "license": "MIT",
            "dependencies": {"left-pad": "^1.0.0"},
            "devDependencies": {"jest": "^29"},
            "optionalDependencies": {"left-pad": "^1.0.0"},
        }
    )
    lic, names = parse_package_json(text)
    assert lic == "MIT"
    assert names == ["left-pad", "jest"]  # deduped, order preserved


def test_build_node_model_resolves_licenses_and_flags_gpl(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "demo", "license": "MIT", "dependencies": {"gpllib": "1", "ok": "1"}})
    )
    lookup = _PkgLookup({"gpllib": "GPL-3.0", "ok": "MIT"})
    model = build_node_model(str(tmp_path), pkg_lookup=lookup)
    assert model.project_license == "MIT"
    assert {d.name: d.license for d in model.dependencies} == {"gpllib": "GPL-3.0", "ok": "MIT"}

    # The SAME license analyzers fire on a Node project (GPL incompatibility).
    findings = evaluate(model, load_bundled_packs())
    assert any(f.obligation_id == "lic-gpl-incompat" for f in findings)


def test_build_node_model_pii_in_js_logs(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"name": "demo", "license": "MIT"}))
    (tmp_path / "app.js").write_text(
        "function f(userEmail, count) {\n  console.log('processing', userEmail);\n"
        "  console.log(count);\n}\n"
    )
    model = build_node_model(str(tmp_path))
    assert len(model.pii_log_sites) == 1
    assert "email" in model.pii_log_sites[0].snippet.lower()
    assert model.pii_log_sites[0].file == "app.js"


def test_build_node_model_skips_node_modules(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"name": "demo"}))
    nm = tmp_path / "node_modules" / "dep"
    nm.mkdir(parents=True)
    (nm / "index.js").write_text("console.log(password)\n")  # must be skipped
    model = build_node_model(str(tmp_path))
    assert model.pii_log_sites == []


def test_build_node_model_unknown_dep_is_unscanned(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "demo", "dependencies": {"ghost": "1"}})
    )
    model = build_node_model(str(tmp_path), pkg_lookup=_PkgLookup({}))
    assert model.dependencies[0].license == "UNKNOWN"
    assert model.unscanned and model.unscanned[0]["file"] == "npm:ghost"


def test_dispatch_node_via_build_project_model(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"name": "demo", "license": "MIT"}))
    model = build_project_model(str(tmp_path), pkg_lookup=_PkgLookup({}))
    assert model.project_license == "MIT"


def test_dispatch_errors_without_any_manifest(tmp_path):
    with pytest.raises(ProjectScanError):
        build_project_model(str(tmp_path))


def test_pii_in_nested_log_call_is_detected(tmp_path):
    # Nested call before the PII identifier must NOT truncate the arg capture.
    (tmp_path / "package.json").write_text(json.dumps({"name": "demo"}))
    (tmp_path / "a.ts").write_text("console.log(formatDate(date), userPassword);\n")
    model = build_node_model(str(tmp_path))
    assert len(model.pii_log_sites) == 1 and "password" in model.pii_log_sites[0].snippet.lower()


def test_custom_logger_receiver_is_detected(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"name": "demo"}))
    (tmp_path / "b.js").write_text("winstonLogger.error(ssn)\n")
    model = build_node_model(str(tmp_path))
    assert len(model.pii_log_sites) == 1 and "ssn" in model.pii_log_sites[0].snippet.lower()


def test_non_object_package_json_raises_cleanly(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps(["not", "an", "object"]))
    with pytest.raises(ProjectScanError):
        build_node_model(str(tmp_path))


def test_scoped_package_lookup_and_traversal_guard(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "demo", "dependencies": {"@scope/pkg": "1", "../evil": "1"}})
    )
    scoped = tmp_path / "node_modules" / "@scope" / "pkg"
    scoped.mkdir(parents=True)
    (scoped / "package.json").write_text(json.dumps({"name": "@scope/pkg", "license": "MIT"}))
    model = build_node_model(str(tmp_path))  # default node_modules lookup
    by_name = {d.name: d.license for d in model.dependencies}
    assert by_name["@scope/pkg"] == "MIT"  # scoped name resolves
    assert by_name["../evil"] == "UNKNOWN"  # traversal name refused -> UNKNOWN


def test_monorepo_warns_and_scans_python(tmp_path, capsys):
    (tmp_path / "pyproject.toml").write_text('[project]\nname="d"\nlicense="MIT"\n')
    (tmp_path / "package.json").write_text(json.dumps({"name": "d", "license": "MIT"}))

    class _NoDeps:
        def get(self, name):
            return None

    model = build_project_model(str(tmp_path), dist_lookup=_NoDeps())
    assert model.project_license == "MIT"  # scanned the Python project
    assert "both pyproject.toml and package.json" in capsys.readouterr().err

from compliance_agent.cli import main
from compliance_agent.drift import compute_drift, load_baseline, save_baseline
from compliance_agent.engine import evaluate
from compliance_agent.models import Baseline
from compliance_agent.packs import load_bundled_packs
from compliance_agent.scanners.licenses import build_project_model


class _Lookup:
    def __init__(self, table):
        self.table = table

    def get(self, name):
        return self.table.get(name)


def test_full_cycle_scan_fix_rescan_and_drift(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="demo"\nlicense="MIT"\n'
        'dependencies=["apachelib>=1.0","gpllib>=1.0"]\n'
    )
    lookup = _Lookup(
        {
            "apachelib": ("Apache-2.0", [], None),
            "gpllib": (
                None,
                ["License :: OSI Approved :: GNU General Public License v3 (GPLv3)"],
                None,
            ),
        }
    )

    # 1. Initial scan: both a GPL incompatibility and a missing-NOTICE violation.
    model = build_project_model(str(tmp_path), dist_lookup=lookup)
    findings = evaluate(model, load_bundled_packs())
    ids = {f.obligation_id for f in findings}
    assert ids == {"lic-gpl-incompat", "lic-apache-notice"}

    # Save baseline of the initial state.
    base_path = tmp_path / "baseline.json"
    save_baseline(str(base_path), Baseline(project_model_hash=model.hash, findings=findings))

    # 2. Auto-fix the NOTICE issue via the CLI.
    assert main(["fix", str(tmp_path), "--apply"], dist_lookup=lookup) == 0
    assert (tmp_path / "NOTICE").is_file()

    # 3. Re-scan: NOTICE resolved, GPL incompatibility remains (manual fix).
    model2 = build_project_model(str(tmp_path), dist_lookup=lookup)
    findings2 = evaluate(model2, load_bundled_packs())
    assert {f.obligation_id for f in findings2} == {"lic-gpl-incompat"}

    # 4. Drift vs baseline: the NOTICE finding is now resolved.
    delta = compute_drift(findings2, load_baseline(str(base_path)))
    assert [f.obligation_id for f in delta["resolved"]] == ["lic-apache-notice"]
    assert delta["new"] == []

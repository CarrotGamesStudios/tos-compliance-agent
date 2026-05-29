from __future__ import annotations

from pathlib import Path

from .models import Baseline, Finding


def finding_key(f: Finding) -> str:
    """Aggregate identity of a finding (obligation + its full evidence set)."""
    snippets = "|".join(sorted(e.snippet for e in f.evidence))
    return f"{f.obligation_id}::{snippets}"


def _evidence_keys(f: Finding) -> set[str]:
    """One key per evidence row (so per-dependency changes are tracked individually).

    Empty-evidence findings (e.g. needs_review) get a single status-qualified key so they
    don't all collide on `obligation_id::`.
    """
    if not f.evidence:
        return {f"{f.obligation_id}::{f.status}::"}
    return {f"{f.obligation_id}::{e.snippet}" for e in f.evidence}


def compute_drift(
    current: list[Finding], baseline: Baseline | None
) -> dict[str, list[Finding]]:
    """Compute drift at evidence granularity.

    A current finding is *new* if it introduces any evidence not in the baseline. A baseline
    finding is *resolved* only when ALL of its evidence has disappeared — so adding a second
    offending dependency reports the growing violation as new without falsely marking the
    original as resolved.
    """
    base_findings = baseline.findings if baseline else []
    base_keys = {k for f in base_findings for k in _evidence_keys(f)}
    cur_keys = {k for f in current for k in _evidence_keys(f)}
    new = [f for f in current if _evidence_keys(f) - base_keys]
    resolved = [f for f in base_findings if not (_evidence_keys(f) & cur_keys)]
    return {"new": new, "resolved": resolved}


def save_baseline(path: str, baseline: Baseline) -> None:
    Path(path).write_text(baseline.model_dump_json(indent=2), encoding="utf-8")


def load_baseline(path: str) -> Baseline | None:
    p = Path(path)
    if not p.is_file():
        return None
    return Baseline.model_validate_json(p.read_text(encoding="utf-8"))

from __future__ import annotations

from pathlib import Path

from .models import Finding, ProjectModel
from .notices import attributed_names
from .safety import ensure_within

_DEFAULT_ATTRIBUTION = {"Apache-2.0"}
_NOTICE_HEADER = ["NOTICE", "", "This product includes third-party software:"]


def _attribution_licenses(finding: Finding) -> set[str]:
    params = finding.remediation.get("params") or {}
    licenses = params.get("attribution_licenses")
    return set(licenses) if licenses else set(_DEFAULT_ATTRIBUTION)


def generate_notice_content(model: ProjectModel, finding: Finding) -> str:
    """Produce NOTICE content that PRESERVES any existing file and appends only missing entries.

    Never clobbers custom attributions/copyrights already present in the project's NOTICE.
    """
    attrib = _attribution_licenses(finding)
    deps = sorted(
        (d for d in model.dependencies if d.license in attrib), key=lambda d: d.name
    )
    existing = model.notice_text or ""
    already = attributed_names(existing)
    if existing.strip():
        lines = [existing.rstrip("\n")]
    else:
        lines = list(_NOTICE_HEADER)
    for d in deps:
        if d.name not in already:  # only add entries not already attributed
            lines.append(f"- {d.name} ({d.license})")
    return "\n".join(lines) + "\n"


def apply_fix(model: ProjectModel, finding: Finding) -> str:
    """Apply an AUTO fix. Deterministic auto-fixes only; manual findings are refused."""
    if finding.remediation.get("kind") != "auto":
        raise ValueError("apply_fix only handles deterministic auto fixes")
    codemod = finding.remediation.get("codemod")
    if codemod == "add_notice_entries":
        root = Path(model.root)
        target = ensure_within(root, root / "NOTICE")  # refuse symlink/`..` escape
        content = generate_notice_content(model, finding)
        target.write_text(content, encoding="utf-8")
        return str(target)
    raise ValueError(f"unknown codemod: {codemod}")

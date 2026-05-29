from __future__ import annotations

import json

from .models import Finding, ProjectModel


def _summary(findings: list[Finding]) -> dict[str, int]:
    return {
        "violations": sum(1 for f in findings if f.status == "violation"),
        "needs_review": sum(1 for f in findings if f.status == "needs_review"),
    }


def to_json(findings: list[Finding], model: ProjectModel | None = None) -> str:
    payload = {
        "summary": _summary(findings),
        "findings": [f.model_dump() for f in findings],
        "unscanned": model.unscanned if model else [],
    }
    return json.dumps(payload, indent=2)


def to_markdown(findings: list[Finding], unscanned: list[dict] | None = None) -> str:
    unscanned = unscanned or []
    if not findings and not unscanned:
        return "# Compliance Report\n\nNo compliance findings. ✅\n"
    lines = [
        "# Compliance Report",
        "",
        f"**{_summary(findings)['violations']} violation(s)**",
        "",
    ]
    for f in findings:
        lines += [
            f"## [{f.severity.upper()}] {f.obligation_id} ({f.status})",
            f"- **Requirement source:** {f.citation['url_or_section']}",
            f"- **Clause:** {f.citation['clause_quote']}",
            f"- **Fix:** {f.remediation['kind']} — {f.remediation.get('guidance', '')}",
            "- **Evidence:**",
        ]
        lines += [f"  - `{e.file}`: {e.snippet}" for e in f.evidence]
        lines.append("")
    if unscanned:
        lines += ["## Unscanned (not evaluated)"]
        lines += [f"- `{u['file']}`: {u.get('reason', '')}" for u in unscanned]
        lines.append("")
    return "\n".join(lines)

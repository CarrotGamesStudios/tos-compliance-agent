from __future__ import annotations

from .analyzers import ANALYZERS
from .models import Finding, Obligation, PolicyPack, ProjectModel
from .predicates import evaluate_predicate


def _finding_from(obligation: Obligation, evidence) -> Finding:
    if obligation.fix.kind == "auto":
        remediation = {
            "kind": "auto",
            "codemod": obligation.fix.codemod,
            "guidance": obligation.fix.guidance,
            # Carry the check params so codemods stay pack-driven (no hardcoded license sets).
            "params": obligation.check.params,
        }
    else:
        remediation = {"kind": "manual", "guidance": obligation.fix.guidance}
    return Finding(
        obligation_id=obligation.id,
        domain=obligation.domain,
        severity=obligation.severity,
        status="violation",
        evidence=evidence,
        citation={
            "clause_quote": obligation.source.clause_quote,
            "url_or_section": obligation.source.url_or_section,
        },
        remediation=remediation,
        confidence=1.0,
    )


def evaluate(model: ProjectModel, packs: list[PolicyPack]) -> list[Finding]:
    findings: list[Finding] = []
    for pack in packs:
        for obligation in pack.obligations:
            if not evaluate_predicate(obligation.applies_when, model):
                continue
            if obligation.check.kind != "deterministic":
                # Tier-0 has no LLM: surface judgment obligations for human review.
                findings.append(
                    Finding(
                        obligation_id=obligation.id,
                        domain=obligation.domain,
                        severity=obligation.severity,
                        status="needs_review",
                        evidence=[],
                        citation={
                            "clause_quote": obligation.source.clause_quote,
                            "url_or_section": obligation.source.url_or_section,
                        },
                        remediation={"kind": "manual", "guidance": obligation.fix.guidance},
                        confidence=0.0,
                    )
                )
                continue
            analyzer = ANALYZERS.get(obligation.check.analyzer or "")
            if analyzer is None:
                raise ValueError(f"unknown analyzer: {obligation.check.analyzer}")
            evidence = analyzer(obligation, model)
            if evidence:
                findings.append(_finding_from(obligation, evidence))
    return findings

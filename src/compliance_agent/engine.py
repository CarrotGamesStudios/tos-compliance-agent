from __future__ import annotations

from .analyzers import ANALYZERS
from .models import Evidence, Finding, Obligation, PolicyPack, ProjectModel
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


def _needs_review(obligation: Obligation, evidence=None) -> Finding:
    return Finding(
        obligation_id=obligation.id,
        domain=obligation.domain,
        severity=obligation.severity,
        status="needs_review",
        evidence=evidence or [],
        citation={
            "clause_quote": obligation.source.clause_quote,
            "url_or_section": obligation.source.url_or_section,
        },
        remediation={"kind": "manual", "guidance": obligation.fix.guidance},
        confidence=0.0,
    )


def _judged_finding(obligation: Obligation, verdict) -> Finding:
    from .judge import JUDGE_THRESHOLD

    status = "violation" if (verdict.violation and verdict.confidence >= JUDGE_THRESHOLD) else (
        "needs_review"
    )
    return Finding(
        obligation_id=obligation.id,
        domain=obligation.domain,
        severity=obligation.severity,
        status=status,
        evidence=[Evidence(file="(judgment)", line=None, snippet=verdict.rationale)],
        citation={
            "clause_quote": obligation.source.clause_quote,
            "url_or_section": obligation.source.url_or_section,
        },
        remediation={"kind": "manual", "guidance": obligation.fix.guidance},
        confidence=verdict.confidence,
    )


def evaluate(model: ProjectModel, packs: list[PolicyPack], judge=None) -> list[Finding]:
    """Evaluate every applicable obligation.

    Deterministic checks run their analyzer. Judgment checks: if a `judge` is supplied (Gemini in
    Tier-1) the LLM verdict decides violation vs needs_review; without a judge (Tier-0) they
    surface as needs_review so they are never silently passed.
    """
    findings: list[Finding] = []
    for pack in packs:
        for obligation in pack.obligations:
            if not evaluate_predicate(obligation.applies_when, model):
                continue
            if obligation.check.kind != "deterministic":
                if judge is None:
                    # No LLM (Tier-0): surface for human review, never silently pass.
                    findings.append(_needs_review(obligation))
                else:
                    try:
                        verdict = judge.judge(obligation, model)
                    except Exception:
                        # A judge/model failure must not crash the whole scan — degrade to
                        # needs_review so the obligation is still surfaced for a human.
                        findings.append(_needs_review(obligation))
                        continue
                    # The judge cleared it -> no finding; otherwise violation (confident) or
                    # needs_review (uncertain), decided by _judged_finding.
                    if verdict.violation:
                        findings.append(_judged_finding(obligation, verdict))
                continue
            analyzer = ANALYZERS.get(obligation.check.analyzer or "")
            if analyzer is None:
                raise ValueError(f"unknown analyzer: {obligation.check.analyzer}")
            evidence = analyzer(obligation, model)
            if evidence:
                findings.append(_finding_from(obligation, evidence))
    return findings

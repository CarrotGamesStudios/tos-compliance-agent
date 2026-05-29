from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Provenance = Literal["public", "internal"]
Domain = Literal[
    "license", "ai_aup", "privacy", "api_tos", "internal_policy", "contract"
]
Severity = Literal["low", "medium", "high", "critical"]


class Source(BaseModel):
    doc: str
    provenance: Provenance
    version: str
    clause_quote: str
    url_or_section: str


class Check(BaseModel):
    kind: Literal["deterministic", "judgment"]
    analyzer: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    prompt_template: str | None = None


class Fix(BaseModel):
    kind: Literal["auto", "manual"]
    codemod: str | None = None
    guidance: str | None = None


class Obligation(BaseModel):
    id: str
    domain: Domain
    source: Source
    applies_when: dict[str, Any]
    requirement: str
    check: Check
    severity: Severity
    fix: Fix


class PolicyPack(BaseModel):
    id: str
    domain: Domain
    provenance: Provenance
    source_doc: str
    source_version: str
    compiled_at: str
    obligations: list[Obligation]


class Dependency(BaseModel):
    name: str
    version: str | None = None
    license: str = "UNKNOWN"
    transitive: bool = False


class ProjectModel(BaseModel):
    hash: str
    root: str
    project_license: str | None = None
    dependencies: list[Dependency] = Field(default_factory=list)
    notice_file_present: bool = False
    notice_text: str | None = None
    # Code-level facts (populated by the scanners; used by privacy/ai_aup/api_tos).
    pii_log_sites: list[Evidence] = Field(default_factory=list)
    imports: list[str] = Field(default_factory=list)
    # Third-party platform APIs detected by host pattern in source (youtube, tiktok, meta, ...).
    platform_apis: list[str] = Field(default_factory=list)
    unscanned: list[dict[str, str]] = Field(default_factory=list)


class Evidence(BaseModel):
    file: str
    line: int | None = None
    snippet: str = ""


class Finding(BaseModel):
    obligation_id: str
    domain: Domain
    severity: Severity
    status: Literal["violation", "needs_review", "fixed"]
    evidence: list[Evidence] = Field(default_factory=list)
    citation: dict[str, str]
    remediation: dict[str, Any]
    confidence: float


class Baseline(BaseModel):
    project_model_hash: str
    policy_pack_versions: dict[str, str] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)


# ProjectModel.pii_log_sites is typed list[Evidence], but Evidence is declared further down in
# this module. Rebuild ProjectModel now that Evidence exists in the namespace so the forward
# reference resolves.
ProjectModel.model_rebuild()

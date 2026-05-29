from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ..models import Check, Domain, Fix, Severity


class CompiledSource(BaseModel):
    """The citation fields the LLM is responsible for (provenance/version are set by us)."""

    clause_quote: str
    url_or_section: str


class CompiledObligation(BaseModel):
    """One obligation as produced by the compiler LLM (before we stamp source provenance)."""

    id: str
    domain: Domain
    source: CompiledSource
    applies_when: dict[str, Any]
    requirement: str
    check: Check
    severity: Severity
    fix: Fix


class CompilerOutput(BaseModel):
    """Top-level structured response the compiler model must return."""

    obligations: list[CompiledObligation] = Field(default_factory=list)

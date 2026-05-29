from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Protocol

from pydantic import BaseModel

from ..config import DEFAULT_MODEL
from ..models import Obligation, PolicyPack, Provenance, Source
from ..predicates import validate_predicate
from .prompts import build_compile_prompt
from .schema import CompilerOutput


class ModelClient(Protocol):
    """Minimal structured-generation interface (real impl: GenaiModelClient; fakes in tests)."""

    def generate_structured(
        self, *, prompt: str, schema: type[BaseModel], model: str
    ) -> BaseModel: ...


# Verification thresholds — tuned to accept genuine elided quotes while rejecting "stitched"
# clauses assembled from short tokens scattered across the document.
_MIN_FRAGMENT_CHARS = 12  # each elided fragment must be at least this long (normalized)
_MAX_FRAGMENTS = 4  # a real quote elides a few times, not many
# Max source chars an "..." may bridge. Generous enough for real legal elisions (long
# parentheticals/lists in ToS & licenses) while still rejecting stitching across a whole document.
_MAX_GAP_PER_ELISION = 600

# Matches an ASCII ellipsis (3+ dots) OR a Unicode horizontal ellipsis.
_ELLIPSIS_RE = re.compile(r"\s*(?:\.{3,}|…)\s*")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def clause_in_source(quote: str, source: str) -> bool:
    """True iff `quote` is genuinely present in `source` (not stitched from scattered tokens).

    The trust gate for compiled obligations: whitespace-normalized, case-insensitive. A quote may
    elide with "..." / "…", but each retained fragment must be reasonably long, there may only be
    a few fragments, they must appear in order, and the whole matched region must stay within a
    bounded window — so an LLM cannot assemble a misleading "clause" from distant fragments.
    """
    src = _norm(source)
    fragments = [_norm(f) for f in _ELLIPSIS_RE.split(quote) if f.strip()]
    fragments = [f for f in fragments if f]
    if not fragments or len(fragments) > _MAX_FRAGMENTS:
        return False
    # When elided, every fragment must be substantial (blocks tiny-token stitching).
    if len(fragments) > 1 and any(len(f) < _MIN_FRAGMENT_CHARS for f in fragments):
        return False
    joined_len = sum(len(f) for f in fragments)
    # Even a single non-elided quote must carry real content (no 1-3 char "clauses").
    if joined_len < _MIN_FRAGMENT_CHARS:
        return False

    allowed_span = joined_len + _MAX_GAP_PER_ELISION * (len(fragments) - 1)
    first = fragments[0]
    # Anchor on each occurrence of the first fragment, then match the rest in order. Trying every
    # anchor (not just the earliest) means a valid tightly-matched occurrence later in the document
    # is found even when the first fragment also appears earlier (avoids greedy false negatives).
    anchor = src.find(first)
    while anchor != -1:
        pos = anchor + len(first)
        last_end = pos
        ok = True
        for needle in fragments[1:]:
            idx = src.find(needle, pos)
            if idx == -1:
                ok = False
                break
            last_end = idx + len(needle)
            pos = last_end
        if ok and (last_end - anchor) <= allowed_span:
            return True
        anchor = src.find(first, anchor + 1)
    return False


def doc_version(doc_text: str) -> str:
    return hashlib.sha256(doc_text.encode("utf-8")).hexdigest()[:16]


def compile_document(
    *,
    doc_text: str,
    doc_id: str,
    domain: str,
    model_client: ModelClient,
    url_base: str = "",
    model: str = DEFAULT_MODEL,
    provenance: Provenance = "public",
    compiled_at: str | None = None,
) -> tuple[PolicyPack, list[dict[str, str]]]:
    """Compile a source document into a versioned PolicyPack.

    Returns (pack, dropped) where `dropped` lists obligations rejected by validation or clause
    verification — surfaced, never silently swallowed.
    """
    version = doc_version(doc_text)
    prompt = build_compile_prompt(doc_text, domain, doc_id, url_base)
    out = model_client.generate_structured(prompt=prompt, schema=CompilerOutput, model=model)
    if not isinstance(out, CompilerOutput):
        out = CompilerOutput.model_validate(out)

    obligations: list[Obligation] = []
    dropped: list[dict[str, str]] = []
    for co in out.obligations:
        try:
            validate_predicate(co.applies_when)
        except ValueError as exc:
            dropped.append({"id": co.id, "reason": f"invalid applies_when: {exc}"})
            continue
        if not clause_in_source(co.source.clause_quote, doc_text):
            dropped.append({"id": co.id, "reason": "clause_quote not found in source document"})
            continue
        obligations.append(
            Obligation(
                id=co.id,
                domain=co.domain,
                source=Source(
                    doc=doc_id,
                    provenance=provenance,
                    version=version,
                    clause_quote=co.source.clause_quote,
                    url_or_section=co.source.url_or_section,
                ),
                applies_when=co.applies_when,
                requirement=co.requirement,
                check=co.check,
                severity=co.severity,
                fix=co.fix,
            )
        )

    pack = PolicyPack(
        id=doc_id,
        domain=domain,  # type: ignore[arg-type]
        provenance=provenance,
        source_doc=doc_id,
        source_version=version,
        compiled_at=compiled_at or date.today().isoformat(),
        obligations=obligations,
    )
    return pack, dropped

from __future__ import annotations

# The predicate DSL the compiler is allowed to emit (must match predicates.validate_predicate).
_PREDICATE_DSL = """
applies_when is a single-key JSON object using ONLY these operators:
  {"all": [<predicate>, ...]}          # every sub-predicate true (non-empty list)
  {"any": [<predicate>, ...]}          # at least one true (non-empty list)
  {"not": <predicate>}                 # negation
  {"has_dep_license": "<SPDX-id>"}     # a dependency has exactly this license
  {"dep_license_in": ["<SPDX-id>", ...]}   # any dependency license is in this list
  {"project_license_in": ["<SPDX-id>", ...]}  # the project's own license is in this list
  {"notice_file_present": true|false}  # whether a NOTICE file exists
  {"has_pii_in_logs": true|false}      # PII-named fields written to logs were detected
  {"uses_import": "<module>"}          # the project imports this module/package
  {"uses_import_in": ["<module>", ...]}    # the project imports any of these
  {"uses_platform_api": "<platform>"}  # uses this platform's API
       # platform is one of: youtube|tiktok|meta|linkedin|x|threads
  {"uses_platform_api_in": ["<platform>", ...]}
Use canonical SPDX ids (e.g. "GPL-3.0", "AGPL-3.0", "Apache-2.0", "MIT", "BSD-3-Clause").
"""

_ANALYZERS = """
check.kind is "deterministic" with check.analyzer one of:
  "gpl_incompatibility"  params: {"incompatible_licenses": ["GPL-3.0","AGPL-3.0"]}
  "missing_notice"       params: {"attribution_licenses": ["Apache-2.0"]}
  "pii_in_logs"          params: {}   (flags PII-named fields written to logs)
Use check.kind "judgment" (with a short prompt_template) for obligations that need reasoning over
the project facts (no deterministic analyzer fits).
"""


def build_compile_prompt(doc_text: str, domain: str, doc_id: str, url_base: str) -> str:
    return f"""You are a compliance-rules compiler. Read the source document below and extract a set
of machine-checkable obligations for the "{domain}" domain.

CRITICAL RULES:
- Every obligation's source.clause_quote MUST be copied VERBATIM from the document text below
  (you may elide with " ... " but each retained fragment must appear exactly in the document).
  Do NOT paraphrase, summarize, or invent clause text — quotes are verified against the source and
  any obligation whose quote is not found will be discarded.
- source.url_or_section should cite where in the document the clause appears (section/heading),
  prefixed by "{url_base}" when a URL is appropriate.
- Prefer deterministic checks; only use judgment checks when unavoidable.
- Keep obligation ids short, kebab-case, and unique within this document (e.g. "{doc_id}-1").

{_PREDICATE_DSL}
{_ANALYZERS}

Return JSON matching the provided schema (an object with an "obligations" array). If the document
contains no checkable obligations for this domain, return an empty array.

=== SOURCE DOCUMENT ({doc_id}) ===
{doc_text}
=== END SOURCE DOCUMENT ===
"""

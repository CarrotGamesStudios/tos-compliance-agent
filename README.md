# ToS / Compliance Agent

An open-source, **self-installable** compliance-drift agent for developers, built on Google's agent
stack (Vertex AI Agent Engine, ADK, Gemini 3.1, Vertex AI RAG Engine). It watches a project, detects
when it **drifts out of compliance**, and either **auto-fixes the violation in place** or **flags
exactly what a human must fix** — always with a citation to the source clause.

> **Single-tenant by design.** This is not a hosted service. You install it into **your own** Google
> Cloud project, running on **your own** infrastructure and credentials. Confidential internal docs
> and B2B contracts never leave your project. A fully **local mode** (CLI + MCP) also runs with no
> GCP project at all.

## What it checks

Compliance obligations are extracted from natural-language documents — **public** (third-party API
ToS, GDPR/CCPA, OSS licenses, AI model acceptable-use policies) **and internal/B2B** (your own
"DNA"/data-classification policies, MSAs, DPAs, SOWs) — compiled into versioned, checkable Policy
Packs, then matched against facts about your code.

Domains: `license` · `ai_aup` · `privacy` · `api_tos` · `internal_policy` · `contract`.

## Architecture (hybrid)

A **deterministic backbone** (SBOM, AST, PII/region scanners) for mechanical high-confidence checks,
**plus agentic Gemini 3.1 Pro reasoning** for genuine judgment calls. Drift is detected on two axes:
your code changing, *and* the upstream source document itself changing. Silent auto-fixes are
reserved for deterministic findings; LLM-proposed fixes always surface for human review.

## Delivery surfaces

- **Always-on hosted agent** on Vertex AI Agent Engine (in your project), with scheduled
  upstream-drift re-checks and auto-fix PRs.
- **MCP server** so AI coding assistants (Claude Code, Cursor, Gemini CLI) can call it inline.
- **Local CLI** (`compliance-agent scan|fix`) for fast, cloud-optional use.

## Status

Early development. See the design spec and phased implementation plans:

- Design spec: [`docs/superpowers/specs/2026-05-28-tos-compliance-agent-design.md`](docs/superpowers/specs/2026-05-28-tos-compliance-agent-design.md)
- Plan 1 (Tier-0 skeleton — OSS license × Python): [`docs/superpowers/plans/2026-05-28-tier0-license-python-skeleton.md`](docs/superpowers/plans/2026-05-28-tier0-license-python-skeleton.md)

## License

[Apache-2.0](LICENSE).

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

## Quickstart (Tier-0, local — no Google Cloud needed)

```bash
pip install -e ".[dev]"            # Python 3.11+

compliance-agent scan  /path/to/python-project     # report license findings (cited)
compliance-agent fix   /path/to/python-project --apply   # auto-fix (e.g. generate NOTICE)

# MCP server for AI coding assistants (Claude Code / Cursor / Gemini CLI):
python -m compliance_agent.mcp_server              # stdio; tools: scan_project, explain_obligation,
                                                   # list_policy_packs, apply_fix
```

What Tier-0 checks today: **GPL/AGPL incompatibility** (flagged, cited to GPL-3.0 §5-6) and
**missing Apache-2.0 NOTICE attributions** (auto-fixed). Every finding cites the exact source
clause; auto-fix is reserved for deterministic findings and never runs without `--apply`.

## Tier-1 (self-hosted on your own GCP project)

Adds a Gemini-backed **compiler** (source docs → versioned Policy Packs with mandatory clause
verification), **upstream-drift** detection (`refresh` recompiles only changed docs), an **ADK
agent** for Vertex AI Agent Engine, and a Terraform module + Dockerfile. See
[`deploy/README.md`](deploy/README.md):

```bash
pip install "compliance-agent[gcp]"
compliance-agent init --project YOUR_PROJECT --bucket YOUR_BUCKET --apply   # provision (Terraform)
compliance-agent refresh --gcs-bucket YOUR_BUCKET --packs ./packs --project YOUR_PROJECT
```

`examples/sources/` contains a runnable `sources.json` + sample docs to try `refresh` against.

## Status

Implemented and tested (150+ tests, ruff-clean, dual external review gates):

- **Tier-0** — local CLI + MCP server.
- **Tier-1** — Gemini compiler, upstream-drift `refresh`, ADK agent, Terraform + Dockerfile deploy.
- **Domains** — `license` (deterministic), `privacy` (PII-in-logs deterministic + GDPR judgment),
  `ai_aup` and `api_tos` (judgment via the Gemini judge), plus `internal_policy` / `contract` for
  your own policies and B2B contracts (PDF ingestion supported).
- **Ecosystems** — Python (pyproject + installed-dist metadata) and **Node/TS** (package.json +
  node_modules licenses + JS/TS PII-in-logs). The scanner auto-detects which.

CI runs lint + tests + a self-scan on every push (`.github/workflows/ci.yml`).

- Design spec: [`docs/superpowers/specs/2026-05-28-tos-compliance-agent-design.md`](docs/superpowers/specs/2026-05-28-tos-compliance-agent-design.md)
- Tier-0 plan: [`docs/superpowers/plans/2026-05-28-tier0-license-python-skeleton.md`](docs/superpowers/plans/2026-05-28-tier0-license-python-skeleton.md)

## License

[Apache-2.0](LICENSE).

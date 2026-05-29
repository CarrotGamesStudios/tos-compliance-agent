# ToS / Compliance Agent — Design Spec

**Date:** 2026-05-28
**Status:** Approved design (pre-implementation)
**Working name:** ToS / Compliance Agent (rename TBD — candidates: *Aegis*, *Conformal*, *Clause*)

---

## 1. Summary

A **developer-facing compliance agent** that watches a software project, detects when it
**drifts out of compliance**, and either **auto-fixes the violation in place** or **flags exactly
what a human must fix** — always with a citation to the source clause.

It is built on Google's agent stack:

- **Vertex AI Agent Engine** — managed always-on runtime (the hosted "brain").
- **Google ADK (Agent Development Kit, v1.0.0+ Python)** — the agent + tool framework; one
  codebase serves Agent Engine *and* an MCP server (ADK exposes tools over MCP via FastMCP).
- **Gemini 3.1 Pro** (`gemini-3.1-pro-preview`) for reasoning/compilation/judgment; **Gemini 2.5
  Flash** (`gemini-2.5-flash`) for cheap high-throughput sub-tasks.
- **Vertex AI RAG Engine** — managed corpus holding the source documents; GCS as source-of-truth,
  `text-embedding-005`.

**Source documents are public *and* internal/B2B.** Obligations are compiled from two provenances:
- **Public** — ToS, regulation texts (GDPR/CCPA…), OSS license texts, model acceptable-use policies.
- **Internal / proprietary** — a company's own internal standards and "DNA" docs (data-classification
  policy, security baselines, engineering rules) **and** B2B agreements (MSAs, DPAs, SOWs) that carry
  customer-specific obligations (data residency, deletion SLAs, subprocessor limits, security commitments).

Because the agent is **single-tenant and self-hosted in the user's own GCP project** (§1, §8),
confidential internal docs and signed contracts are ingested into *their* RAG corpus and **never
leave their infrastructure** — which is precisely why this deployment model matters.

**Project meta:** standalone, **open-source** (Apache-2.0), free — built for a **Google hackathon**.

**Tenancy: single-tenant, self-installable.** This is *not* a hosted service. Each user installs it
into **their own Google Cloud project**, running on **their own infrastructure and credentials**.
No shared backend, no central database, no multi-tenancy — the author's infrastructure is never
used by anyone else. "Anyone can install it in their own Google Cloud to use internally." A fully
**local mode** (CLI/MCP) additionally runs with *no* GCP project at all for the deterministic path
(see §8).

### Delivery surfaces (chosen)

1. **Always-on hosted agent** on Vertex AI Agent Engine — re-checks projects when the underlying
   source documents themselves change upstream, and opens auto-fix PRs.
2. **MCP server** — exposes the engine as tools so AI coding assistants (Claude Code, Cursor,
   Gemini CLI) can call it inline while the developer codes.
3. **Thin CLI** — `compliance-agent scan|check|fix` wrapping the same engine for fast,
   cloud-optional local demos.

### Architecture approach (chosen): **Hybrid (C)**

A **deterministic backbone** for mechanical, high-confidence checks, **plus agentic Gemini 3.1 Pro
reasoning** for genuine judgment calls. This delivers the "fix in place if possible, else highlight"
requirement directly, gives real drift detection on two axes, and showcases the fullest slice of
Google's stack without being vaporware.

---

## 2. Core abstraction — *obligations are data*

The whole system rests on one idea: **compliance obligations are buried in natural-language
documents; we extract them into checkable data, map them to facts about the project, and check.**

### 2.1 `Obligation`

One checkable rule, compiled from a single source clause.

```
Obligation:
  id: str
  domain: "license" | "ai_aup" | "privacy" | "api_tos"   # public-doc domains
        | "internal_policy"                              # company DNA / standards / data-classification
        | "contract"                                     # B2B MSA / DPA / SOW obligations
  source:
    doc: str                 # e.g. "stripe-tos", "acme-dpa-2026", "internal-data-policy"
    provenance: "public" | "internal"
    version: str             # content-hash / dated version of the doc
    clause_quote: str        # VERBATIM text from the doc (must exist in source — verified)
    url_or_section: str      # citation a human can open (URL for public; doc#section for internal)
  applies_when: Predicate     # over ProjectModel facts, e.g. depends_on("stripe")
  requirement: str            # what must hold (human-readable)
  check:
    kind: "deterministic"     # mechanical
      analyzer: str           #   which analyzer to dispatch to
      params: dict
    | kind: "judgment"        # LLM gray-area call
      prompt_template: str
  severity: "low" | "medium" | "high" | "critical"
  fix:
    kind: "auto"              # codemod / patch recipe
      codemod: str
    | kind: "manual"          # guidance text only
      guidance: str
```

**Invariant:** every `Obligation` carries a verbatim `clause_quote` + citation. This is what makes
findings trustworthy and auto-fixes auditable.

### 2.2 `PolicyPack`

A **versioned bundle** of obligations compiled from one source document (e.g. "Stripe ToS
2026-03", "GDPR", "MIT license", "Gemini AUP"). Version-pinned by **content hash of the source
doc**. This is the unit of *upstream* drift.

```
PolicyPack:
  id: str
  domain: str
  provenance: "public" | "internal"
  source_doc: str
  source_version: str        # content hash of the source document
  compiled_at: str
  obligations: list[Obligation]
```

Compiled **public** packs are **checked into the repo** under `packs/` (so the CLI/MCP work offline)
and also stored in GCS for the hosted agent. **Internal/B2B** packs are *never* committed to the
repo — they are compiled from the user's own docs and stored only in **their** GCS/corpus (Tier 1)
or a local `.compliance/packs/` ignored by git (Tier 0), keeping confidential obligations private.

### 2.3 `ProjectModel`

Deterministic **facts** about the scanned repo, produced by scanners (no LLM):

```
ProjectModel:
  hash: str                          # content hash of the relevant project inputs
  dependencies: [{name, version, license, transitive}]   # SBOM
  api_call_sites: [{provider, file, line, kind}]         # external API/SDK usage
  data_sinks: [{kind: log|db|network, file, line, target}]
  pii_fields: [{name, file, line, kind}]                 # PII-shaped data
  model_invocations: [{model, file, line, use_context}]  # AI model calls
  data_regions: [str]                                    # from config/env
  unscanned: [{file, reason}]                            # files that failed to parse
```

### 2.4 `Finding` and `Baseline`

```
Finding:
  obligation_id, domain, severity
  status: "violation" | "needs_review" | "fixed"
  evidence: [{file, line, snippet}]
  citation: {clause_quote, url_or_section}
  remediation: {kind: "auto"|"manual"|"llm_proposed", patch?|guidance}
  confidence: float           # 1.0 for deterministic; model confidence for judgment

Baseline:                      # last accepted state, per project
  project_model_hash: str
  policy_pack_versions: {pack_id: source_version}
  findings: [Finding]
```

---

## 3. Pipeline / data flow

```
 source docs ──▶ [RAG corpus] ──▶ [Compiler: Gemini 3.1] ──▶ PolicyPacks (versioned, validated)
                                                                      │
 repo ──▶ [Scanners (deterministic)] ──▶ ProjectModel ──────────────┤
                                                                      ▼
                                                          [Engine: match + evaluate]
                                          deterministic analyzers ─┤
                                          judgment calls (Gemini) ─┘
                                                                      ▼
                                                    Findings ──▶ [Remediation] ──▶ auto-PR / patch
                                                            └──▶ flagged + cited
                                                                      ▼
                                            [Drift] = Δ(Findings, PolicyPack versions) vs Baseline
```

1. **Ingest** — source docs → GCS → Vertex RAG corpus, from two provenances:
   - **Public**: ToS URLs, regulation texts, SPDX license texts, model AUPs.
   - **Internal/B2B**: the user points the corpus at their own sources — a **GCS folder**, a
     **Google Drive folder** (RAG Engine ingests both natively), or a **local directory** (Tier 0) —
     e.g. internal "DNA"/data-classification policies, MSAs, DPAs, SOWs. These are tagged
     `provenance: internal` and stay in the user's project.
2. **Compile** (LLM, offline / on upstream change) — Gemini 3.1 Pro reads each doc (grounded via
   RAG) → emits a `PolicyPack` of structured obligations → schema-validated + clause-verified →
   version-pinned, stored.
3. **Build ProjectModel** (deterministic scanners) — parse repo → facts.
4. **Match** — evaluate each obligation's `applies_when` against facts → applicable obligation set.
5. **Evaluate** —
   - deterministic checks → dispatch to analyzer → pass/fail with `file:line` evidence;
   - judgment checks → Gemini call with the clause + relevant code snippet → verdict + rationale +
     confidence.
6. **Drift** — compare current `{findings, pack versions, model hash}` against the stored
   `Baseline` (see §4).
7. **Remediate** — per the decision tree in §5.
8. **Report** — structured report (JSON + Markdown): findings, severities, citations, drift delta,
   `unscanned` list.

---

## 4. Drift model (two independent axes)

A `Baseline` is stored per project (Firestore for hosted, local file for CLI). **Drift = any delta
against it**, arising from two independent axes:

- **Project drift** — code changed. New scan → new `ProjectModel` → re-evaluate → findings not in
  baseline. *(e.g. a dev adds a `stripe` call that stores card data the ToS forbids.)*
- **Upstream drift** — the *document* changed. The always-on Agent Engine instance periodically
  re-fetches source docs into the RAG corpus; if a doc's content hash changes, the Compiler
  recompiles its `PolicyPack`, the version bumps, and every project pinned to that pack is
  re-evaluated. *(e.g. Stripe revises its ToS → unchanged code is now non-compliant.)*

Upstream drift — a violation appearing with **zero code change** — is precisely what justifies a
hosted, always-on agent rather than a one-shot CLI.

---

## 5. Remediation policy ("fix in place, else highlight")

```
finding
 ├─ check.kind == deterministic  AND  fix.kind == auto      → generate patch
 │      └─ confidence = 1.0 (mechanical)                       → auto-PR / apply via MCP
 ├─ check.kind == judgment  AND  Gemini confidence ≥ τ  AND  fix.kind == auto
 │      └─ generate patch, mark "LLM-proposed, review"       → DRAFT PR; never silent-apply
 └─ otherwise                                                → FLAG only:
        severity + verbatim source clause + file:line + manual guidance
```

**Safety line (hard rule):** silent auto-apply is reserved for **deterministic** fixes only.
LLM-proposed patches always surface for human review (draft PR, or MCP `suggest_fix` — never
`apply_fix` without explicit confirmation). Every finding — fixed or flagged — carries the verbatim
source clause + URL so a human can audit it.

### Worked example (license domain)

- **ProjectModel:** dep `somelib@2.0` is `GPL-3.0`; project's own license is `MIT`.
- **Obligation** (compiled from GPL-3.0 + MIT incompatibility): `applies_when:
  has_dep_license("GPL-3.0") AND project_license("MIT")`; deterministic; severity HIGH; fix MANUAL.
- **Finding:** flagged, cited to GPL-3.0 §5, guidance: "replace `somelib` or relicense; candidate
  MIT-compatible alternatives: …".
- **Contrast (auto-fixable):** missing `NOTICE`/attribution for an Apache-2.0 dep → deterministic +
  auto fix → patch adds the NOTICE entry → auto-PR.

---

## 6. Module structure

Each module has one clear job and is testable in isolation.

```
tos-compliance-agent/
├─ packs/                  # checked-in compiled PolicyPacks (JSON) + their source manifests
├─ src/compliance_agent/
│  ├─ models/              # Obligation, PolicyPack, ProjectModel, Finding, Baseline (pydantic)
│  ├─ corpus/              # RAG corpus mgmt: ingest docs→GCS→RAG, hash-watch upstream
│  ├─ compiler/            # doc → PolicyPack (Gemini 3.1, RAG-grounded); per-domain schema+prompt
│  ├─ scanners/            # deterministic ProjectModel builders, pluggable:
│  │     deps_sbom.py · api_calls.py · pii.py · config_regions.py · model_calls.py
│  ├─ engine/              # match(applies_when) + evaluate(deterministic | judgment) → Findings
│  ├─ analyzers/           # deterministic check implementations the engine dispatches to
│  ├─ remediation/         # patch/codemod generation + GitHub PR opener
│  ├─ drift/               # Baseline store + two-axis delta
│  ├─ report/              # render findings (json + markdown)
│  ├─ agent/               # ADK agent: tools, instructions, root_agent → Agent Engine
│  ├─ mcp/                 # MCP server exposing engine tools (FastMCP)
│  └─ cli.py               # thin CLI wrapper
├─ tests/                  # fixtures = tiny sample repos with planted violations
└─ deploy/                 # adk deploy config, Cloud Scheduler, Terraform (optional)
```

**One agent, three entry points.** The ADK `root_agent` in `agent/` is the single brain; `mcp/`
wraps the same tools as an MCP server; `deploy/` pushes it to Agent Engine; `cli.py` calls the
engine directly. No logic duplication.

---

## 7. MCP tool surface

Tools AI coding assistants (Claude Code / Cursor / Gemini CLI) call inline:

| tool | does |
|---|---|
| `scan_project(path)` | full ProjectModel build + evaluate → report |
| `check_change(diff)` | evaluate only what a diff touches — the inline "am I drifting?" check |
| `explain_obligation(id)` | returns the cited clause + rationale |
| `suggest_fix(finding_id)` | returns a patch (never applies) |
| `apply_fix(finding_id, confirm)` | applies a fix; deterministic auto, LLM-proposed needs `confirm` |
| `list_policy_packs()` | inspect loaded packs + versions |
| `refresh_corpus()` | re-pull source docs; recompile changed packs |

---

## 8. Installation, tenancy & deployment

**Single-tenant, self-installable** (see §1). Every user runs the agent in **their own** Google
Cloud project on **their own** credentials. There are two install tiers; the same package serves
both, so a user can start local and graduate to hosted without changing tools.

### Tier 0 — Local (no GCP project required)

For "local work" and quick adoption. The **CLI** and **MCP server** run on the developer's machine
against the **checked-in `packs/*.json`** (no RAG corpus, no GCS, no Firestore needed):

- **Baselines** stored in a local file (e.g. `.compliance/baseline.json` in the scanned repo).
- **Deterministic checks** (license SBOM, PII patterns, etc.) run fully offline — no model needed.
- **Judgment checks** need a Gemini model: the user supplies **their own** key — either a Google AI
  Studio `GEMINI_API_KEY` (zero GCP project) *or* Vertex via their own project (ADC). With no key,
  judgment obligations degrade to `needs_review` flags (never blocked, never silently skipped).
- **No upstream-drift watching** in this tier (that needs the hosted scheduler) — only project drift.

### Tier 1 — Self-hosted always-on (user's own GCP project)

The full showcase, provisioned **into the installer's own project**:

- `compliance-agent init --project <THEIR_PROJECT>` runs the **bootstrap**: enables required APIs,
  creates a **GCS** bucket (source docs + packs), a **Firestore** database (baselines/findings), a
  **Vertex AI RAG Engine** corpus, a least-privilege **service account**, then
  `adk deploy agent_engine` to **their** Agent Engine. Implemented as a **Terraform module** in
  `deploy/` with a one-command wrapper.
- A **Cloud Scheduler** job (in their project) triggers `corpus.refresh → recompile → re-evaluate`
  daily → upstream-drift detection + auto-PRs against their repos.
- All data (docs, packs, baselines, findings) lives in **their** project; nothing leaves it.

### Storage & fallback

- Findings/baselines: **Firestore** (Tier 1) or local file (Tier 0).
- Source docs + compiled packs: **GCS** (Tier 1); checked-in `packs/*.json` ship with the repo and
  are the **offline fallback** whenever GCP/RAG is unavailable in either tier.
- Retrieval (Tier 1): **Vertex AI RAG Engine** in the user's project.

### Distribution

- Published as a **PyPI package** (`pip install compliance-agent`) + the source repo. The Terraform
  module and an `init` command are the entire setup; no account with the author, no shared keys.

---

## 9. Scope & delivery sequencing

**Full target (per user):** all four public-doc domains (`license`, `ai_aup`, `privacy`, `api_tos`)
**plus** the two internal/B2B domains (`internal_policy`, `contract`) built end-to-end, sourcing
from **public + internal docs**, scanning **both Python and Node/TS** projects.

This is large for a hackathon. To make it tractable *without dropping anything*, build a **walking
skeleton first, then fan out** — every step leaves a working, demoable system, and later items
degrade gracefully to stub Policy Packs if time runs short (no architectural rebuild needed):

1. **Tier-0 skeleton** — full *local* pipeline on the narrowest slice: **OSS license × Python**,
   running as **CLI + MCP** against checked-in packs (most deterministic, fastest to a real fix,
   zero GCP needed). Proves scanner → engine → drift → remediation → MCP all connect, and is
   immediately installable by anyone (`pip install`).
2. **Tier-1 hosting** — add the cloud path on the *same* slice: bootstrap (`init` + Terraform) into
   the user's own project, RAG corpus + compiler, `adk deploy agent_engine`, Cloud Scheduler →
   upstream drift + auto-PR. Proves the full Google-stack story end-to-end.
3. **Fan out domains** — add **AI-AUP** (judgment-heavy → showcases Gemini reasoning), then
   **Privacy** (GDPR/CCPA), then **API-ToS**, each as Policy Packs + analyzers/judgment prompts.
   Additive; the engine does not change.
4. **Internal/B2B sourcing** — wire the internal-doc connectors (GCS / Drive / local dir) and the
   `internal_policy` + `contract` domains. Reuses the same compiler + engine; mostly judgment-based,
   with bespoke `applies_when` predicates (e.g. data-region, subprocessor). High-value differentiator
   enabled by the single-tenant model.
5. **Fan out ecosystem** — add **Node/TS** scanner adapters behind the same `ProjectModel`
   interface (deps + AST), so every existing domain check works on Node "for free."

**Domain pairing rationale:** License (deterministic) + AI-AUP (judgment) together demonstrate *both
halves* of the hybrid engine; Privacy and API-ToS broaden coverage and on-theme appeal.

---

## 10. Error handling (failure modes that matter)

- **LLM compiler produces malformed / hallucinated obligations** → every compiled `PolicyPack` is
  schema-validated (pydantic) and each obligation's `clause_quote` is **verified to actually appear
  in the source doc**; obligations failing verification are dropped + logged, never shipped.
- **Judgment call low-confidence / Gemini error** → never auto-fixes; degrades to a FLAG with the
  model's rationale + confidence, or `status: needs_review` on error.
- **Scanner can't parse a file** → recorded as `unscanned` in the report (visible, not silently
  skipped) — never a false "compliant."
- **Source doc fetch fails on refresh** → keep the last good pack, mark the corpus entry stale;
  never evaluate against an empty pack.
- **GCP / RAG / Firestore unavailable** → CLI/MCP fall back to checked-in `packs/*.json`.

---

## 11. Testing

- **Fixtures = tiny sample repos with deliberately planted violations** (a GPL dep in an MIT
  project, PII written to logs, a prohibited model use case) + matching clean repos → assert exact
  findings, citations, and that auto-fix patches actually resolve them.
- **Compiler** tested against **frozen source-doc snapshots** → deterministic expected packs
  (golden files).
- **Engine** `applies_when` matching + drift-delta unit-tested in isolation (no cloud).
- **End-to-end:** planted-violation repo → scan → fix → re-scan → clean.

---

## 12. Open questions (resolve during planning)

- Final product name.
- Node/TS AST tooling choice (e.g. `tree-sitter` vs `@typescript-eslint/typescript-estree` invoked
  via a sidecar) — Python scanners use the stdlib `ast` module + an SBOM lib.
- Patch/codemod mechanism per language (e.g. `libcst` for Python, `jscodeshift`/`ts-morph` for Node).
- Confidence threshold `τ` for LLM-proposed auto-fixes (start conservative; never silent).
- Source-doc set for the API-ToS corpus (which providers to seed: Stripe, Google Maps, etc.).
- Model-provider resolution order for judgment calls (AI Studio `GEMINI_API_KEY` vs Vertex ADC in
  the user's project) and how `init`/config surfaces the choice.
- Least-privilege IAM role set the Terraform module grants the agent's service account.
- Confirm the project's own OSS license is **Apache-2.0** (permissive, and clean for a tool that
  audits license compliance).
- Internal-doc connectors to ship first (GCS folder vs Google Drive folder vs local dir) and the
  config UX for registering them.
- Whether `internal_policy` and `contract` obligations need bespoke `applies_when` predicates (e.g.
  "data stored in region X", "uses subprocessor Y") beyond the public-domain predicate set.
- How internal/B2B `clause_quote` verification works when the source is a binary/PDF contract
  (extract text on ingest; verify the quote against extracted text).
```


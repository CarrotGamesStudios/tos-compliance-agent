# Deploying the ToS / Compliance Agent (Tier-1, self-hosted)

Tier-1 runs the agent **in your own Google Cloud project** on your own credentials. Nothing is
shared with anyone else. Tier-0 (local CLI + MCP) needs none of this — see the root README.

## 1. Provision infrastructure (your project)

```bash
pip install "compliance-agent[gcp]"
gcloud auth application-default login           # your credentials

# Writes deploy/terraform/terraform.tfvars and runs Terraform:
compliance-agent init \
  --project YOUR_PROJECT \
  --location us-central1 \
  --bucket YOUR_UNIQUE_BUCKET \
  --apply
```

This enables the required APIs and creates, **in your project**: a GCS bucket (source docs +
compiled packs, versioned), a Firestore database (baselines/findings), and a least-privilege
service account (`aiplatform.user`, `datastore.user`, bucket-scoped `storage.objectAdmin`).

## 2. Add source documents

Upload a `sources/sources.json` manifest + the referenced text files to your bucket (public ToS /
regulations / licenses / AUPs and/or internal "DNA" policies and B2B contracts). Internal docs stay
in your bucket and never leave your project.

## 3. Compile Policy Packs (and detect upstream drift)

```bash
compliance-agent refresh \
  --gcs-bucket YOUR_UNIQUE_BUCKET \
  --packs ./packs \
  --project YOUR_PROJECT
```

Only documents whose content changed are recompiled (content-hash versioning = upstream drift).
Run this on a schedule to catch upstream ToS/regulation changes with zero code change. The
Terraform enables the Cloud Scheduler API but does not create the job (it depends on your run
target); create one pointing at a Cloud Run **job** that runs `compliance-agent refresh`, e.g.:

```bash
gcloud scheduler jobs create http compliance-refresh \
  --schedule="0 6 * * *" --uri="https://<your-cloud-run-job-trigger>" \
  --oauth-service-account-email=compliance-agent@YOUR_PROJECT.iam.gserviceaccount.com
``` Every compiled obligation's clause is verified against the source text; unverifiable
obligations are dropped and reported.

**Enforcing your compiled packs.** `refresh` writes compiled packs to the `--packs` directory.
Scans enforce the built-in packs **plus** any packs found in `$COMPLIANCE_PACKS_DIR`:

```bash
export COMPLIANCE_PACKS_DIR=./packs   # the dir you passed to `refresh --packs`
compliance-agent scan /path/to/project   # now also enforces your compiled obligations
```

For a hosted deploy, make that directory available to the runtime — either bake it into the image
(`COPY packs /app/packs` + `ENV COMPLIANCE_PACKS_DIR=/app/packs`) or mount/sync it from your GCS
bucket at startup and point `COMPLIANCE_PACKS_DIR` at the mount. (The bucket is the source-of-truth
store; packs are produced from it by `refresh`.)

## 4. Deploy the agent

**Vertex AI Agent Engine** (managed runtime) — uses the ADK entrypoint `agent.agent.root_agent`:

```bash
adk deploy agent_engine \
  --project YOUR_PROJECT --region us-central1 \
  --display_name "compliance-agent" \
  src/compliance_agent/agent
```

**Or host the MCP server on Cloud Run** (HTTP transport):

```bash
gcloud run deploy compliance-agent \
  --source . --region us-central1 \
  --service-account compliance-agent@YOUR_PROJECT.iam.gserviceaccount.com \
  --no-allow-unauthenticated      # REQUIRED: the MCP tools scan paths and mutate files —
                                  # never expose this service publicly. Grant run.invoker
                                  # only to the identities/agents that should call it.
# (uses deploy/Dockerfile; serves FastMCP over HTTP on $PORT, as a non-root user)
```

> Security: the hosted MCP tools (`scan_project`, `apply_fix`) read arbitrary paths and write
> fixes. Keep the service authenticated (`--no-allow-unauthenticated`) and bind `roles/run.invoker`
> to specific callers only.

## Credentials for judgment checks

The compiler/agent call Gemini via Vertex in your project (ADC). For purely local use you can
instead set a `GEMINI_API_KEY` (AI Studio) — no GCP project required.

# Container image for hosting the compliance-agent MCP server over HTTP (Cloud Run / GKE).
# (Vertex AI Agent Engine deploys are done with `adk deploy agent_engine` and don't need this.)
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    COMPLIANCE_MCP_TRANSPORT=http \
    PORT=8080

WORKDIR /app

# Install the package with the GCP extra (Gemini / Vertex / GCS / Firestore).
# `packs/` is copied so the hatch force-include bakes the bundled (default) packs into the wheel.
COPY pyproject.toml README.md NOTICE LICENSE ./
COPY src ./src
COPY packs ./packs
RUN pip install ".[gcp]"

# To ALSO enforce your own compiled packs in this image, copy them in and point the runtime at
# them, e.g.:
#   COPY my-compiled-packs ./my-packs
#   ENV COMPLIANCE_PACKS_DIR=/app/my-packs
# (Default packs are always loaded; COMPLIANCE_PACKS_DIR adds/overrides on top.)

# Run as a non-root user (least privilege).
RUN useradd --create-home --uid 1001 appuser
USER appuser

EXPOSE 8080

# Runs FastMCP over HTTP on $PORT (see compliance_agent.mcp_server.run).
CMD ["python", "-m", "compliance_agent.mcp_server"]

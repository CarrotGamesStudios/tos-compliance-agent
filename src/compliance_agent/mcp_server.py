from __future__ import annotations

import json
from typing import Any

from fastmcp import FastMCP

from .engine import evaluate
from .errors import ProjectScanError
from .models import Finding
from .packs import load_active_packs
from .remediation import apply_fix as _apply_fix
from .report import to_json
from .scanners.licenses import build_project_model

mcp = FastMCP("compliance-agent")


# ── Internal implementations (accept dist_lookup for testing; NOT exposed in the tool schema) ──


def _scan(path: str, dist_lookup=None) -> dict[str, Any]:
    model = build_project_model(path, dist_lookup=dist_lookup)
    findings = evaluate(model, load_active_packs())
    return json.loads(to_json(findings, model))


def needs_confirmation(finding: Finding, confirm: bool) -> bool:
    """Safety line (spec §5): deterministic auto-fixes (confidence == 1.0) apply directly;
    LLM-proposed fixes (confidence < 1.0, arriving in later tiers) require explicit confirm."""
    return finding.confidence < 1.0 and not confirm


def _apply(
    path: str, obligation_id: str, confirm: bool = False, dist_lookup=None
) -> dict[str, Any]:
    model = build_project_model(path, dist_lookup=dist_lookup)
    findings = evaluate(model, load_active_packs())
    target = next((f for f in findings if f.obligation_id == obligation_id), None)
    if target is None:
        return {"error": f"no active finding for {obligation_id}"}
    if target.remediation.get("kind") != "auto":
        return {
            "error": "manual finding; not auto-applicable",
            "guidance": target.remediation.get("guidance"),
        }
    if needs_confirmation(target, confirm):
        return {
            "error": "confirmation required",
            "reason": "LLM-proposed fix; re-call with confirm=true to apply",
            "guidance": target.remediation.get("guidance"),
        }
    written = _apply_fix(model, target)
    return {"applied": True, "path": written}


# ── Public MCP tools (clean signatures: path / obligation_id / confirm only) ──


def scan_project(path: str) -> dict[str, Any]:
    """Scan a project directory and return a structured compliance report."""
    try:
        return _scan(path)
    except ProjectScanError as exc:
        return {"error": str(exc)}


def explain_obligation(obligation_id: str) -> dict[str, Any]:
    """Return the requirement text and verbatim source citation for an obligation."""
    for pack in load_active_packs():
        for ob in pack.obligations:
            if ob.id == obligation_id:
                return {
                    "requirement": ob.requirement,
                    "severity": ob.severity,
                    "citation": {
                        "clause_quote": ob.source.clause_quote,
                        "url_or_section": ob.source.url_or_section,
                    },
                }
    return {"error": f"unknown obligation: {obligation_id}"}


def list_policy_packs() -> list[dict[str, Any]]:
    """List loaded Policy Packs with their domain, provenance, and version."""
    return [
        {
            "id": p.id,
            "domain": p.domain,
            "provenance": p.provenance,
            "version": p.source_version,
            "obligations": len(p.obligations),
        }
        for p in load_active_packs()
    ]


def apply_fix(path: str, obligation_id: str, confirm: bool = False) -> dict[str, Any]:
    """Apply a deterministic auto-fix for one finding.

    Deterministic fixes apply directly; LLM-proposed fixes require confirm=True.
    """
    try:
        return _apply(path, obligation_id, confirm)
    except ProjectScanError as exc:
        return {"error": str(exc)}


# Register tools with FastMCP. The public tool callables are named exactly as the agent
# instruction references them (e.g. `apply_fix`) so ADK / MCP expose matching tool names.
mcp.tool()(scan_project)
mcp.tool()(explain_obligation)
mcp.tool()(list_policy_packs)
mcp.tool()(apply_fix)


def select_port(value: str | None, default: int = 8080) -> int:
    """Parse a PORT env value into a valid TCP port, falling back to `default`."""
    try:
        port = int(value) if value is not None else default
    except (TypeError, ValueError):
        return default
    return port if 0 < port <= 65535 else default


def run() -> None:
    """Start the MCP server. Transport is chosen by env for both local and hosted use:

    - COMPLIANCE_MCP_TRANSPORT=stdio (default): local use by coding assistants.
    - COMPLIANCE_MCP_TRANSPORT=http: hosted (Cloud Run); binds 0.0.0.0:$PORT (default 8080).
    """
    import os

    transport = os.getenv("COMPLIANCE_MCP_TRANSPORT", "stdio")
    if transport == "http":
        mcp.run(transport="http", host="0.0.0.0", port=select_port(os.getenv("PORT")))
    else:
        mcp.run()


if __name__ == "__main__":
    run()

from __future__ import annotations

from ..config import DEFAULT_MODEL
from ..mcp_server import (
    apply_fix,
    explain_obligation,
    list_policy_packs,
    scan_project,
)

AGENT_INSTRUCTION = """You are a software-compliance agent. You help developers keep a project
compliant with the obligations in the loaded Policy Packs (licenses, ToS, regulations, AI usage
policies, internal/B2B contracts).

Use the tools to do real work — never guess a verdict:
- `scan_project(path)`: build the report of violations for a project directory.
- `explain_obligation(obligation_id)`: quote the exact source clause behind a finding.
- `list_policy_packs()`: show which packs/versions are loaded.
- `apply_fix(path, obligation_id, confirm)`: apply a fix. Deterministic fixes apply directly;
  anything requiring confirmation must be confirmed by the user first.

Always cite the source clause for any finding. Never claim a project is compliant without having
run `scan_project`. Prefer flagging with guidance over applying a fix you are unsure about.
"""

def build_root_agent(model: str = DEFAULT_MODEL):
    """Construct the ADK root agent. Imports google-adk lazily (requires the [gcp] extra).

    Tools are passed as their public callables, whose __name__ matches the names the instruction
    tells the model to call (scan_project / explain_obligation / list_policy_packs / apply_fix).
    """
    from google.adk import Agent

    return Agent(
        name="compliance_agent",
        model=model,
        instruction=AGENT_INSTRUCTION,
        tools=[scan_project, explain_obligation, list_policy_packs, apply_fix],
    )

from __future__ import annotations

import os

# Single source of truth for the Gemini model used by the compiler and the hosted agent.
# Preview model ids change; override with COMPLIANCE_MODEL without touching code, and update this
# default in ONE place when the stable id changes.
DEFAULT_MODEL = os.getenv("COMPLIANCE_MODEL", "gemini-3.1-pro-preview")

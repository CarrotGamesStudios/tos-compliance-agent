"""ADK deploy entrypoint.

`adk deploy agent_engine` (and `adk run`) look for a module exposing `root_agent`. We build it
lazily via module `__getattr__` so merely importing this module never triggers the google-adk
import — only *accessing* `root_agent` does. That keeps Tier-0 fully GCP-free even if something
imports this submodule.
"""

from __future__ import annotations

from typing import Any

from .root import build_root_agent


def __getattr__(name: str) -> Any:
    if name == "root_agent":
        return build_root_agent()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

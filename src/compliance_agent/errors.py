from __future__ import annotations


class ProjectScanError(Exception):
    """Raised when a project cannot be scanned (missing/malformed inputs, unsafe path)."""

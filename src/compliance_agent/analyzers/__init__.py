from __future__ import annotations

from collections.abc import Callable

from ..models import Evidence, Obligation, ProjectModel
from .gpl_incompatibility import gpl_incompatibility
from .missing_notice import missing_notice
from .pii_in_logs import pii_in_logs

Analyzer = Callable[[Obligation, ProjectModel], list[Evidence]]

ANALYZERS: dict[str, Analyzer] = {
    "gpl_incompatibility": gpl_incompatibility,
    "missing_notice": missing_notice,
    "pii_in_logs": pii_in_logs,
}

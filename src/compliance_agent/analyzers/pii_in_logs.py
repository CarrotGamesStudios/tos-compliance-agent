from __future__ import annotations

from ..models import Evidence, Obligation, ProjectModel


def pii_in_logs(obligation: Obligation, model: ProjectModel) -> list[Evidence]:
    """Flag log/print calls that reference PII-named fields (one Evidence per site).

    The ProjectModel's AST scanner already located the sites; this analyzer simply surfaces them
    as findings for the privacy domain. Per-site Evidence keeps drift granular.
    """
    return list(model.pii_log_sites)

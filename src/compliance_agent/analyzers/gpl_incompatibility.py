from __future__ import annotations

from ..models import Evidence, Obligation, ProjectModel


def gpl_incompatibility(obligation: Obligation, model: ProjectModel) -> list[Evidence]:
    incompatible = set(obligation.check.params.get("incompatible_licenses", []))
    return [
        Evidence(file="pyproject.toml", line=None, snippet=f"{d.name} ({d.license})")
        for d in model.dependencies
        if d.license in incompatible
    ]

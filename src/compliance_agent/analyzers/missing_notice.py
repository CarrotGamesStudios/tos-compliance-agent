from __future__ import annotations

from ..models import Evidence, Obligation, ProjectModel
from ..notices import attributed_names


def missing_notice(obligation: Obligation, model: ProjectModel) -> list[Evidence]:
    """Flag attribution-bearing deps that are not yet listed in the project's NOTICE.

    Content-aware (not mere file presence): if a new Apache-2.0 dependency is added after a
    NOTICE already exists, it is still flagged until it appears as an attribution entry.
    """
    needs = set(obligation.check.params.get("attribution_licenses", []))
    offenders = [d.name for d in model.dependencies if d.license in needs]
    if not offenders:
        return []
    listed = attributed_names(model.notice_text)
    missing = sorted(name for name in offenders if name not in listed)
    # One Evidence per missing dependency so drift keys stay per-dependency stable
    # (adding a new offender must not flip the existing one to "resolved").
    return [
        Evidence(file="NOTICE", line=None, snippet=f"missing attribution for: {name}")
        for name in missing
    ]

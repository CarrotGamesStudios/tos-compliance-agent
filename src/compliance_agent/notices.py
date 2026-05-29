from __future__ import annotations

import re

# Match attribution entries of the form "- <name> (<license>)" — the format we generate.
_ENTRY_RE = re.compile(r"^\s*-\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*\(", re.MULTILINE)


def attributed_names(notice_text: str | None) -> set[str]:
    """Distribution names already listed as attribution entries in a NOTICE.

    Uses line-structured parsing (not a substring scan) so a dependency name that merely
    appears in prose/copyright text is not mistaken for an attribution entry.
    """
    if not notice_text:
        return set()
    return set(_ENTRY_RE.findall(notice_text))

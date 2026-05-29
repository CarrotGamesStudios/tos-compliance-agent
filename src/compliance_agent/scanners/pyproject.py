from __future__ import annotations

import re
import tomllib

# Trove-classifier -> SPDX map. Not exhaustive, but covers the licenses seen in the
# overwhelming majority of real Python projects (extended further in later plans).
_CLASSIFIER_TO_SPDX = {
    "License :: OSI Approved :: MIT License": "MIT",
    "License :: OSI Approved :: Apache Software License": "Apache-2.0",
    "License :: OSI Approved :: BSD License": "BSD-3-Clause",
    "License :: OSI Approved :: ISC License (ISCL)": "ISC",
    "License :: OSI Approved :: The Unlicense (Unlicense)": "Unlicense",
    "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
    "License :: OSI Approved :: GNU Lesser General Public License v2 (LGPLv2)": "LGPL-2.0",
    "License :: OSI Approved :: GNU Lesser General Public License v2 or later (LGPLv2+)": "LGPL-2.0",  # noqa: E501
    "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)": "LGPL-3.0",
    "License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)": "LGPL-3.0",  # noqa: E501
    "License :: OSI Approved :: GNU General Public License v2 (GPLv2)": "GPL-2.0",
    "License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)": "GPL-2.0",
    "License :: OSI Approved :: GNU General Public License v3 (GPLv3)": "GPL-3.0",
    "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)": "GPL-3.0",
    "License :: OSI Approved :: GNU Affero General Public License v3": "AGPL-3.0",
    "License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)": "AGPL-3.0",  # noqa: E501
    "License :: OSI Approved :: Eclipse Public License 2.0 (EPL-2.0)": "EPL-2.0",
    "License :: OSI Approved :: Python Software Foundation License": "PSF-2.0",
}

# Canonicalize common SPDX variants / informal spellings to the ids the packs match on.
_SPDX_NORMALIZE = {
    "GPL-3.0-only": "GPL-3.0",
    "GPL-3.0-or-later": "GPL-3.0",
    "GPLv3": "GPL-3.0",
    "GPL v3": "GPL-3.0",
    "GPL-2.0-only": "GPL-2.0",
    "GPL-2.0-or-later": "GPL-2.0",
    "AGPL-3.0-only": "AGPL-3.0",
    "AGPL-3.0-or-later": "AGPL-3.0",
    "LGPL-3.0-only": "LGPL-3.0",
    "LGPL-3.0-or-later": "LGPL-3.0",
    "Apache 2.0": "Apache-2.0",
    "Apache-2": "Apache-2.0",
    "Apache License 2.0": "Apache-2.0",
    "Apache Software License": "Apache-2.0",
    "BSD": "BSD-3-Clause",
    "BSD-3": "BSD-3-Clause",
    "BSD 3-Clause": "BSD-3-Clause",
    "The MIT License": "MIT",
    "MIT License": "MIT",
}

# PEP 508: a name is the leading run of letters/digits/._- before any specifier/extra/marker.
_NAME_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")


def normalize_license(value: str) -> str:
    """Canonicalize a license string to a known SPDX id where we recognize a variant."""
    text = value.strip()
    return _SPDX_NORMALIZE.get(text, text)


def parse_project_license(pyproject_text: str) -> str | None:
    data = tomllib.loads(pyproject_text)
    project = data.get("project", {})
    lic = project.get("license")
    if isinstance(lic, str) and lic.strip():
        return normalize_license(lic)
    if isinstance(lic, dict) and isinstance(lic.get("text"), str) and lic["text"].strip():
        return normalize_license(lic["text"])
    # PEP 621 `license = {file = "LICENSE"}` carries no inline id — fall through to classifiers
    # rather than guessing; absence resolves to None (and is reported as such, not a false pass).
    for classifier in project.get("classifiers", []):
        if classifier in _CLASSIFIER_TO_SPDX:
            return _CLASSIFIER_TO_SPDX[classifier]
    return None


def _names_from_specs(specs: list[str]) -> list[str]:
    names: list[str] = []
    for raw in specs:
        if not isinstance(raw, str):
            continue
        match = _NAME_RE.match(raw.strip())
        if match:
            names.append(match.group(1))
    return names


def parse_dependencies(pyproject_text: str, include_optional: bool = True) -> list[str]:
    """Distribution names from [project.dependencies] and (by default) optional-dependencies.

    Optional/extra groups are included because they ship in the project and carry the same
    license obligations; dedups while preserving first-seen order.
    """
    data = tomllib.loads(pyproject_text)
    project = data.get("project", {})
    names = list(_names_from_specs(project.get("dependencies", [])))
    if include_optional:
        optional = project.get("optional-dependencies", {})
        if isinstance(optional, dict):
            for specs in optional.values():
                if isinstance(specs, list):
                    names.extend(_names_from_specs(specs))
    seen: set[str] = set()
    deduped: list[str] = []
    for name in names:
        if name not in seen:
            seen.add(name)
            deduped.append(name)
    return deduped

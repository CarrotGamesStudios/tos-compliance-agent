from __future__ import annotations

import hashlib
import importlib.metadata
from pathlib import Path

from ..errors import ProjectScanError
from ..models import Dependency, ProjectModel
from ..safety import resolve_root
from .code_ast import scan_python_files
from .pyproject import (
    _CLASSIFIER_TO_SPDX,
    normalize_license,
    parse_dependencies,
    parse_project_license,
)

_NOTICE_FILES = ("NOTICE", "NOTICE.txt", "NOTICE.md")


def license_from_metadata(
    license_expression: str | None,
    classifiers: list[str],
    license_field: str | None,
) -> str:
    """Resolve an SPDX-ish license id from a distribution's metadata fields.

    Priority: License-Expression (PEP 639, already SPDX) > Trove classifier > License field.
    Only multi-line text (a full embedded license body) is rejected as UNKNOWN — single-line
    values, including SPDX expressions with spaces ("Apache-2.0 OR MIT") and informal names
    ("Apache 2.0"), are kept and normalized.
    """
    if license_expression and license_expression.strip():
        return normalize_license(license_expression)
    for classifier in classifiers:
        if classifier in _CLASSIFIER_TO_SPDX:
            return _CLASSIFIER_TO_SPDX[classifier]
    if license_field and license_field.strip():
        text = license_field.strip()
        # A real license id/expression is short and single-line; full license text is not.
        if len(text) <= 64 and "\n" not in text:
            return normalize_license(text)
    return "UNKNOWN"


class _ImportlibLookup:
    """Default lookup adapting importlib.metadata to (expr, classifiers, license_field)."""

    def get(self, name: str):
        try:
            meta = importlib.metadata.metadata(name)
        except importlib.metadata.PackageNotFoundError:
            return None
        return (
            meta.get("License-Expression"),
            meta.get_all("Classifier") or [],
            meta.get("License"),
        )


def _read_notice(root: Path) -> str | None:
    for fname in _NOTICE_FILES:
        candidate = root / fname
        if candidate.is_file():
            try:
                return candidate.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                return ""
    return None


def build_project_model(project_dir: str, dist_lookup=None) -> ProjectModel:
    lookup = dist_lookup if dist_lookup is not None else _ImportlibLookup()
    root = resolve_root(project_dir)

    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        raise ProjectScanError(f"no pyproject.toml found in {root}")
    try:
        pyproject_text = pyproject.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:  # pragma: no cover - defensive
        raise ProjectScanError(f"cannot read {pyproject}: {exc}") from exc

    try:
        project_license = parse_project_license(pyproject_text)
        dep_names = parse_dependencies(pyproject_text)
    except Exception as exc:  # tomllib.TOMLDecodeError and friends
        raise ProjectScanError(f"malformed pyproject.toml in {root}: {exc}") from exc

    deps: list[Dependency] = []
    unscanned: list[dict[str, str]] = []
    for name in dep_names:
        entry = lookup.get(name)
        if entry is None:
            deps.append(Dependency(name=name, license="UNKNOWN"))
            unscanned.append({"file": f"dist:{name}", "reason": "package metadata not found"})
            continue
        expr, classifiers, license_field = entry
        deps.append(
            Dependency(name=name, license=license_from_metadata(expr, classifiers, license_field))
        )

    notice_text = _read_notice(root)

    # Code-level facts (privacy / ai_aup / api_tos): PII-in-logs + imported modules.
    pii_log_sites, imports, code_unscanned = scan_python_files(str(root))
    unscanned.extend(code_unscanned)

    digest_input = "|".join(
        [project_license or ""]
        + sorted(f"{d.name}:{d.license}" for d in deps)
        + [str(notice_text is not None)]
        + sorted(f"{e.file}:{e.line}:{e.snippet}" for e in pii_log_sites)
        + sorted(imports)
    )
    model_hash = hashlib.sha256(digest_input.encode()).hexdigest()[:16]

    return ProjectModel(
        hash=model_hash,
        root=str(root),
        project_license=project_license,
        dependencies=deps,
        notice_file_present=notice_text is not None,
        notice_text=notice_text,
        pii_log_sites=pii_log_sites,
        imports=imports,
        unscanned=unscanned,
    )

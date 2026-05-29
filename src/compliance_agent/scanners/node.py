from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from ..errors import ProjectScanError
from ..models import Dependency, Evidence, ProjectModel
from ..safety import ensure_within
from .code_ast import identifier_pii_hit
from .pyproject import normalize_license

_NOTICE_FILES = ("NOTICE", "NOTICE.txt", "NOTICE.md")
_SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", "coverage", ".venv", "out"}
_SOURCE_EXTS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")

# Heuristic: opener of a `<receiver>.<verb>(` log call (any receiver, so winston/pino/custom
# loggers match, not just `console`/`logger`). The argument list is then captured by matching
# parentheses (handles nested calls like console.log(fmt(x), email)).
_LOG_OPEN_RE = re.compile(
    r"(?:console|[A-Za-z_$][\w$]*)\s*\.\s*(?:log|info|warn|error|debug)\s*\(",
)
_IDENT_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_MAX_ARG_SCAN = 4000  # cap how far we scan for a matching close paren


def _capture_args(text: str, open_end: int) -> str:
    """Return the substring inside a call whose '(' ended at open_end, matching nested parens."""
    depth = 1
    i = open_end
    limit = min(len(text), open_end + _MAX_ARG_SCAN)
    while i < limit:
        c = text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[open_end:i]
        i += 1
    return text[open_end:limit]


def license_from_package_json(pkg: dict) -> str:
    """Resolve an SPDX-ish license id from a package.json dict (string, {type}, or legacy list)."""
    if not isinstance(pkg, dict):
        return "UNKNOWN"
    lic = pkg.get("license")
    if isinstance(lic, str) and lic.strip():
        return normalize_license(lic)
    if isinstance(lic, dict) and isinstance(lic.get("type"), str):
        return normalize_license(lic["type"])
    lics = pkg.get("licenses")
    if isinstance(lics, list) and lics and isinstance(lics[0], dict) and lics[0].get("type"):
        return normalize_license(lics[0]["type"])
    return "UNKNOWN"


def parse_package_json(text: str) -> tuple[str | None, list[str]]:
    """Return (project_license, dependency names) from package.json text."""
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ProjectScanError("package.json must be a JSON object")
    project_license = license_from_package_json(data)
    if project_license == "UNKNOWN":
        project_license = None
    names: list[str] = []
    for key in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        section = data.get(key)
        if isinstance(section, dict):
            names.extend(section.keys())
    seen: set[str] = set()
    deduped: list[str] = []
    for name in names:
        if name not in seen:
            seen.add(name)
            deduped.append(name)
    return project_license, deduped


class _NodeModulesLookup:
    """Default lookup: read <root>/node_modules/<name>/package.json for a dependency's license."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def get(self, name: str):
        if ".." in name:  # never let an adversarial dep name traverse out of node_modules
            return None
        node_modules = self.root / "node_modules"
        try:
            pkg_dir = ensure_within(node_modules, node_modules / name)  # allows "@scope/pkg"
        except ProjectScanError:
            return None
        pkg_json = pkg_dir / "package.json"
        if not pkg_json.is_file():
            return None
        try:
            return license_from_package_json(json.loads(pkg_json.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            return None


def scan_js_pii(root: Path) -> tuple[list[Evidence], list[dict[str, str]]]:
    pii_sites: list[Evidence] = []
    unscanned: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if path.suffix not in _SOURCE_EXTS or not path.is_file():
            continue
        rel_path = path.relative_to(root)
        if any(part in _SKIP_DIRS for part in rel_path.parts[:-1]):
            continue
        rel = str(rel_path)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            unscanned.append({"file": rel, "reason": f"read error: {exc}"})
            continue
        for match in _LOG_OPEN_RE.finditer(text):
            args = _capture_args(text, match.end())
            hits = sorted(
                {
                    f"{ident} ({hit})"
                    for ident in _IDENT_RE.findall(args)
                    if (hit := identifier_pii_hit(ident))
                }
            )
            if hits:
                line = text.count("\n", 0, match.start()) + 1
                pii_sites.append(
                    Evidence(file=rel, line=line, snippet="PII in log call: " + ", ".join(hits))
                )
    return pii_sites, unscanned


def build_node_model(project_dir: str, pkg_lookup=None) -> ProjectModel:
    root = Path(project_dir)
    pkg_path = root / "package.json"
    if not pkg_path.is_file():
        raise ProjectScanError(f"no package.json found in {root}")
    try:
        project_license, dep_names = parse_package_json(pkg_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        raise ProjectScanError(f"malformed package.json in {root}: {exc}") from exc

    lookup = pkg_lookup if pkg_lookup is not None else _NodeModulesLookup(root)
    deps: list[Dependency] = []
    unscanned: list[dict[str, str]] = []
    for name in dep_names:
        lic = lookup.get(name)
        if lic is None:
            deps.append(Dependency(name=name, license="UNKNOWN"))
            unscanned.append({"file": f"npm:{name}", "reason": "package metadata not found"})
        else:
            deps.append(Dependency(name=name, license=lic))

    notice_text = None
    for fname in _NOTICE_FILES:
        candidate = root / fname
        if candidate.is_file():
            try:
                notice_text = candidate.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                notice_text = ""
            break

    pii_sites, code_unscanned = scan_js_pii(root)
    unscanned.extend(code_unscanned)

    digest_input = "|".join(
        [project_license or ""]
        + sorted(f"{d.name}:{d.license}" for d in deps)
        + [str(notice_text is not None)]
        + sorted(f"{e.file}:{e.line}:{e.snippet}" for e in pii_sites)
        + sorted(dep_names)
    )
    model_hash = hashlib.sha256(digest_input.encode()).hexdigest()[:16]

    return ProjectModel(
        hash=model_hash,
        root=str(root),
        project_license=project_license,
        dependencies=deps,
        notice_file_present=notice_text is not None,
        notice_text=notice_text,
        pii_log_sites=pii_sites,
        imports=dep_names,
        unscanned=unscanned,
    )

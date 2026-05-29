from __future__ import annotations

import ast
import os
import re
from pathlib import Path

from ..models import Evidence
from ._common import SKIP_DIRS as _SKIP_DIRS

# Logging-ish call targets: a call is "a log call" if it is `print(...)` or an attribute call
# whose final attribute is one of these verbs (logger.info, logging.error, self.log.debug, ...).
_LOG_VERBS = {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}

# PII identifier tokens. An argument identifier hits if any of its underscore/camelCase
# components equals one of these (precise component match, not loose substring).
_PII_TOKENS = {
    "email", "ssn", "password", "passwd", "secret", "cvv", "phone", "dob", "address",
    "passport", "iban", "msisdn", "pan", "fingerprint", "biometric",
}
# Multi-component PII names (joined check on the normalized component list).
_PII_PHRASES = {
    ("social", "security"), ("credit", "card"), ("card", "number"), ("date", "of", "birth"),
    ("full", "name"), ("first", "name"), ("last", "name"), ("bank", "account"),
    ("api", "key"), ("access", "token"), ("license", "number"), ("tax", "id"),
}

_CAMEL_RE = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+")


def _components(identifier: str) -> list[str]:
    parts: list[str] = []
    for chunk in identifier.split("_"):
        parts.extend(m.group(0).lower() for m in _CAMEL_RE.finditer(chunk))
    return parts


def identifier_pii_hit(identifier: str) -> str | None:
    """Return the PII keyword matched by an identifier, or None."""
    comps = _components(identifier)
    comp_set = set(comps)
    for token in _PII_TOKENS:
        if token in comp_set:
            return token
    for phrase in _PII_PHRASES:
        if all(p in comp_set for p in phrase):
            return " ".join(phrase)
    return None


def _is_log_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "print"
    if isinstance(func, ast.Attribute):
        return func.attr in _LOG_VERBS
    return False


class _Visitor(ast.NodeVisitor):
    def __init__(self, rel_path: str) -> None:
        self.rel_path = rel_path
        self.pii_sites: list[Evidence] = []
        self.imports: set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.add(alias.name.split(".")[0])
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module and node.level == 0:
            self.imports.add(node.module.split(".")[0])
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if _is_log_call(node):
            hits: list[str] = []
            for arg in list(node.args) + [kw.value for kw in node.keywords]:
                for sub in ast.walk(arg):
                    name = None
                    if isinstance(sub, ast.Name):
                        name = sub.id
                    elif isinstance(sub, ast.Attribute):
                        name = sub.attr
                    if name:
                        hit = identifier_pii_hit(name)
                        if hit:
                            hits.append(f"{name} ({hit})")
            if hits:
                self.pii_sites.append(
                    Evidence(
                        file=self.rel_path,
                        line=node.lineno,
                        snippet="PII in log call: " + ", ".join(sorted(set(hits))),
                    )
                )
        self.generic_visit(node)


def scan_python_files(root: str) -> tuple[list[Evidence], list[str], list[dict[str, str]]]:
    """Walk a project's .py files. Returns (pii_log_sites, imported top-level modules, unscanned)."""  # noqa: E501
    root_path = Path(root)
    pii_sites: list[Evidence] = []
    imports: set[str] = set()
    unscanned: list[dict[str, str]] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skipped dirs in place so we never descend into node_modules/.venv/etc.
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            path = Path(dirpath) / filename
            rel = str(path.relative_to(root_path))
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
            except (SyntaxError, UnicodeDecodeError, OSError) as exc:
                unscanned.append({"file": rel, "reason": f"parse error: {exc}"})
                continue
            visitor = _Visitor(rel)
            visitor.visit(tree)
            pii_sites.extend(visitor.pii_sites)
            imports.update(visitor.imports)

    return pii_sites, sorted(imports), unscanned

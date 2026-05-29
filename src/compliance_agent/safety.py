from __future__ import annotations

from pathlib import Path

from .errors import ProjectScanError


def resolve_root(path: str) -> Path:
    """Resolve a project path to a real, existing directory (symlinks collapsed)."""
    p = Path(path).resolve()
    if not p.is_dir():
        raise ProjectScanError(f"not a directory: {path}")
    return p


def ensure_within(root: Path, target: Path) -> Path:
    """Refuse to touch a path that escapes the project root (symlink/`..` defense).

    Returns the resolved target if it is the root itself or a descendant of it. If the final
    component is a symlink (or already exists), it is fully resolved so a symlink pointing
    outside the root is caught; otherwise only the parent is resolved (the file may not exist).
    """
    root_r = Path(root).resolve()
    candidate = target if target.is_absolute() else root_r / target
    if candidate.is_symlink() or candidate.exists():
        resolved = candidate.resolve()
    else:
        resolved = candidate.parent.resolve() / candidate.name
    if resolved != root_r and root_r not in resolved.parents:
        raise ProjectScanError(f"refusing to access path outside project root: {target}")
    return resolved

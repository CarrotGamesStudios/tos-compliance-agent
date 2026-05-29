from __future__ import annotations

# Directories the source scanners never descend into: VCS, caches, virtualenvs, dependency trees,
# and build/output artifacts (whose contents are generated, often minified, and not the project's
# authored source). Shared by code_ast, node, and platforms so the skip set stays consistent.
SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git", "__pycache__",
        "node_modules",
        ".venv", "venv", "env", ".tox", ".eggs",
        # build / output artifacts
        "build", "dist", "out", ".next", ".open-next", ".turbo", ".vercel", "coverage", ".cache",
        # tool caches
        ".mypy_cache", ".pytest_cache", ".ruff_cache",
        # editor / agent config
        ".cursor", ".idea", ".vscode",
    }
)

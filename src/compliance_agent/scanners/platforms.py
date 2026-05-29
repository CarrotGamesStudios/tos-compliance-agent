from __future__ import annotations

import os
from pathlib import Path

# Detect use of a social-platform API by its distinctive API host/path appearing in source.
# Keyed to API endpoints (not generic domains like youtube.com) for precision — a reference to
# these strongly implies the project integrates that platform's API and is bound by its ToS.
_PLATFORM_PATTERNS: dict[str, tuple[str, ...]] = {
    "youtube": ("youtube.googleapis.com", "googleapis.com/youtube", "/youtube/v3", "youtubei/v1"),
    "tiktok": ("tiktokapis.com", "open-api.tiktok.com", "business-api.tiktok.com"),
    "meta": ("graph.facebook.com", "graph.instagram.com"),
    "linkedin": ("api.linkedin.com",),
    "x": ("api.twitter.com", "api.x.com"),
    "threads": ("graph.threads.net",),
}

_SCAN_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".json", ".yaml", ".yml",
}


def _is_scannable(filename: str) -> bool:
    # Match by extension, plus dotenv files (.env, .env.local, ...) whose ".env" is not a suffix.
    return Path(filename).suffix in _SCAN_EXTS or filename.startswith(".env")
_SKIP_DIRS = {
    "node_modules", ".git", ".next", "dist", "build", ".venv", "venv", "__pycache__",
    "coverage", ".mypy_cache", ".pytest_cache", ".ruff_cache", "out", ".turbo",
}
_MAX_FILE_BYTES = 2_000_000  # skip very large files (lockfiles, bundles)


def detect_platform_apis(root: str) -> list[str]:
    """Sorted set of social platforms whose API host/path appears in the project's source."""
    found: set[str] = set()
    # Full pruned walk (no early-out): the result is the complete, order-independent set of
    # platforms whose API host appears anywhere in the (non-skipped) source.
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for filename in sorted(filenames):
            if not _is_scannable(filename):
                continue
            path = Path(dirpath) / filename
            try:
                if path.stat().st_size > _MAX_FILE_BYTES:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore").lower()
            except OSError:
                continue
            for platform, patterns in _PLATFORM_PATTERNS.items():
                if platform not in found and any(pat in text for pat in patterns):
                    found.add(platform)
    return sorted(found)

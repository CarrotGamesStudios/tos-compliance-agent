from __future__ import annotations

import json
from pathlib import Path

from ..errors import ProjectScanError
from .base import SourceDoc
from .extract import extract_text

# A local source store reads a `sources.json` manifest plus the referenced text files:
#   [{"id": "gpl-3.0", "domain": "license", "file": "gpl-3.0.txt",
#     "url_base": "https://www.gnu.org/licenses/gpl-3.0.txt", "provenance": "public"}, ...]


class LocalSourceStore:
    """Filesystem source store — useful for Tier-0/local runs and tests (no GCP needed)."""

    def __init__(self, directory: str) -> None:
        self.directory = Path(directory)

    def list_documents(self) -> list[SourceDoc]:
        manifest = self.directory / "sources.json"
        if not manifest.is_file():
            raise ProjectScanError(f"no sources.json in {self.directory}")
        try:
            entries = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ProjectScanError(f"malformed sources.json: {exc}") from exc

        docs: list[SourceDoc] = []
        for entry in entries:
            try:
                file_path = self.directory / entry["file"]
                if not file_path.is_file():
                    raise ProjectScanError(f"source file not found: {file_path}")
                docs.append(
                    SourceDoc(
                        id=entry["id"],
                        domain=entry["domain"],
                        text=extract_text(entry["file"], file_path.read_bytes()),
                        url_base=entry.get("url_base", ""),
                        provenance=entry.get("provenance", "public"),
                    )
                )
            except ProjectScanError:
                raise
            except KeyError as exc:
                raise ProjectScanError(f"source manifest entry missing key {exc}") from exc
            except Exception as exc:  # validation / decode errors -> clean message
                entry_id = entry.get("id", "?") if isinstance(entry, dict) else "?"
                raise ProjectScanError(f"invalid source entry {entry_id}: {exc}") from exc
        return docs

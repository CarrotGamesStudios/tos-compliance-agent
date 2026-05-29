from __future__ import annotations

import json

from ..errors import ProjectScanError
from .base import SourceDoc
from .extract import extract_text


class GcsSourceStore:
    """Source store backed by a GCS bucket prefix (the user's own bucket).

    Reads a `sources.json` manifest object at the prefix root, then each referenced blob. Lazily
    imports google-cloud-storage so Tier-0 installs don't require the GCP stack. Everything stays
    in the user's project (single-tenant).
    """

    def __init__(self, bucket: str, prefix: str = "sources/", *, client=None) -> None:
        self.bucket_name = bucket
        self.prefix = prefix.rstrip("/") + "/"
        self._client = client

    def _bucket(self):
        if self._client is None:
            from google.cloud import storage  # requires the [gcp] extra

            self._client = storage.Client()
        return self._client.bucket(self.bucket_name)

    def list_documents(self) -> list[SourceDoc]:
        bucket = self._bucket()
        manifest_blob = bucket.blob(f"{self.prefix}sources.json")
        try:
            entries = json.loads(manifest_blob.download_as_text())
        except json.JSONDecodeError as exc:
            manifest = f"gs://{self.bucket_name}/{self.prefix}sources.json"
            raise ProjectScanError(f"malformed {manifest}: {exc}") from exc
        except Exception as exc:  # google.cloud.exceptions.NotFound and friends
            raise ProjectScanError(
                f"cannot read gs://{self.bucket_name}/{self.prefix}sources.json: {exc}"
            ) from exc

        docs: list[SourceDoc] = []
        for entry in entries:
            try:
                file_name = entry["file"]
                blob = bucket.blob(f"{self.prefix}{file_name}")
                text = extract_text(file_name, blob.download_as_bytes())
                docs.append(
                    SourceDoc(
                        id=entry["id"],
                        domain=entry["domain"],
                        text=text,
                        url_base=entry.get("url_base", ""),
                        provenance=entry.get("provenance", "public"),
                    )
                )
            except KeyError as exc:
                raise ProjectScanError(f"source manifest entry missing key {exc}") from exc
            except Exception as exc:
                entry_id = entry.get("id", "?") if isinstance(entry, dict) else "?"
                raise ProjectScanError(
                    f"cannot read source blob for entry {entry_id}: {exc}"
                ) from exc
        return docs

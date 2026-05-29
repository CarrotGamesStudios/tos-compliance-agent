from __future__ import annotations

from pathlib import Path

from .compiler.core import ModelClient, compile_document, doc_version
from .config import DEFAULT_MODEL
from .models import PolicyPack
from .packs import load_pack, save_pack, validate_pack_id
from .sources.base import SourceStore


def _existing_version(packs_dir: str, doc_id: str) -> str | None:
    path = Path(packs_dir) / f"{doc_id}.json"
    if not path.is_file():
        return None
    try:
        return load_pack(str(path)).source_version
    except Exception:
        return None


def refresh_packs(
    store: SourceStore,
    model_client: ModelClient,
    packs_dir: str,
    *,
    model: str = DEFAULT_MODEL,
    compiled_at: str | None = None,
) -> dict[str, object]:
    """Recompile only the source documents whose content changed (upstream-drift detection).

    For each source doc: if a pack already exists with the same content-hash version, it is left
    untouched; otherwise the doc is recompiled and the pack rewritten. Returns a summary listing
    which packs changed (upstream drift) and any obligations dropped by clause verification.
    """
    changed: list[dict[str, str]] = []
    unchanged: list[str] = []
    dropped_all: list[dict[str, str]] = []
    packs: list[PolicyPack] = []

    for doc in store.list_documents():
        validate_pack_id(doc.id)  # doc id becomes a pack filename — reject traversal
        version = doc_version(doc.text)
        if _existing_version(packs_dir, doc.id) == version:
            unchanged.append(doc.id)
            continue
        pack, dropped = compile_document(
            doc_text=doc.text,
            doc_id=doc.id,
            domain=doc.domain,
            model_client=model_client,
            url_base=doc.url_base,
            model=model,
            provenance=doc.provenance,
            compiled_at=compiled_at,
        )
        save_pack(packs_dir, pack)
        packs.append(pack)
        changed.append(
            {"id": doc.id, "version": version, "obligations": str(len(pack.obligations))}
        )
        for d in dropped:
            dropped_all.append({"doc": doc.id, **d})

    return {
        "changed": changed,
        "unchanged": unchanged,
        "dropped": dropped_all,
        "upstream_drift": bool(changed),
    }

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from ..models import Domain, Provenance


class SourceDoc(BaseModel):
    """A raw source document (ToS / regulation / license / AUP / internal policy / contract)."""

    id: str
    domain: Domain
    text: str
    url_base: str = ""
    provenance: Provenance = "public"


class SourceStore(Protocol):
    """A store of raw source documents the compiler reads to (re)build PolicyPacks."""

    def list_documents(self) -> list[SourceDoc]: ...

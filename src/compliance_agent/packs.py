from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from .errors import ProjectScanError
from .models import PolicyPack
from .predicates import validate_predicate

# Resolve the bundled packs directory for both layouts:
#  - installed wheel: packs/ are force-included at compliance_agent/_bundled_packs
#  - source tree:      packs/ live at the repo root (src/compliance_agent/packs.py -> parents[2])
_INSTALLED_DIR = Path(__file__).resolve().parent / "_bundled_packs"
_SOURCE_DIR = Path(__file__).resolve().parents[2] / "packs"

# A pack id becomes a filename, so it must not contain path separators or traversal.
_PACK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

# Env var pointing at a directory of user-compiled packs to enforce ALONGSIDE the bundled ones
# (the output of `compliance-agent refresh`). Lets a hosted/self-installed deployment actually
# enforce its own obligations without rebuilding the package.
PACKS_DIR_ENV = "COMPLIANCE_PACKS_DIR"


def _bundled_dir() -> Path:
    return _INSTALLED_DIR if _INSTALLED_DIR.is_dir() else _SOURCE_DIR


def validate_pack_id(pack_id: str) -> str:
    """Reject pack ids that could escape the packs directory when used as a filename."""
    if ".." in pack_id or not _PACK_ID_RE.match(pack_id):
        raise ProjectScanError(
            f"unsafe pack/source id {pack_id!r}: must match {_PACK_ID_RE.pattern} (no '..')"
        )
    return pack_id


def load_pack(path: str) -> PolicyPack:
    pack = PolicyPack.model_validate_json(Path(path).read_text(encoding="utf-8"))
    for ob in pack.obligations:
        try:
            validate_predicate(ob.applies_when)
        except ValueError as exc:
            raise ValueError(
                f"invalid applies_when in obligation '{ob.id}' ({path}): {exc}"
            ) from exc
    return pack


def load_bundled_packs() -> list[PolicyPack]:
    return [load_pack(str(p)) for p in sorted(_bundled_dir().glob("*.json"))]


def load_packs_from(directory: str) -> list[PolicyPack]:
    """Load all PolicyPacks from a directory (e.g. a compiled-packs dir or GCS-synced cache)."""
    return [load_pack(str(p)) for p in sorted(Path(directory).glob("*.json"))]


def load_active_packs() -> list[PolicyPack]:
    """The packs actually enforced at scan time: bundled packs PLUS user packs from
    $COMPLIANCE_PACKS_DIR (if set). A user pack overrides a bundled pack with the same id, so a
    deployment's compiled obligations are genuinely enforced — not just the baked-in defaults."""
    by_id: dict[str, PolicyPack] = {p.id: p for p in load_bundled_packs()}
    ext = os.getenv(PACKS_DIR_ENV)
    if ext:
        if Path(ext).is_dir():
            for pack in load_packs_from(ext):
                by_id[pack.id] = pack
        else:
            # Set but unusable — warn loudly so an inert mount/bake doesn't pass silently.
            print(
                f"warning: {PACKS_DIR_ENV}={ext!r} is not a directory; user packs not loaded",
                file=sys.stderr,
            )
    return list(by_id.values())


def save_pack(directory: str, pack: PolicyPack) -> str:
    """Write a PolicyPack to `<directory>/<pack.id>.json` and return the path."""
    validate_pack_id(pack.id)
    out_dir = Path(directory)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{pack.id}.json"
    target.write_text(pack.model_dump_json(indent=2), encoding="utf-8")
    return str(target)

from __future__ import annotations

from pathlib import Path

from .models import PolicyPack
from .predicates import validate_predicate

# Resolve the bundled packs directory for both layouts:
#  - installed wheel: packs/ are force-included at compliance_agent/_bundled_packs
#  - source tree:      packs/ live at the repo root (src/compliance_agent/packs.py -> parents[2])
_INSTALLED_DIR = Path(__file__).resolve().parent / "_bundled_packs"
_SOURCE_DIR = Path(__file__).resolve().parents[2] / "packs"


def _bundled_dir() -> Path:
    return _INSTALLED_DIR if _INSTALLED_DIR.is_dir() else _SOURCE_DIR


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

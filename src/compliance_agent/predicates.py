from __future__ import annotations

from typing import Any

from .models import ProjectModel

_LIST_OPS = {"dep_license_in", "project_license_in", "uses_import_in"}
_STR_OPS = {"has_dep_license", "uses_import"}
_BOOL_OPS = {"notice_file_present", "has_pii_in_logs"}
_COMPOUND_OPS = {"all", "any"}


def validate_predicate(pred: Any) -> None:
    """Statically validate a predicate's shape and operand types.

    Called at pack-load time so a malformed pack (or future compiler output) fails loudly
    with a clear error instead of crashing — or silently misbehaving — mid-scan.
    """
    if not isinstance(pred, dict) or len(pred) != 1:
        raise ValueError(f"predicate must be a single-key dict, got {pred!r}")
    ((op, value),) = pred.items()
    if op in _COMPOUND_OPS:
        if not isinstance(value, list) or not value:
            raise ValueError(f"'{op}' requires a non-empty list of sub-predicates")
        for child in value:
            validate_predicate(child)
    elif op == "not":
        validate_predicate(value)
    elif op in _LIST_OPS:
        if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            raise ValueError(f"'{op}' requires a list of license strings, got {value!r}")
    elif op in _STR_OPS:
        if not isinstance(value, str):
            raise ValueError(f"'{op}' requires a license string, got {value!r}")
    elif op in _BOOL_OPS:
        if not isinstance(value, bool):
            raise ValueError(f"'{op}' requires a boolean, got {value!r}")
    else:
        raise ValueError(f"unknown predicate op: {op}")


def evaluate_predicate(pred: dict[str, Any], model: ProjectModel) -> bool:
    """Safe, structured boolean evaluator over ProjectModel facts. No code eval.

    Assumes `pred` has passed `validate_predicate` (enforced at pack load); still re-checks
    structure defensively so a hand-built predicate can't silently misbehave.
    """
    validate_predicate(pred)
    ((op, value),) = pred.items()

    if op == "all":
        return all(evaluate_predicate(p, model) for p in value)
    if op == "any":
        return any(evaluate_predicate(p, model) for p in value)
    if op == "not":
        return not evaluate_predicate(value, model)

    dep_licenses = {d.license for d in model.dependencies}
    if op == "has_dep_license":
        return value in dep_licenses
    if op == "dep_license_in":
        return bool(dep_licenses & set(value))
    if op == "project_license_in":
        return model.project_license in set(value)
    if op == "notice_file_present":
        return model.notice_file_present == value
    if op == "has_pii_in_logs":
        return bool(model.pii_log_sites) == value
    if op == "uses_import":
        return value in set(model.imports)
    if op == "uses_import_in":
        return bool(set(model.imports) & set(value))

    raise ValueError(f"unknown predicate op: {op}")  # pragma: no cover - validate_predicate guards

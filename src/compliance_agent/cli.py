from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from . import __version__
from .engine import evaluate
from .errors import ProjectScanError
from .packs import load_bundled_packs
from .remediation import apply_fix
from .report import to_json, to_markdown
from .scanners.licenses import build_project_model


def _scan(path: str, dist_lookup, as_json: bool) -> tuple[int, list]:
    model = build_project_model(path, dist_lookup=dist_lookup)
    findings = evaluate(model, load_bundled_packs())
    out = to_json(findings, model) if as_json else to_markdown(findings, model.unscanned)
    print(out)
    violations = [f for f in findings if f.status == "violation"]
    return (1 if violations else 0), findings


def main(argv: Sequence[str] | None = None, dist_lookup=None) -> int:
    parser = argparse.ArgumentParser(prog="compliance-agent")
    parser.add_argument("--version", action="version", version=f"compliance-agent {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="scan a project and report findings")
    p_scan.add_argument("path")
    p_scan.add_argument("--json", action="store_true")

    p_fix = sub.add_parser("fix", help="apply deterministic auto-fixes")
    p_fix.add_argument("path")
    p_fix.add_argument("--apply", action="store_true", help="write fixes (default: dry-run)")

    args = parser.parse_args(argv)

    try:
        if args.command == "scan":
            code, _ = _scan(args.path, dist_lookup, args.json)
            return code

        if args.command == "fix":
            model = build_project_model(args.path, dist_lookup=dist_lookup)
            findings = evaluate(model, load_bundled_packs())
            auto = [f for f in findings if f.remediation.get("kind") == "auto"]
            if not auto:
                print("No auto-fixable findings.")
                return 0
            for f in auto:
                if args.apply:
                    written = apply_fix(model, f)
                    print(f"Fixed {f.obligation_id} -> {written}")
                else:
                    print(f"Would fix {f.obligation_id} (run with --apply)")
            return 0
    except ProjectScanError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    return 2


if __name__ == "__main__":
    sys.exit(main())

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .config import DEFAULT_MODEL
from .engine import evaluate
from .errors import ProjectScanError
from .packs import load_active_packs
from .remediation import apply_fix
from .report import to_json, to_markdown
from .scanners.licenses import build_project_model


def _scan(path: str, dist_lookup, as_json: bool, judge=None) -> tuple[int, list]:
    model = build_project_model(path, dist_lookup=dist_lookup)
    findings = evaluate(model, load_active_packs(), judge=judge)
    out = to_json(findings, model) if as_json else to_markdown(findings, model.unscanned)
    print(out)
    violations = [f for f in findings if f.status == "violation"]
    return (1 if violations else 0), findings


def _build_judge(args):
    """Construct a Gemini judge for judgment obligations, or None when --judge is not set.

    Raises ProjectScanError (clean CLI error) if the GCP extra is missing or the Gemini client
    can't initialize. Per-obligation judge failures during the scan still degrade to needs_review.
    """
    if not getattr(args, "judge", False):
        return None
    try:
        from .compiler.genai_client import GenaiModelClient
        from .judge import GeminiJudge

        client = GenaiModelClient(
            project=getattr(args, "project", None),
            location=getattr(args, "location", "us-central1"),
        )
    except ImportError as exc:
        raise ProjectScanError(
            f"--judge needs the GCP extra — `pip install 'compliance-agent[gcp]'` ({exc})"
        ) from exc
    except Exception as exc:
        raise ProjectScanError(f"--judge: could not initialize the Gemini client: {exc}") from exc
    return GeminiJudge(client=client)


# ── Tier-1 helpers (pure + testable) ──


# GCP identifiers are tightly constrained; validate so nothing can break out of the HCL string
# (no quotes, backslashes, newlines, or ${} interpolation reach terraform.tfvars).
_TFVAR_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")


def build_tfvars(project: str, location: str, bucket: str, create_firestore: bool = True) -> str:
    for name, value in (("project", project), ("location", location), ("bucket", bucket)):
        if not _TFVAR_SAFE.match(value):
            raise ProjectScanError(
                f"invalid --{name} {value!r}: must match {_TFVAR_SAFE.pattern}"
            )
    return (
        f'project_id  = "{project}"\n'
        f'location    = "{location}"\n'
        f'bucket_name = "{bucket}"\n'
        f"create_firestore = {str(create_firestore).lower()}\n"
    )


def terraform_commands(tf_dir: str, apply: bool) -> list[list[str]]:
    action = "apply" if apply else "plan"
    init = ["terraform", f"-chdir={tf_dir}", "init", "-input=false"]
    run = ["terraform", f"-chdir={tf_dir}", action, "-input=false", "-var-file=terraform.tfvars"]
    if apply:
        run.append("-auto-approve")
    return [init, run]


def _cmd_refresh(args) -> int:
    from .refresh import refresh_packs

    try:
        if args.gcs_bucket:
            from .sources.gcs import GcsSourceStore

            store = GcsSourceStore(args.gcs_bucket, args.gcs_prefix)
        else:
            from .sources import LocalSourceStore

            store = LocalSourceStore(args.sources)
        from .compiler.genai_client import GenaiModelClient

        client = GenaiModelClient(project=args.project, location=args.location)
        summary = refresh_packs(store, client, args.packs, model=args.model)
    except ImportError as exc:
        print(
            f"error: refresh needs the GCP extra — `pip install 'compliance-agent[gcp]'` ({exc})",
            file=sys.stderr,
        )
        return 2
    except ProjectScanError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # model/auth/network/compile failures -> clean message
        print(f"error: refresh failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, indent=2))
    return 0


def _cmd_init(args) -> int:
    tf_dir = args.tf_dir
    if not Path(tf_dir).is_dir():
        print(f"error: terraform dir not found: {tf_dir}", file=sys.stderr)
        return 2
    tfvars_path = Path(tf_dir) / "terraform.tfvars"
    tfvars_path.write_text(
        build_tfvars(args.project, args.location, args.bucket, args.create_firestore),
        encoding="utf-8",
    )
    print(f"Wrote {tfvars_path}")
    cmds = terraform_commands(tf_dir, args.apply)
    for cmd in cmds:
        print("  $ " + " ".join(cmd))
    if not args.apply:
        print("\n(dry-run) re-run with --apply to provision into your own GCP project.")
        return 0
    for cmd in cmds:
        try:
            # args are a constructed list (no shell); generous timeout for terraform apply.
            result = subprocess.run(cmd, timeout=3600)  # noqa: S603
        except FileNotFoundError:
            print("error: `terraform` not found on PATH — install it first.", file=sys.stderr)
            return 2
        except subprocess.TimeoutExpired:
            print(f"error: command timed out: {' '.join(cmd)}", file=sys.stderr)
            return 2
        if result.returncode != 0:
            print(f"error: command failed: {' '.join(cmd)}", file=sys.stderr)
            return result.returncode
    return 0


def main(argv: Sequence[str] | None = None, dist_lookup=None) -> int:
    parser = argparse.ArgumentParser(prog="compliance-agent")
    parser.add_argument("--version", action="version", version=f"compliance-agent {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="scan a project and report findings")
    p_scan.add_argument("path")
    p_scan.add_argument("--json", action="store_true")
    p_scan.add_argument(
        "--judge",
        action="store_true",
        help="evaluate judgment obligations with Gemini (needs a Gemini/Vertex key; "
        "GEMINI_API_KEY for AI Studio, or --project for Vertex)",
    )
    p_scan.add_argument("--project", default=None, help="GCP project for Vertex (judge)")
    p_scan.add_argument("--location", default="us-central1")

    p_fix = sub.add_parser("fix", help="apply deterministic auto-fixes")
    p_fix.add_argument("path")
    p_fix.add_argument("--apply", action="store_true", help="write fixes (default: dry-run)")

    p_ref = sub.add_parser("refresh", help="recompile Policy Packs from source docs (drift)")
    p_ref.add_argument("--sources", default="sources", help="local source dir (with sources.json)")
    p_ref.add_argument("--packs", default="packs", help="output dir for compiled packs")
    p_ref.add_argument("--gcs-bucket", default=None, help="read sources from this GCS bucket")
    p_ref.add_argument("--gcs-prefix", default="sources/")
    p_ref.add_argument("--project", default=None, help="GCP project (Vertex) for the model")
    p_ref.add_argument("--location", default="us-central1")
    p_ref.add_argument("--model", default=DEFAULT_MODEL)

    p_init = sub.add_parser("init", help="provision Tier-1 infra into YOUR GCP project (Terraform)")
    p_init.add_argument("--project", required=True)
    p_init.add_argument("--location", default="us-central1")
    p_init.add_argument("--bucket", required=True, help="GCS bucket name for source docs + packs")
    p_init.add_argument("--tf-dir", default="deploy/terraform")
    p_init.add_argument("--apply", action="store_true", help="actually run terraform apply")
    p_init.add_argument(
        "--no-create-firestore",
        dest="create_firestore",
        action="store_false",
        help="skip Firestore creation (use if the project already has a (default) database)",
    )

    args = parser.parse_args(argv)

    try:
        if args.command == "scan":
            code, _ = _scan(args.path, dist_lookup, args.json, judge=_build_judge(args))
            return code

        if args.command == "fix":
            model = build_project_model(args.path, dist_lookup=dist_lookup)
            findings = evaluate(model, load_active_packs())
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

        if args.command == "refresh":
            return _cmd_refresh(args)

        if args.command == "init":
            return _cmd_init(args)
    except ProjectScanError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    return 2


if __name__ == "__main__":
    sys.exit(main())

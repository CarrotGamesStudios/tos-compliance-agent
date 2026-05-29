# Tier-0 Walking Skeleton — OSS License × Python (CLI + MCP) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an installable, cloud-free compliance agent that scans a Python project for OSS-license violations using a checked-in Policy Pack, flags incompatibilities with citations, auto-fixes missing-attribution issues, tracks drift against a local baseline, and exposes both a CLI and an MCP server.

**Architecture:** Deterministic hybrid backbone (no LLM in Tier 0). A `ProjectModel` of facts is built by pure scanners; a checked-in `PolicyPack` of `Obligation`s is matched via a safe structured-predicate evaluator; deterministic analyzers produce `Finding`s with verbatim source citations; remediation generates/applies patches for auto-fixable findings only; drift compares findings to a stored `Baseline`. The same engine is wrapped by a CLI and a FastMCP server.

**Tech Stack:** Python 3.11+, pydantic v2, `importlib.metadata` (stdlib), `tomllib` (stdlib), `fastmcp` (3.x), `pytest`. License: Apache-2.0.

This is **Plan 1 of 5** (see spec §9). It produces working, demoable software on its own. Later plans add Tier-1 hosting, the LLM compiler, more domains, internal/B2B sourcing, and Node/TS.

---

## File Structure

```
tos-compliance-agent/
├─ pyproject.toml                         # package metadata + deps + pytest config
├─ LICENSE                                # Apache-2.0
├─ README.md
├─ packs/
│  └─ license-core.json                   # checked-in PUBLIC license PolicyPack
├─ src/compliance_agent/
│  ├─ __init__.py
│  ├─ models.py                           # pydantic data model (Tier-0 subset)
│  ├─ packs.py                            # load + validate PolicyPack JSON
│  ├─ predicates.py                       # safe structured applies_when evaluator
│  ├─ scanners/
│  │  ├─ __init__.py
│  │  ├─ pyproject.py                     # parse project license + dependency names (pure)
│  │  └─ licenses.py                      # license extraction (pure) + build_project_model
│  ├─ analyzers/
│  │  ├─ __init__.py                      # ANALYZERS registry
│  │  ├─ gpl_incompatibility.py
│  │  └─ missing_notice.py
│  ├─ engine.py                           # match + evaluate → Findings
│  ├─ drift.py                            # Baseline load/save + delta
│  ├─ remediation.py                      # NOTICE patch generation + apply
│  ├─ report.py                           # JSON + Markdown rendering
│  ├─ cli.py                              # `compliance-agent scan|fix`
│  └─ mcp_server.py                       # FastMCP server
└─ tests/
   ├─ __init__.py
   ├─ fixtures/                           # built at runtime by tests via tmp_path
   ├─ test_models.py
   ├─ test_pyproject.py
   ├─ test_licenses.py
   ├─ test_predicates.py
   ├─ test_packs.py
   ├─ test_analyzers.py
   ├─ test_engine.py
   ├─ test_drift.py
   ├─ test_remediation.py
   ├─ test_report.py
   ├─ test_cli.py
   ├─ test_mcp_server.py
   └─ test_end_to_end.py
```

**Module responsibilities (decomposition):** `models` = data only; `scanners` = facts in, no judgments; `predicates` = pure boolean over facts; `analyzers` = precise evidence per check; `engine` = orchestration only (no I/O, no file writes); `remediation` = the only module that writes project files; `drift`/`report`/`cli`/`mcp_server` = thin shells over the engine. Files that change together (a scanner + its tests) live together.

---

## Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`, `LICENSE`, `README.md`, `src/compliance_agent/__init__.py`, `tests/__init__.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "compliance-agent"
version = "0.1.0"
description = "Self-installable ToS/Compliance drift agent (Tier-0: OSS license, Python)"
readme = "README.md"
requires-python = ">=3.11"
license = "Apache-2.0"
dependencies = [
    "pydantic>=2.6",
    "fastmcp>=3.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
compliance-agent = "compliance_agent.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/compliance_agent"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 2: Create `LICENSE`**

Write the standard Apache License 2.0 text (full text from https://www.apache.org/licenses/LICENSE-2.0.txt). Copyright line: `Copyright 2026 ToS/Compliance Agent contributors`.

- [ ] **Step 3: Create `README.md`**

```markdown
# ToS / Compliance Agent (Tier-0)

Self-installable, single-tenant compliance-drift agent. Tier-0 runs fully locally
(no Google Cloud required) and checks Python projects for OSS-license compliance.

## Install
    pip install -e ".[dev]"

## Use
    compliance-agent scan /path/to/project
    compliance-agent fix /path/to/project --apply

## MCP server (for AI coding assistants)
    python -m compliance_agent.mcp_server
```

- [ ] **Step 4: Create empty package markers**

`src/compliance_agent/__init__.py`:
```python
__version__ = "0.1.0"
```
`tests/__init__.py`: empty file.

- [ ] **Step 5: Install and verify import**

Run: `pip install -e ".[dev]" && python -c "import compliance_agent; print(compliance_agent.__version__)"`
Expected: prints `0.1.0`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml LICENSE README.md src tests
git commit -m "chore: project scaffold for Tier-0 compliance agent"
```

---

## Task 2: Data models

**Files:**
- Create: `src/compliance_agent/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from compliance_agent.models import (
    Source, Check, Fix, Obligation, PolicyPack,
    Dependency, ProjectModel, Evidence, Finding, Baseline,
)


def test_obligation_roundtrips_through_json():
    ob = Obligation(
        id="lic-gpl-incompat",
        domain="license",
        source=Source(
            doc="gpl-3.0", provenance="public", version="spdx-2026",
            clause_quote="You may convey a covered work...", url_or_section="GPL-3.0 §5",
        ),
        applies_when={"all": [{"has_dep_license": "GPL-3.0"}]},
        requirement="GPL-3.0 deps require the project to be GPL-compatible.",
        check=Check(kind="deterministic", analyzer="gpl_incompatibility",
                    params={"incompatible_licenses": ["GPL-3.0"]}),
        severity="high",
        fix=Fix(kind="manual", guidance="Replace the dependency or relicense."),
    )
    dumped = ob.model_dump_json()
    again = Obligation.model_validate_json(dumped)
    assert again == ob


def test_project_model_defaults():
    pm = ProjectModel(hash="abc", root="/tmp/p")
    assert pm.dependencies == []
    assert pm.notice_file_present is False
    assert pm.project_license is None


def test_finding_carries_citation():
    f = Finding(
        obligation_id="x", domain="license", severity="high", status="violation",
        evidence=[Evidence(file="pyproject.toml", line=None, snippet="dep: somelib")],
        citation={"clause_quote": "q", "url_or_section": "GPL-3.0 §5"},
        remediation={"kind": "manual", "guidance": "g"}, confidence=1.0,
    )
    assert f.citation["url_or_section"] == "GPL-3.0 §5"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'compliance_agent.models'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/compliance_agent/models.py
from __future__ import annotations
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

Provenance = Literal["public", "internal"]
Domain = Literal["license", "ai_aup", "privacy", "api_tos", "internal_policy", "contract"]
Severity = Literal["low", "medium", "high", "critical"]


class Source(BaseModel):
    doc: str
    provenance: Provenance
    version: str
    clause_quote: str
    url_or_section: str


class Check(BaseModel):
    kind: Literal["deterministic", "judgment"]
    analyzer: Optional[str] = None
    params: dict[str, Any] = Field(default_factory=dict)
    prompt_template: Optional[str] = None


class Fix(BaseModel):
    kind: Literal["auto", "manual"]
    codemod: Optional[str] = None
    guidance: Optional[str] = None


class Obligation(BaseModel):
    id: str
    domain: Domain
    source: Source
    applies_when: dict[str, Any]
    requirement: str
    check: Check
    severity: Severity
    fix: Fix


class PolicyPack(BaseModel):
    id: str
    domain: Domain
    provenance: Provenance
    source_doc: str
    source_version: str
    compiled_at: str
    obligations: list[Obligation]


class Dependency(BaseModel):
    name: str
    version: Optional[str] = None
    license: str = "UNKNOWN"
    transitive: bool = False


class ProjectModel(BaseModel):
    hash: str
    root: str
    project_license: Optional[str] = None
    dependencies: list[Dependency] = Field(default_factory=list)
    notice_file_present: bool = False
    unscanned: list[dict[str, str]] = Field(default_factory=list)


class Evidence(BaseModel):
    file: str
    line: Optional[int] = None
    snippet: str = ""


class Finding(BaseModel):
    obligation_id: str
    domain: Domain
    severity: Severity
    status: Literal["violation", "needs_review", "fixed"]
    evidence: list[Evidence] = Field(default_factory=list)
    citation: dict[str, str]
    remediation: dict[str, Any]
    confidence: float


class Baseline(BaseModel):
    project_model_hash: str
    policy_pack_versions: dict[str, str] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/compliance_agent/models.py tests/test_models.py
git commit -m "feat: Tier-0 pydantic data model"
```

---

## Task 3: pyproject scanner (project license + dependency names)

**Files:**
- Create: `src/compliance_agent/scanners/__init__.py`, `src/compliance_agent/scanners/pyproject.py`
- Test: `tests/test_pyproject.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pyproject.py
from compliance_agent.scanners.pyproject import parse_project_license, parse_dependencies

PYPROJECT = """
[project]
name = "demo"
license = "MIT"
dependencies = [
    "requests>=2.0",
    "somelib==1.2.3",
    "extra-pkg[fast]>=0.1; python_version>='3.10'",
]
"""

CLASSIFIER_LICENSE = """
[project]
name = "demo"
classifiers = ["License :: OSI Approved :: Apache Software License"]
"""


def test_parse_project_license_from_string():
    assert parse_project_license(PYPROJECT) == "MIT"


def test_parse_project_license_from_classifier():
    assert parse_project_license(CLASSIFIER_LICENSE) == "Apache-2.0"


def test_parse_project_license_absent_returns_none():
    assert parse_project_license('[project]\nname = "x"\n') is None


def test_parse_dependencies_strips_specifiers_and_extras():
    assert parse_dependencies(PYPROJECT) == ["requests", "somelib", "extra-pkg"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pyproject.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/compliance_agent/scanners/__init__.py
```
(empty file)

```python
# src/compliance_agent/scanners/pyproject.py
from __future__ import annotations
import re
import tomllib
from typing import Optional

# Minimal Trove-classifier -> SPDX map (extended in later plans).
_CLASSIFIER_TO_SPDX = {
    "License :: OSI Approved :: MIT License": "MIT",
    "License :: OSI Approved :: Apache Software License": "Apache-2.0",
    "License :: OSI Approved :: BSD License": "BSD-3-Clause",
    "License :: OSI Approved :: GNU General Public License v3 (GPLv3)": "GPL-3.0",
    "License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)": "AGPL-3.0",
}

# PEP 508: a name is the leading run of letters/digits/._- before any specifier/extra/marker.
_NAME_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")


def parse_project_license(pyproject_text: str) -> Optional[str]:
    data = tomllib.loads(pyproject_text)
    project = data.get("project", {})
    lic = project.get("license")
    if isinstance(lic, str) and lic.strip():
        return lic.strip()
    if isinstance(lic, dict) and isinstance(lic.get("text"), str) and lic["text"].strip():
        return lic["text"].strip()
    for classifier in project.get("classifiers", []):
        if classifier in _CLASSIFIER_TO_SPDX:
            return _CLASSIFIER_TO_SPDX[classifier]
    return None


def parse_dependencies(pyproject_text: str) -> list[str]:
    data = tomllib.loads(pyproject_text)
    names: list[str] = []
    for raw in data.get("project", {}).get("dependencies", []):
        match = _NAME_RE.match(raw.strip())
        if match:
            names.append(match.group(1))
    return names
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pyproject.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/compliance_agent/scanners tests/test_pyproject.py
git commit -m "feat: pyproject license + dependency parsing"
```

---

## Task 4: License extraction from distribution metadata (pure)

**Files:**
- Create: `src/compliance_agent/scanners/licenses.py`
- Test: `tests/test_licenses.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_licenses.py
from compliance_agent.scanners.licenses import license_from_metadata


def test_prefers_license_expression():
    assert license_from_metadata("Apache-2.0", [], None) == "Apache-2.0"


def test_falls_back_to_classifier():
    out = license_from_metadata(
        None, ["License :: OSI Approved :: GNU General Public License v3 (GPLv3)"], None
    )
    assert out == "GPL-3.0"


def test_falls_back_to_short_license_field():
    assert license_from_metadata(None, [], "MIT") == "MIT"


def test_long_license_field_is_unknown():
    long_text = "Permission is hereby granted, free of charge, to any person..."
    assert license_from_metadata(None, [], long_text) == "UNKNOWN"


def test_nothing_is_unknown():
    assert license_from_metadata(None, [], None) == "UNKNOWN"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_licenses.py -v`
Expected: FAIL with `ImportError: cannot import name 'license_from_metadata'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/compliance_agent/scanners/licenses.py
from __future__ import annotations
from typing import Optional
from .pyproject import _CLASSIFIER_TO_SPDX


def license_from_metadata(
    license_expression: Optional[str],
    classifiers: list[str],
    license_field: Optional[str],
) -> str:
    """Resolve an SPDX-ish license id from a distribution's metadata fields.

    Priority: License-Expression (already SPDX) > Trove classifier > short License field.
    A long License field (full license text) is treated as UNKNOWN.
    """
    if license_expression and license_expression.strip():
        return license_expression.strip()
    for classifier in classifiers:
        if classifier in _CLASSIFIER_TO_SPDX:
            return _CLASSIFIER_TO_SPDX[classifier]
    if license_field and license_field.strip():
        text = license_field.strip()
        # A real SPDX id is short and single-line; full license text is not.
        if len(text) <= 40 and "\n" not in text and " " not in text.strip(" .-"):
            return text
    return "UNKNOWN"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_licenses.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/compliance_agent/scanners/licenses.py tests/test_licenses.py
git commit -m "feat: license extraction from distribution metadata"
```

---

## Task 5: build_project_model (facts assembly with injected lookup)

**Files:**
- Modify: `src/compliance_agent/scanners/licenses.py`
- Test: `tests/test_licenses.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_licenses.py  (append)
from compliance_agent.scanners.licenses import build_project_model


class FakeLookup:
    """Stand-in for importlib.metadata: name -> (license_expression, classifiers, license_field)."""
    def __init__(self, table):
        self.table = table

    def get(self, name):
        return self.table.get(name)


def test_build_project_model_resolves_dep_licenses(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="demo"\nlicense="MIT"\n'
        'dependencies=["gpllib>=1.0","apachelib>=2.0"]\n'
    )
    lookup = FakeLookup({
        "gpllib": (None, ["License :: OSI Approved :: GNU General Public License v3 (GPLv3)"], None),
        "apachelib": ("Apache-2.0", [], None),
    })
    pm = build_project_model(str(tmp_path), dist_lookup=lookup)

    assert pm.project_license == "MIT"
    licenses = {d.name: d.license for d in pm.dependencies}
    assert licenses == {"gpllib": "GPL-3.0", "apachelib": "Apache-2.0"}
    assert pm.notice_file_present is False
    assert pm.hash  # non-empty


def test_build_project_model_flags_unknown_lookup_as_unscanned(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="demo"\nlicense="MIT"\ndependencies=["ghostlib>=1.0"]\n'
    )
    pm = build_project_model(str(tmp_path), dist_lookup=FakeLookup({}))
    assert pm.dependencies[0].license == "UNKNOWN"
    assert pm.unscanned and pm.unscanned[0]["file"] == "dist:ghostlib"


def test_build_project_model_detects_notice_file(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname="demo"\nlicense="MIT"\n')
    (tmp_path / "NOTICE").write_text("attributions\n")
    pm = build_project_model(str(tmp_path), dist_lookup=FakeLookup({}))
    assert pm.notice_file_present is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_licenses.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_project_model'`

- [ ] **Step 3: Write minimal implementation (append to licenses.py)**

```python
# src/compliance_agent/scanners/licenses.py  (append)
import hashlib
import importlib.metadata
from pathlib import Path
from ..models import Dependency, ProjectModel
from .pyproject import parse_dependencies, parse_project_license


class _ImportlibLookup:
    """Default lookup adapting importlib.metadata to (expr, classifiers, license_field)."""
    def get(self, name):
        try:
            meta = importlib.metadata.metadata(name)
        except importlib.metadata.PackageNotFoundError:
            return None
        return (
            meta.get("License-Expression"),
            meta.get_all("Classifier") or [],
            meta.get("License"),
        )


def build_project_model(project_dir: str, dist_lookup=None) -> ProjectModel:
    lookup = dist_lookup if dist_lookup is not None else _ImportlibLookup()
    root = Path(project_dir)
    pyproject_text = (root / "pyproject.toml").read_text(encoding="utf-8")

    project_license = parse_project_license(pyproject_text)
    dep_names = parse_dependencies(pyproject_text)

    deps: list[Dependency] = []
    unscanned: list[dict[str, str]] = []
    for name in dep_names:
        entry = lookup.get(name)
        if entry is None:
            deps.append(Dependency(name=name, license="UNKNOWN"))
            unscanned.append({"file": f"dist:{name}", "reason": "package metadata not found"})
            continue
        expr, classifiers, license_field = entry
        deps.append(Dependency(name=name, license=license_from_metadata(expr, classifiers, license_field)))

    notice_present = any((root / fname).is_file() for fname in ("NOTICE", "NOTICE.txt", "NOTICE.md"))

    digest_input = "|".join(
        [project_license or ""] + sorted(f"{d.name}:{d.license}" for d in deps) + [str(notice_present)]
    )
    model_hash = hashlib.sha256(digest_input.encode()).hexdigest()[:16]

    return ProjectModel(
        hash=model_hash,
        root=str(root),
        project_license=project_license,
        dependencies=deps,
        notice_file_present=notice_present,
        unscanned=unscanned,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_licenses.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add src/compliance_agent/scanners/licenses.py tests/test_licenses.py
git commit -m "feat: build ProjectModel facts from a Python project"
```

---

## Task 6: Predicate evaluator (applies_when)

**Files:**
- Create: `src/compliance_agent/predicates.py`
- Test: `tests/test_predicates.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_predicates.py
from compliance_agent.models import Dependency, ProjectModel
from compliance_agent.predicates import evaluate_predicate


def model(project_license="MIT", dep_licenses=("Apache-2.0",), notice=False):
    return ProjectModel(
        hash="h", root="/p", project_license=project_license,
        dependencies=[Dependency(name=f"d{i}", license=l) for i, l in enumerate(dep_licenses)],
        notice_file_present=notice,
    )


def test_has_dep_license_true():
    assert evaluate_predicate({"has_dep_license": "Apache-2.0"}, model()) is True


def test_has_dep_license_false():
    assert evaluate_predicate({"has_dep_license": "GPL-3.0"}, model()) is False


def test_project_license_in():
    assert evaluate_predicate({"project_license_in": ["MIT", "BSD-3-Clause"]}, model()) is True


def test_dep_license_in():
    assert evaluate_predicate({"dep_license_in": ["Apache-2.0"]}, model()) is True


def test_notice_file_present_predicate():
    assert evaluate_predicate({"notice_file_present": False}, model(notice=False)) is True
    assert evaluate_predicate({"notice_file_present": False}, model(notice=True)) is False


def test_all_any_not_composition():
    pred = {"all": [
        {"has_dep_license": "Apache-2.0"},
        {"not": {"project_license_in": ["GPL-3.0", "AGPL-3.0"]}},
    ]}
    assert evaluate_predicate(pred, model()) is True
    assert evaluate_predicate({"any": [{"has_dep_license": "GPL-3.0"}]}, model()) is False


def test_unknown_predicate_raises():
    import pytest
    with pytest.raises(ValueError):
        evaluate_predicate({"bogus": 1}, model())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_predicates.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/compliance_agent/predicates.py
from __future__ import annotations
from typing import Any
from .models import ProjectModel


def evaluate_predicate(pred: dict[str, Any], model: ProjectModel) -> bool:
    """Safe, structured boolean evaluator over ProjectModel facts. No code eval."""
    if len(pred) != 1:
        raise ValueError(f"predicate must have exactly one key, got {list(pred)}")
    (op, value), = pred.items()

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

    raise ValueError(f"unknown predicate op: {op}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_predicates.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add src/compliance_agent/predicates.py tests/test_predicates.py
git commit -m "feat: safe structured applies_when predicate evaluator"
```

---

## Task 7: Policy Pack loader + checked-in `license-core.json`

**Files:**
- Create: `packs/license-core.json`, `src/compliance_agent/packs.py`
- Test: `tests/test_packs.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_packs.py
from compliance_agent.packs import load_pack, load_bundled_packs


def test_load_bundled_license_pack_validates():
    packs = load_bundled_packs()
    ids = {p.id for p in packs}
    assert "license-core" in ids
    pack = next(p for p in packs if p.id == "license-core")
    ob_ids = {o.id for o in pack.obligations}
    assert {"lic-gpl-incompat", "lic-apache-notice"} <= ob_ids
    # Every obligation carries a verbatim citation (spec invariant).
    for o in pack.obligations:
        assert o.source.clause_quote.strip()
        assert o.source.url_or_section.strip()


def test_load_pack_from_path(tmp_path):
    import json
    data = {
        "id": "p1", "domain": "license", "provenance": "public",
        "source_doc": "x", "source_version": "v1", "compiled_at": "2026-05-28",
        "obligations": [],
    }
    f = tmp_path / "p.json"
    f.write_text(json.dumps(data))
    pack = load_pack(str(f))
    assert pack.id == "p1" and pack.obligations == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_packs.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create `packs/license-core.json`**

```json
{
  "id": "license-core",
  "domain": "license",
  "provenance": "public",
  "source_doc": "spdx-license-rules",
  "source_version": "2026-05-28",
  "compiled_at": "2026-05-28",
  "obligations": [
    {
      "id": "lic-gpl-incompat",
      "domain": "license",
      "source": {
        "doc": "GPL-3.0",
        "provenance": "public",
        "version": "spdx-GPL-3.0",
        "clause_quote": "You may convey a covered work in object code form ... provided that you also convey ... the corresponding source under the terms of this License.",
        "url_or_section": "https://www.gnu.org/licenses/gpl-3.0.txt §5-6"
      },
      "applies_when": {
        "all": [
          {"any": [{"has_dep_license": "GPL-3.0"}, {"has_dep_license": "AGPL-3.0"}]},
          {"not": {"project_license_in": ["GPL-3.0", "AGPL-3.0"]}}
        ]
      },
      "requirement": "A non-(A)GPL project must not link copyleft (A)GPL-3.0 dependencies; doing so forces the whole work under (A)GPL.",
      "check": {
        "kind": "deterministic",
        "analyzer": "gpl_incompatibility",
        "params": {"incompatible_licenses": ["GPL-3.0", "AGPL-3.0"]}
      },
      "severity": "high",
      "fix": {
        "kind": "manual",
        "guidance": "Replace the copyleft dependency with a permissively-licensed alternative, or relicense the project under (A)GPL-3.0."
      }
    },
    {
      "id": "lic-apache-notice",
      "domain": "license",
      "source": {
        "doc": "Apache-2.0",
        "provenance": "public",
        "version": "spdx-Apache-2.0",
        "clause_quote": "You must retain, in the Source form of any Derivative Works that You distribute, all copyright, patent, trademark, and attribution notices ... and ... include a readable copy of the attribution notices contained within ... a NOTICE text file distributed as part of the Derivative Works.",
        "url_or_section": "https://www.apache.org/licenses/LICENSE-2.0 §4"
      },
      "applies_when": {
        "all": [
          {"dep_license_in": ["Apache-2.0"]},
          {"notice_file_present": false}
        ]
      },
      "requirement": "Projects bundling Apache-2.0 dependencies must ship a NOTICE file with attributions.",
      "check": {
        "kind": "deterministic",
        "analyzer": "missing_notice",
        "params": {"attribution_licenses": ["Apache-2.0"]}
      },
      "severity": "medium",
      "fix": {
        "kind": "auto",
        "codemod": "add_notice_entries",
        "guidance": "Create/extend a NOTICE file listing each Apache-2.0 dependency."
      }
    }
  ]
}
```

- [ ] **Step 4: Write minimal implementation**

```python
# src/compliance_agent/packs.py
from __future__ import annotations
import json
from pathlib import Path
from .models import PolicyPack

# packs/ lives at the repo root: src/compliance_agent/packs.py -> parents[2]/packs
_BUNDLED_DIR = Path(__file__).resolve().parents[2] / "packs"


def load_pack(path: str) -> PolicyPack:
    return PolicyPack.model_validate_json(Path(path).read_text(encoding="utf-8"))


def load_bundled_packs() -> list[PolicyPack]:
    return [load_pack(str(p)) for p in sorted(_BUNDLED_DIR.glob("*.json"))]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_packs.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add packs/license-core.json src/compliance_agent/packs.py tests/test_packs.py
git commit -m "feat: PolicyPack loader + checked-in license-core pack"
```

---

## Task 8: Deterministic analyzers + registry

**Files:**
- Create: `src/compliance_agent/analyzers/__init__.py`, `analyzers/gpl_incompatibility.py`, `analyzers/missing_notice.py`
- Test: `tests/test_analyzers.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_analyzers.py
from compliance_agent.models import Dependency, Obligation, ProjectModel, Source, Check, Fix
from compliance_agent.analyzers import ANALYZERS


def _obligation(analyzer, params):
    return Obligation(
        id="o", domain="license",
        source=Source(doc="d", provenance="public", version="v", clause_quote="q", url_or_section="s"),
        applies_when={}, requirement="r",
        check=Check(kind="deterministic", analyzer=analyzer, params=params),
        severity="high", fix=Fix(kind="manual", guidance="g"),
    )


def test_gpl_incompatibility_flags_each_offending_dep():
    model = ProjectModel(
        hash="h", root="/p", project_license="MIT",
        dependencies=[Dependency(name="gpllib", license="GPL-3.0"),
                      Dependency(name="ok", license="MIT")],
    )
    ob = _obligation("gpl_incompatibility", {"incompatible_licenses": ["GPL-3.0", "AGPL-3.0"]})
    ev = ANALYZERS["gpl_incompatibility"](ob, model)
    assert [e.snippet for e in ev] == ["gpllib (GPL-3.0)"]


def test_gpl_incompatibility_clean_when_no_copyleft():
    model = ProjectModel(hash="h", root="/p", project_license="MIT",
                         dependencies=[Dependency(name="ok", license="MIT")])
    ob = _obligation("gpl_incompatibility", {"incompatible_licenses": ["GPL-3.0"]})
    assert ANALYZERS["gpl_incompatibility"](ob, model) == []


def test_missing_notice_flags_when_apache_dep_and_no_notice():
    model = ProjectModel(hash="h", root="/p", project_license="MIT",
                         dependencies=[Dependency(name="apachelib", license="Apache-2.0")],
                         notice_file_present=False)
    ob = _obligation("missing_notice", {"attribution_licenses": ["Apache-2.0"]})
    ev = ANALYZERS["missing_notice"](ob, model)
    assert len(ev) == 1 and "apachelib" in ev[0].snippet


def test_missing_notice_clean_when_notice_present():
    model = ProjectModel(hash="h", root="/p", project_license="MIT",
                         dependencies=[Dependency(name="apachelib", license="Apache-2.0")],
                         notice_file_present=True)
    ob = _obligation("missing_notice", {"attribution_licenses": ["Apache-2.0"]})
    assert ANALYZERS["missing_notice"](ob, model) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_analyzers.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/compliance_agent/analyzers/gpl_incompatibility.py
from __future__ import annotations
from ..models import Evidence, Obligation, ProjectModel


def gpl_incompatibility(obligation: Obligation, model: ProjectModel) -> list[Evidence]:
    incompatible = set(obligation.check.params.get("incompatible_licenses", []))
    return [
        Evidence(file="pyproject.toml", line=None, snippet=f"{d.name} ({d.license})")
        for d in model.dependencies
        if d.license in incompatible
    ]
```

```python
# src/compliance_agent/analyzers/missing_notice.py
from __future__ import annotations
from ..models import Evidence, Obligation, ProjectModel


def missing_notice(obligation: Obligation, model: ProjectModel) -> list[Evidence]:
    if model.notice_file_present:
        return []
    needs = set(obligation.check.params.get("attribution_licenses", []))
    offenders = [d.name for d in model.dependencies if d.license in needs]
    if not offenders:
        return []
    return [Evidence(file="NOTICE", line=None,
                     snippet="missing attribution for: " + ", ".join(sorted(offenders)))]
```

```python
# src/compliance_agent/analyzers/__init__.py
from __future__ import annotations
from typing import Callable
from ..models import Evidence, Obligation, ProjectModel
from .gpl_incompatibility import gpl_incompatibility
from .missing_notice import missing_notice

Analyzer = Callable[[Obligation, ProjectModel], list[Evidence]]

ANALYZERS: dict[str, Analyzer] = {
    "gpl_incompatibility": gpl_incompatibility,
    "missing_notice": missing_notice,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_analyzers.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/compliance_agent/analyzers tests/test_analyzers.py
git commit -m "feat: deterministic license analyzers + registry"
```

---

## Task 9: Engine (match + evaluate → Findings)

**Files:**
- Create: `src/compliance_agent/engine.py`
- Test: `tests/test_engine.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_engine.py
from compliance_agent.engine import evaluate
from compliance_agent.models import Dependency, ProjectModel
from compliance_agent.packs import load_bundled_packs


def test_evaluate_flags_gpl_and_notice_violations():
    model = ProjectModel(
        hash="h", root="/p", project_license="MIT",
        dependencies=[Dependency(name="gpllib", license="GPL-3.0"),
                      Dependency(name="apachelib", license="Apache-2.0")],
        notice_file_present=False,
    )
    findings = evaluate(model, load_bundled_packs())
    by_id = {f.obligation_id: f for f in findings}

    assert "lic-gpl-incompat" in by_id
    assert by_id["lic-gpl-incompat"].status == "violation"
    assert by_id["lic-gpl-incompat"].confidence == 1.0
    assert by_id["lic-gpl-incompat"].citation["url_or_section"].startswith("https://www.gnu.org")
    assert by_id["lic-gpl-incompat"].remediation["kind"] == "manual"

    assert "lic-apache-notice" in by_id
    assert by_id["lic-apache-notice"].remediation["kind"] == "auto"


def test_evaluate_clean_project_has_no_findings():
    model = ProjectModel(
        hash="h", root="/p", project_license="MIT",
        dependencies=[Dependency(name="ok", license="MIT")],
        notice_file_present=True,
    )
    assert evaluate(model, load_bundled_packs()) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_engine.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/compliance_agent/engine.py
from __future__ import annotations
from .analyzers import ANALYZERS
from .models import Finding, Obligation, PolicyPack, ProjectModel
from .predicates import evaluate_predicate


def _finding_from(obligation: Obligation, evidence) -> Finding:
    if obligation.fix.kind == "auto":
        remediation = {"kind": "auto", "codemod": obligation.fix.codemod, "guidance": obligation.fix.guidance}
    else:
        remediation = {"kind": "manual", "guidance": obligation.fix.guidance}
    return Finding(
        obligation_id=obligation.id,
        domain=obligation.domain,
        severity=obligation.severity,
        status="violation",
        evidence=evidence,
        citation={"clause_quote": obligation.source.clause_quote,
                  "url_or_section": obligation.source.url_or_section},
        remediation=remediation,
        confidence=1.0,
    )


def evaluate(model: ProjectModel, packs: list[PolicyPack]) -> list[Finding]:
    findings: list[Finding] = []
    for pack in packs:
        for obligation in pack.obligations:
            if not evaluate_predicate(obligation.applies_when, model):
                continue
            if obligation.check.kind != "deterministic":
                # Tier-0 has no LLM: surface judgment obligations for human review.
                findings.append(Finding(
                    obligation_id=obligation.id, domain=obligation.domain,
                    severity=obligation.severity, status="needs_review", evidence=[],
                    citation={"clause_quote": obligation.source.clause_quote,
                              "url_or_section": obligation.source.url_or_section},
                    remediation={"kind": "manual", "guidance": obligation.fix.guidance},
                    confidence=0.0,
                ))
                continue
            analyzer = ANALYZERS.get(obligation.check.analyzer or "")
            if analyzer is None:
                raise ValueError(f"unknown analyzer: {obligation.check.analyzer}")
            evidence = analyzer(obligation, model)
            if evidence:
                findings.append(_finding_from(obligation, evidence))
    return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_engine.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/compliance_agent/engine.py tests/test_engine.py
git commit -m "feat: compliance engine match + evaluate"
```

---

## Task 10: Drift (baseline store + delta)

**Files:**
- Create: `src/compliance_agent/drift.py`
- Test: `tests/test_drift.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_drift.py
from compliance_agent.drift import finding_key, compute_drift, save_baseline, load_baseline
from compliance_agent.models import Baseline, Evidence, Finding


def _finding(ob_id, snippet):
    return Finding(obligation_id=ob_id, domain="license", severity="high", status="violation",
                   evidence=[Evidence(file="pyproject.toml", snippet=snippet)],
                   citation={"clause_quote": "q", "url_or_section": "s"},
                   remediation={"kind": "manual", "guidance": "g"}, confidence=1.0)


def test_finding_key_stable_and_distinct():
    a = _finding("lic-gpl-incompat", "gpllib (GPL-3.0)")
    b = _finding("lic-gpl-incompat", "otherlib (GPL-3.0)")
    assert finding_key(a) == finding_key(_finding("lic-gpl-incompat", "gpllib (GPL-3.0)"))
    assert finding_key(a) != finding_key(b)


def test_compute_drift_reports_new_and_resolved():
    base = Baseline(project_model_hash="h0", findings=[_finding("lic-gpl-incompat", "gpllib (GPL-3.0)")])
    current = [_finding("lic-apache-notice", "missing attribution for: apachelib")]
    delta = compute_drift(current, base)
    assert [f.obligation_id for f in delta["new"]] == ["lic-apache-notice"]
    assert [f.obligation_id for f in delta["resolved"]] == ["lic-gpl-incompat"]


def test_compute_drift_against_none_baseline_all_new():
    current = [_finding("lic-gpl-incompat", "gpllib (GPL-3.0)")]
    delta = compute_drift(current, None)
    assert len(delta["new"]) == 1 and delta["resolved"] == []


def test_baseline_roundtrip(tmp_path):
    path = tmp_path / "baseline.json"
    base = Baseline(project_model_hash="h1", policy_pack_versions={"license-core": "2026-05-28"},
                    findings=[_finding("lic-gpl-incompat", "gpllib (GPL-3.0)")])
    save_baseline(str(path), base)
    loaded = load_baseline(str(path))
    assert loaded == base
    assert load_baseline(str(tmp_path / "missing.json")) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_drift.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/compliance_agent/drift.py
from __future__ import annotations
from pathlib import Path
from typing import Optional
from .models import Baseline, Finding


def finding_key(f: Finding) -> str:
    snippets = "|".join(sorted(e.snippet for e in f.evidence))
    return f"{f.obligation_id}::{snippets}"


def compute_drift(current: list[Finding], baseline: Optional[Baseline]) -> dict[str, list[Finding]]:
    base_findings = baseline.findings if baseline else []
    base_keys = {finding_key(f) for f in base_findings}
    cur_keys = {finding_key(f) for f in current}
    new = [f for f in current if finding_key(f) not in base_keys]
    resolved = [f for f in base_findings if finding_key(f) not in cur_keys]
    return {"new": new, "resolved": resolved}


def save_baseline(path: str, baseline: Baseline) -> None:
    Path(path).write_text(baseline.model_dump_json(indent=2), encoding="utf-8")


def load_baseline(path: str) -> Optional[Baseline]:
    p = Path(path)
    if not p.is_file():
        return None
    return Baseline.model_validate_json(p.read_text(encoding="utf-8"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_drift.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/compliance_agent/drift.py tests/test_drift.py
git commit -m "feat: drift baseline storage and delta"
```

---

## Task 11: Remediation (NOTICE auto-fix)

**Files:**
- Create: `src/compliance_agent/remediation.py`
- Test: `tests/test_remediation.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_remediation.py
import pytest
from compliance_agent.models import Dependency, Evidence, Finding, ProjectModel
from compliance_agent.remediation import generate_notice_content, apply_fix


def _model(tmp_path, notice=False):
    if notice:
        (tmp_path / "NOTICE").write_text("Existing.\n")
    return ProjectModel(
        hash="h", root=str(tmp_path), project_license="MIT",
        dependencies=[Dependency(name="apachelib", license="Apache-2.0"),
                      Dependency(name="ok", license="MIT")],
        notice_file_present=notice,
    )


def _notice_finding():
    return Finding(obligation_id="lic-apache-notice", domain="license", severity="medium",
                   status="violation", evidence=[Evidence(file="NOTICE", snippet="missing")],
                   citation={"clause_quote": "q", "url_or_section": "s"},
                   remediation={"kind": "auto", "codemod": "add_notice_entries", "guidance": "g"},
                   confidence=1.0)


def test_generate_notice_lists_attribution_deps(tmp_path):
    content = generate_notice_content(_model(tmp_path), _notice_finding())
    assert "apachelib" in content and "Apache-2.0" in content
    assert "ok" not in content  # MIT dep not an attribution dep


def test_apply_fix_writes_notice_file(tmp_path):
    model = _model(tmp_path)
    path = apply_fix(model, _notice_finding())
    assert (tmp_path / "NOTICE").is_file()
    assert "apachelib" in (tmp_path / "NOTICE").read_text()
    assert path.endswith("NOTICE")


def test_apply_fix_refuses_manual_finding(tmp_path):
    model = _model(tmp_path)
    manual = _notice_finding()
    manual.remediation = {"kind": "manual", "guidance": "g"}
    with pytest.raises(ValueError):
        apply_fix(model, manual)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_remediation.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/compliance_agent/remediation.py
from __future__ import annotations
from pathlib import Path
from .models import Finding, ProjectModel

_ATTRIBUTION_LICENSES = {"Apache-2.0"}


def generate_notice_content(model: ProjectModel, finding: Finding) -> str:
    deps = sorted(d for d in model.dependencies if d.license in _ATTRIBUTION_LICENSES,
                  key=lambda d: d.name) if False else sorted(
        (d for d in model.dependencies if d.license in _ATTRIBUTION_LICENSES), key=lambda d: d.name)
    lines = ["NOTICE", "", "This product includes third-party software:"]
    for d in deps:
        lines.append(f"- {d.name} ({d.license})")
    return "\n".join(lines) + "\n"


def apply_fix(model: ProjectModel, finding: Finding) -> str:
    """Apply an AUTO fix. Deterministic auto-fixes only; manual findings are refused."""
    if finding.remediation.get("kind") != "auto":
        raise ValueError("apply_fix only handles deterministic auto fixes")
    codemod = finding.remediation.get("codemod")
    if codemod == "add_notice_entries":
        target = Path(model.root) / "NOTICE"
        target.write_text(generate_notice_content(model, finding), encoding="utf-8")
        return str(target)
    raise ValueError(f"unknown codemod: {codemod}")
```

> Note for the implementer: simplify the `deps =` line to the readable single comprehension below before committing — the `if False else` is an artifact:
> ```python
> deps = sorted((d for d in model.dependencies if d.license in _ATTRIBUTION_LICENSES), key=lambda d: d.name)
> ```

- [ ] **Step 4: Clean up the artifact line, then run tests**

Replace the `deps =` assignment with the single-line comprehension from the note above. Then run: `pytest tests/test_remediation.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/compliance_agent/remediation.py tests/test_remediation.py
git commit -m "feat: NOTICE auto-fix remediation (deterministic only)"
```

---

## Task 12: Report rendering (JSON + Markdown)

**Files:**
- Create: `src/compliance_agent/report.py`
- Test: `tests/test_report.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_report.py
import json
from compliance_agent.models import Evidence, Finding, ProjectModel
from compliance_agent.report import to_json, to_markdown


def _findings():
    return [Finding(obligation_id="lic-gpl-incompat", domain="license", severity="high",
                    status="violation", evidence=[Evidence(file="pyproject.toml", snippet="gpllib (GPL-3.0)")],
                    citation={"clause_quote": "You may convey...", "url_or_section": "GPL-3.0 §5"},
                    remediation={"kind": "manual", "guidance": "Replace dep."}, confidence=1.0)]


def test_to_json_is_parseable_and_complete():
    payload = json.loads(to_json(_findings(), ProjectModel(hash="h", root="/p")))
    assert payload["summary"]["violations"] == 1
    assert payload["findings"][0]["obligation_id"] == "lic-gpl-incompat"


def test_to_markdown_includes_citation_and_evidence():
    md = to_markdown(_findings(), unscanned=[{"file": "dist:x", "reason": "not found"}])
    assert "lic-gpl-incompat" in md
    assert "GPL-3.0 §5" in md          # citation present
    assert "gpllib (GPL-3.0)" in md    # evidence present
    assert "dist:x" in md              # unscanned surfaced, not hidden


def test_to_markdown_clean_project():
    assert "No compliance findings" in to_markdown([], unscanned=[])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_report.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/compliance_agent/report.py
from __future__ import annotations
import json
from typing import Optional
from .models import Finding, ProjectModel


def _summary(findings: list[Finding]) -> dict[str, int]:
    return {
        "violations": sum(1 for f in findings if f.status == "violation"),
        "needs_review": sum(1 for f in findings if f.status == "needs_review"),
    }


def to_json(findings: list[Finding], model: Optional[ProjectModel] = None) -> str:
    payload = {
        "summary": _summary(findings),
        "findings": [f.model_dump() for f in findings],
        "unscanned": model.unscanned if model else [],
    }
    return json.dumps(payload, indent=2)


def to_markdown(findings: list[Finding], unscanned: Optional[list[dict]] = None) -> str:
    unscanned = unscanned or []
    if not findings and not unscanned:
        return "# Compliance Report\n\nNo compliance findings. ✅\n"
    lines = ["# Compliance Report", "", f"**{_summary(findings)['violations']} violation(s)**", ""]
    for f in findings:
        lines += [f"## [{f.severity.upper()}] {f.obligation_id} ({f.status})",
                  f"- **Requirement source:** {f.citation['url_or_section']}",
                  f"- **Clause:** {f.citation['clause_quote']}",
                  f"- **Fix:** {f.remediation['kind']} — {f.remediation.get('guidance', '')}",
                  "- **Evidence:**"]
        lines += [f"  - `{e.file}`: {e.snippet}" for e in f.evidence]
        lines.append("")
    if unscanned:
        lines += ["## Unscanned (not evaluated)"]
        lines += [f"- `{u['file']}`: {u.get('reason', '')}" for u in unscanned]
        lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_report.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/compliance_agent/report.py tests/test_report.py
git commit -m "feat: JSON + Markdown report rendering"
```

---

## Task 13: CLI (`scan` / `fix`)

**Files:**
- Create: `src/compliance_agent/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
from compliance_agent.cli import main


def _write_project(tmp_path, deps, project_license="MIT"):
    dep_str = ", ".join(f'"{d}>=1.0"' for d in deps)
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname="demo"\nlicense="{project_license}"\ndependencies=[{dep_str}]\n'
    )


class _Lookup:
    def __init__(self, table): self.table = table
    def get(self, name): return self.table.get(name)


def test_scan_reports_violation_and_returns_nonzero(tmp_path, capsys):
    _write_project(tmp_path, ["apachelib"])
    lookup = _Lookup({"apachelib": ("Apache-2.0", [], None)})
    code = main(["scan", str(tmp_path)], dist_lookup=lookup)
    out = capsys.readouterr().out
    assert "lic-apache-notice" in out
    assert code == 1   # violations -> non-zero exit


def test_scan_clean_project_returns_zero(tmp_path, capsys):
    _write_project(tmp_path, ["ok"])
    code = main(["scan", str(tmp_path)], dist_lookup=_Lookup({"ok": (None, [], "MIT")}))
    assert code == 0
    assert "No compliance findings" in capsys.readouterr().out


def test_fix_apply_creates_notice_and_then_clean(tmp_path, capsys):
    _write_project(tmp_path, ["apachelib"])
    lookup = _Lookup({"apachelib": ("Apache-2.0", [], None)})
    fix_code = main(["fix", str(tmp_path), "--apply"], dist_lookup=lookup)
    assert (tmp_path / "NOTICE").is_file()
    assert fix_code == 0
    # Re-scan now clean for the notice obligation.
    assert main(["scan", str(tmp_path)], dist_lookup=lookup) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/compliance_agent/cli.py
from __future__ import annotations
import argparse
import sys
from typing import Optional, Sequence
from .engine import evaluate
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


def main(argv: Optional[Sequence[str]] = None, dist_lookup=None) -> int:
    parser = argparse.ArgumentParser(prog="compliance-agent")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="scan a project and report findings")
    p_scan.add_argument("path")
    p_scan.add_argument("--json", action="store_true")

    p_fix = sub.add_parser("fix", help="apply deterministic auto-fixes")
    p_fix.add_argument("path")
    p_fix.add_argument("--apply", action="store_true", help="write fixes (default: dry-run)")

    args = parser.parse_args(argv)

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

    return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/compliance_agent/cli.py tests/test_cli.py
git commit -m "feat: scan/fix CLI"
```

---

## Task 14: MCP server (FastMCP)

**Files:**
- Create: `src/compliance_agent/mcp_server.py`
- Test: `tests/test_mcp_server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mcp_server.py
from compliance_agent.mcp_server import scan_project, explain_obligation, list_policy_packs


def _write_project(tmp_path, deps, project_license="MIT"):
    dep_str = ", ".join(f'"{d}>=1.0"' for d in deps)
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname="demo"\nlicense="{project_license}"\ndependencies=[{dep_str}]\n'
    )


class _Lookup:
    def __init__(self, table): self.table = table
    def get(self, name): return self.table.get(name)


def test_scan_project_returns_structured_findings(tmp_path):
    _write_project(tmp_path, ["apachelib"])
    result = scan_project(str(tmp_path), dist_lookup=_Lookup({"apachelib": ("Apache-2.0", [], None)}))
    assert result["summary"]["violations"] == 1
    assert result["findings"][0]["obligation_id"] == "lic-apache-notice"


def test_explain_obligation_returns_citation():
    info = explain_obligation("lic-gpl-incompat")
    assert info["citation"]["url_or_section"].startswith("https://www.gnu.org")
    assert info["requirement"]


def test_list_policy_packs_includes_license_core():
    packs = list_policy_packs()
    assert any(p["id"] == "license-core" for p in packs)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mcp_server.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

The tool *functions* are plain, importable, and unit-testable; the FastMCP instance just registers them. (FastMCP 3.x: `@mcp.tool()` wraps a function and exposes it; we keep the underlying callables module-level so tests call them directly.)

```python
# src/compliance_agent/mcp_server.py
from __future__ import annotations
from typing import Any
from fastmcp import FastMCP
from .engine import evaluate
from .packs import load_bundled_packs
from .remediation import apply_fix as _apply_fix
from .report import to_json
from .scanners.licenses import build_project_model
import json

mcp = FastMCP("compliance-agent")


def scan_project(path: str, dist_lookup=None) -> dict[str, Any]:
    """Scan a project directory and return a structured compliance report."""
    model = build_project_model(path, dist_lookup=dist_lookup)
    findings = evaluate(model, load_bundled_packs())
    return json.loads(to_json(findings, model))


def explain_obligation(obligation_id: str) -> dict[str, Any]:
    """Return the requirement text and verbatim source citation for an obligation."""
    for pack in load_bundled_packs():
        for ob in pack.obligations:
            if ob.id == obligation_id:
                return {"requirement": ob.requirement, "severity": ob.severity,
                        "citation": {"clause_quote": ob.source.clause_quote,
                                     "url_or_section": ob.source.url_or_section}}
    return {"error": f"unknown obligation: {obligation_id}"}


def list_policy_packs() -> list[dict[str, Any]]:
    """List loaded Policy Packs with their domain, provenance, and version."""
    return [{"id": p.id, "domain": p.domain, "provenance": p.provenance,
             "version": p.source_version, "obligations": len(p.obligations)}
            for p in load_bundled_packs()]


def apply_fix_tool(path: str, obligation_id: str, confirm: bool = False) -> dict[str, Any]:
    """Apply a deterministic auto-fix for one finding. LLM-proposed fixes require confirm=True (none in Tier-0)."""
    model = build_project_model(path)
    findings = evaluate(model, load_bundled_packs())
    target = next((f for f in findings if f.obligation_id == obligation_id), None)
    if target is None:
        return {"error": f"no active finding for {obligation_id}"}
    if target.remediation.get("kind") != "auto":
        return {"error": "manual finding; not auto-applicable", "guidance": target.remediation.get("guidance")}
    written = _apply_fix(model, target)
    return {"applied": True, "path": written}


# Register tools with FastMCP (decorate the existing callables).
mcp.tool()(scan_project)
mcp.tool()(explain_obligation)
mcp.tool()(list_policy_packs)
mcp.tool(name="apply_fix")(apply_fix_tool)


def run() -> None:
    mcp.run()


if __name__ == "__main__":
    run()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_mcp_server.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Verify the server boots (smoke check)**

Run: `python -c "import compliance_agent.mcp_server as m; print(sorted(t.name for t in __import__('asyncio').get_event_loop().run_until_complete(m.mcp.get_tools())))"`
Expected: prints a list containing `apply_fix`, `explain_obligation`, `list_policy_packs`, `scan_project`.
(If the FastMCP 3.x tool-introspection API differs, fall back to: `python -c "import compliance_agent.mcp_server"` returning exit 0 — import without error is sufficient evidence the decorators applied.)

- [ ] **Step 6: Commit**

```bash
git add src/compliance_agent/mcp_server.py tests/test_mcp_server.py
git commit -m "feat: FastMCP server exposing scan/explain/list/apply_fix"
```

---

## Task 15: End-to-end test + README usage

**Files:**
- Create: `tests/test_end_to_end.py`
- Modify: `README.md`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_end_to_end.py
from compliance_agent.cli import main
from compliance_agent.drift import compute_drift, load_baseline, save_baseline
from compliance_agent.engine import evaluate
from compliance_agent.models import Baseline
from compliance_agent.packs import load_bundled_packs
from compliance_agent.scanners.licenses import build_project_model


class _Lookup:
    def __init__(self, table): self.table = table
    def get(self, name): return self.table.get(name)


def test_full_cycle_scan_fix_rescan_and_drift(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="demo"\nlicense="MIT"\n'
        'dependencies=["apachelib>=1.0","gpllib>=1.0"]\n'
    )
    lookup = _Lookup({
        "apachelib": ("Apache-2.0", [], None),
        "gpllib": (None, ["License :: OSI Approved :: GNU General Public License v3 (GPLv3)"], None),
    })

    # 1. Initial scan: both a GPL incompatibility and a missing-NOTICE violation.
    model = build_project_model(str(tmp_path), dist_lookup=lookup)
    findings = evaluate(model, load_bundled_packs())
    ids = {f.obligation_id for f in findings}
    assert ids == {"lic-gpl-incompat", "lic-apache-notice"}

    # Save baseline of the initial state.
    base_path = tmp_path / "baseline.json"
    save_baseline(str(base_path), Baseline(project_model_hash=model.hash, findings=findings))

    # 2. Auto-fix the NOTICE issue via the CLI.
    assert main(["fix", str(tmp_path), "--apply"], dist_lookup=lookup) == 0
    assert (tmp_path / "NOTICE").is_file()

    # 3. Re-scan: NOTICE resolved, GPL incompatibility remains (manual fix).
    model2 = build_project_model(str(tmp_path), dist_lookup=lookup)
    findings2 = evaluate(model2, load_bundled_packs())
    assert {f.obligation_id for f in findings2} == {"lic-gpl-incompat"}

    # 4. Drift vs baseline: the NOTICE finding is now resolved.
    delta = compute_drift(findings2, load_baseline(str(base_path)))
    assert [f.obligation_id for f in delta["resolved"]] == ["lic-apache-notice"]
    assert delta["new"] == []
```

- [ ] **Step 2: Run test to verify it fails (or passes if all wiring is correct)**

Run: `pytest tests/test_end_to_end.py -v`
Expected: PASS — if it fails, fix the wiring revealed (do not edit the test to match a bug).

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: all tests PASS (every test file green).

- [ ] **Step 4: Manual smoke test against a real project**

```bash
mkdir -p /tmp/demoproj && printf '[project]\nname="demoproj"\nlicense="MIT"\ndependencies=["fastmcp>=3.0"]\n' > /tmp/demoproj/pyproject.toml
compliance-agent scan /tmp/demoproj
```
Expected: a Markdown report printed (findings depend on `fastmcp`'s installed license metadata); command exits cleanly.

- [ ] **Step 5: Update README usage section**

Add a short "What it checks (Tier-0)" section to `README.md`:
```markdown
## What it checks (Tier-0)
- **GPL/AGPL incompatibility** — copyleft dependencies in a non-copyleft project (flagged, cited to GPL-3.0 §5-6).
- **Missing NOTICE** — Apache-2.0 dependencies without a NOTICE file (auto-fixed by `fix --apply`).

Every finding cites the exact source clause. Auto-fixes are applied **only** for deterministic
findings; nothing is changed without `fix --apply`.
```

- [ ] **Step 6: Commit**

```bash
git add tests/test_end_to_end.py README.md
git commit -m "test: end-to-end scan/fix/rescan/drift cycle + README usage"
```

---

## Self-Review (completed against the spec)

**1. Spec coverage (Tier-0 slice of spec §9 step 1):**
- Core data model (spec §2): Task 2 ✅ (full domain enum + `provenance` carried, even though Tier-0 only exercises `license`/`public`).
- Deterministic scanners → ProjectModel (spec §2.3): Tasks 3–5 ✅.
- PolicyPack + verbatim-citation invariant (spec §2.1–2.2): Task 7 ✅ (test asserts every obligation has a clause quote).
- Match + evaluate engine (spec §3): Task 9 ✅.
- Two-axis drift — *project* axis only in Tier-0 (upstream axis needs the compiler/corpus, deferred to Plan 2; spec §4): Task 10 ✅, documented as partial here.
- Remediation policy: deterministic auto-fix only, manual flagged (spec §5): Tasks 9 + 11 ✅ (`apply_fix` refuses manual; `--apply` gate).
- MCP surface subset (spec §7): Task 14 ✅ (`scan_project`, `explain_obligation`, `list_policy_packs`, `apply_fix`; `check_change`/`suggest_fix`/`refresh_corpus` deferred to later plans).
- Tier-0 local, no GCP (spec §8): entire plan — no cloud dependency ✅.
- Error handling: unscanned surfaced not hidden (spec §10): Tasks 5 + 12 ✅; offline = default (no network) ✅.
- Testing via planted-violation fixtures (spec §11): Tasks 8–15 ✅; end-to-end scan→fix→rescan→clean: Task 15 ✅.

**Deferred to later plans (intentional, not gaps):** LLM compiler + RAG corpus + upstream drift (Plan 2); AI-AUP/privacy/API-ToS domains (Plan 3); internal/B2B (Plan 4); Node/TS (Plan 5); `check_change`/`suggest_fix`/`refresh_corpus` MCP tools.

**2. Placeholder scan:** No `TODO`/`TBD`/"handle edge cases" left. The one artifact (`if False else` in Task 11) is explicitly flagged with a cleanup step before its commit.

**3. Type consistency:** `build_project_model(project_dir, dist_lookup=None)` signature consistent across Tasks 5/13/14/15. `evaluate(model, packs)`, `compute_drift(current, baseline)`, `apply_fix(model, finding)`, `ANALYZERS[name](obligation, model) -> list[Evidence]`, `Finding.remediation["kind"]` all used consistently. Predicate leaf ops (`has_dep_license`, `dep_license_in`, `project_license_in`, `notice_file_present`, `all`/`any`/`not`) match between `predicates.py` (Task 6) and `license-core.json` (Task 7).

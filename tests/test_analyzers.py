from compliance_agent.analyzers import ANALYZERS
from compliance_agent.models import Check, Dependency, Fix, Obligation, ProjectModel, Source


def _obligation(analyzer, params):
    return Obligation(
        id="o",
        domain="license",
        source=Source(
            doc="d", provenance="public", version="v", clause_quote="q", url_or_section="s"
        ),
        applies_when={},
        requirement="r",
        check=Check(kind="deterministic", analyzer=analyzer, params=params),
        severity="high",
        fix=Fix(kind="manual", guidance="g"),
    )


def test_gpl_incompatibility_flags_each_offending_dep():
    model = ProjectModel(
        hash="h",
        root="/p",
        project_license="MIT",
        dependencies=[
            Dependency(name="gpllib", license="GPL-3.0"),
            Dependency(name="ok", license="MIT"),
        ],
    )
    ob = _obligation("gpl_incompatibility", {"incompatible_licenses": ["GPL-3.0", "AGPL-3.0"]})
    ev = ANALYZERS["gpl_incompatibility"](ob, model)
    assert [e.snippet for e in ev] == ["gpllib (GPL-3.0)"]


def test_gpl_incompatibility_clean_when_no_copyleft():
    model = ProjectModel(
        hash="h",
        root="/p",
        project_license="MIT",
        dependencies=[Dependency(name="ok", license="MIT")],
    )
    ob = _obligation("gpl_incompatibility", {"incompatible_licenses": ["GPL-3.0"]})
    assert ANALYZERS["gpl_incompatibility"](ob, model) == []


def test_missing_notice_flags_when_apache_dep_and_no_notice():
    model = ProjectModel(
        hash="h",
        root="/p",
        project_license="MIT",
        dependencies=[Dependency(name="apachelib", license="Apache-2.0")],
        notice_file_present=False,
        notice_text=None,
    )
    ob = _obligation("missing_notice", {"attribution_licenses": ["Apache-2.0"]})
    ev = ANALYZERS["missing_notice"](ob, model)
    assert len(ev) == 1 and "apachelib" in ev[0].snippet


def test_missing_notice_yields_one_evidence_per_missing_dep():
    # Per-dep evidence keeps drift keys stable when a new offender is added.
    model = ProjectModel(
        hash="h",
        root="/p",
        project_license="MIT",
        dependencies=[
            Dependency(name="apachelib", license="Apache-2.0"),
            Dependency(name="anotherapache", license="Apache-2.0"),
        ],
        notice_file_present=False,
        notice_text=None,
    )
    ob = _obligation("missing_notice", {"attribution_licenses": ["Apache-2.0"]})
    ev = ANALYZERS["missing_notice"](ob, model)
    snippets = sorted(e.snippet for e in ev)
    assert snippets == [
        "missing attribution for: anotherapache",
        "missing attribution for: apachelib",
    ]


def test_missing_notice_clean_when_dep_already_attributed():
    model = ProjectModel(
        hash="h",
        root="/p",
        project_license="MIT",
        dependencies=[Dependency(name="apachelib", license="Apache-2.0")],
        notice_file_present=True,
        notice_text="NOTICE\n- apachelib (Apache-2.0)\n",
    )
    ob = _obligation("missing_notice", {"attribution_licenses": ["Apache-2.0"]})
    assert ANALYZERS["missing_notice"](ob, model) == []


def test_missing_notice_flags_new_dep_even_when_notice_exists():
    # Content-aware: a NOTICE exists but does not yet list the new Apache dep.
    model = ProjectModel(
        hash="h",
        root="/p",
        project_license="MIT",
        dependencies=[
            Dependency(name="apachelib", license="Apache-2.0"),
            Dependency(name="newapache", license="Apache-2.0"),
        ],
        notice_file_present=True,
        notice_text="NOTICE\n- apachelib (Apache-2.0)\n",
    )
    ob = _obligation("missing_notice", {"attribution_licenses": ["Apache-2.0"]})
    ev = ANALYZERS["missing_notice"](ob, model)
    assert len(ev) == 1 and "newapache" in ev[0].snippet and "apachelib" not in ev[0].snippet

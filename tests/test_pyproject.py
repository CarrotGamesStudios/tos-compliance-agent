from compliance_agent.scanners.pyproject import (
    normalize_license,
    parse_dependencies,
    parse_project_license,
)

OPTIONAL_DEPS = """
[project]
name = "demo"
license = "MIT"
dependencies = ["requests>=2.0"]

[project.optional-dependencies]
dev = ["pytest>=8.0", "requests>=2.0"]
docs = ["sphinx>=7"]
"""

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


def test_parse_dependencies_includes_optional_deduped():
    names = parse_dependencies(OPTIONAL_DEPS)
    assert names == ["requests", "pytest", "sphinx"]  # deduped, first-seen order


def test_parse_dependencies_can_exclude_optional():
    assert parse_dependencies(OPTIONAL_DEPS, include_optional=False) == ["requests"]


def test_normalize_license_canonicalizes_variants():
    assert normalize_license("GPL-3.0-or-later") == "GPL-3.0"
    assert normalize_license("Apache 2.0") == "Apache-2.0"
    assert normalize_license("MIT") == "MIT"  # already canonical, unchanged


def test_parse_project_license_normalizes():
    assert parse_project_license('[project]\nname="x"\nlicense="GPL-3.0-or-later"\n') == "GPL-3.0"

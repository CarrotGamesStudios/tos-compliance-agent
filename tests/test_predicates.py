import pytest

from compliance_agent.models import Dependency, ProjectModel
from compliance_agent.predicates import evaluate_predicate, validate_predicate


def model(project_license="MIT", dep_licenses=("Apache-2.0",), notice=False):
    return ProjectModel(
        hash="h",
        root="/p",
        project_license=project_license,
        dependencies=[Dependency(name=f"d{i}", license=lic) for i, lic in enumerate(dep_licenses)],
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
    pred = {
        "all": [
            {"has_dep_license": "Apache-2.0"},
            {"not": {"project_license_in": ["GPL-3.0", "AGPL-3.0"]}},
        ]
    }
    assert evaluate_predicate(pred, model()) is True
    assert evaluate_predicate({"any": [{"has_dep_license": "GPL-3.0"}]}, model()) is False


def test_unknown_predicate_raises():
    with pytest.raises(ValueError):
        evaluate_predicate({"bogus": 1}, model())


def test_validate_rejects_string_for_list_op():
    # The classic bug: a string instead of a list would become set("GPL-3.0") (chars).
    with pytest.raises(ValueError):
        validate_predicate({"dep_license_in": "GPL-3.0"})


def test_validate_rejects_empty_compound():
    with pytest.raises(ValueError):
        validate_predicate({"all": []})


def test_validate_rejects_non_bool_notice():
    with pytest.raises(ValueError):
        validate_predicate({"notice_file_present": "false"})


def test_validate_rejects_list_for_str_op():
    with pytest.raises(ValueError):
        validate_predicate({"has_dep_license": ["GPL-3.0"]})


def test_validate_accepts_well_formed_compound():
    validate_predicate(
        {"all": [{"dep_license_in": ["Apache-2.0"]}, {"not": {"has_dep_license": "MIT"}}]}
    )

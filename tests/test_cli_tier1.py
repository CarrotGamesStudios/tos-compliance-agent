import pytest

from compliance_agent.cli import build_tfvars, main, terraform_commands
from compliance_agent.errors import ProjectScanError


def test_build_tfvars_contains_all_vars():
    out = build_tfvars("my-proj", "us-central1", "my-bucket")
    assert 'project_id  = "my-proj"' in out
    assert 'location    = "us-central1"' in out
    assert 'bucket_name = "my-bucket"' in out
    assert "create_firestore = true" in out


def test_build_tfvars_can_skip_firestore():
    assert "create_firestore = false" in build_tfvars("p", "l", "b", create_firestore=False)


def test_init_no_create_firestore_flag(tmp_path):
    main(
        [
            "init", "--project", "p", "--bucket", "b",
            "--tf-dir", str(tmp_path), "--no-create-firestore",
        ]
    )
    assert "create_firestore = false" in (tmp_path / "terraform.tfvars").read_text()


def test_build_tfvars_rejects_hcl_injection():
    # Quotes / newlines / interpolation must not reach the HCL file.
    with pytest.raises(ProjectScanError):
        build_tfvars('p" \n malicious = "x', "us-central1", "bucket")
    with pytest.raises(ProjectScanError):
        build_tfvars("proj", "loc", 'b"${path.module}')
    with pytest.raises(ProjectScanError):
        build_tfvars("proj", "loc\nx=1", "bucket")


def test_terraform_commands_plan_vs_apply():
    plan = terraform_commands("deploy/terraform", apply=False)
    assert plan[0][:2] == ["terraform", "-chdir=deploy/terraform"]
    assert "plan" in plan[1] and "-auto-approve" not in plan[1]
    apply = terraform_commands("deploy/terraform", apply=True)
    assert "apply" in apply[1] and "-auto-approve" in apply[1]


def test_init_dry_run_writes_tfvars(tmp_path, capsys):
    code = main(["init", "--project", "p", "--bucket", "b", "--tf-dir", str(tmp_path)])
    assert code == 0
    tfvars = (tmp_path / "terraform.tfvars").read_text()
    assert 'project_id  = "p"' in tfvars
    assert "dry-run" in capsys.readouterr().out


def test_init_missing_tf_dir_errors(capsys):
    code = main(["init", "--project", "p", "--bucket", "b", "--tf-dir", "/no/such/dir"])
    assert code == 2
    assert "terraform dir not found" in capsys.readouterr().err

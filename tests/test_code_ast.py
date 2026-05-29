from compliance_agent.scanners.code_ast import identifier_pii_hit, scan_python_files


def test_identifier_pii_hit_components():
    assert identifier_pii_hit("email") == "email"
    assert identifier_pii_hit("user_email") == "email"
    assert identifier_pii_hit("passwordHash") == "password"
    assert identifier_pii_hit("social_security_number") == "social security"
    assert identifier_pii_hit("creditCardNumber") in {"credit card", "card number"}
    assert identifier_pii_hit("count") is None
    assert identifier_pii_hit("emailer") is None  # component is "emailer", not "email"


def test_scan_flags_pii_in_log_calls(tmp_path):
    (tmp_path / "app.py").write_text(
        "import logging\n"
        "import requests\n"
        "logger = logging.getLogger(__name__)\n"
        "def f(user_email, count):\n"
        "    logger.info('processing %s', user_email)\n"
        "    print(count)\n"
    )
    sites, imports, unscanned = scan_python_files(str(tmp_path))
    assert len(sites) == 1
    assert sites[0].file == "app.py" and sites[0].line == 5
    assert "email" in sites[0].snippet
    assert "requests" in imports and "logging" in imports
    assert unscanned == []


def test_scan_ignores_pii_outside_log_calls(tmp_path):
    (tmp_path / "m.py").write_text(
        "def store(password):\n    db.save(password)\n    return password\n"
    )
    sites, _, _ = scan_python_files(str(tmp_path))
    assert sites == []  # not inside a log/print call


def test_scan_when_root_is_under_skip_named_dir(tmp_path):
    # The project root itself lives under a dir literally named "build" — files must NOT be skipped.
    proj = tmp_path / "build" / "proj"
    proj.mkdir(parents=True)
    (proj / "app.py").write_text("import logging\ndef f(email):\n    logging.info(email)\n")
    sites, _, _ = scan_python_files(str(proj))
    assert len(sites) == 1 and "email" in sites[0].snippet


def test_scan_skips_venv_and_reports_unscanned(tmp_path):
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "junk.py").write_text("print(email)\n")  # must be skipped
    (tmp_path / "bad.py").write_text("def (:\n")  # syntax error
    sites, _, unscanned = scan_python_files(str(tmp_path))
    assert sites == []
    assert any(u["file"] == "bad.py" for u in unscanned)

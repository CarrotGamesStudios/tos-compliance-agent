import pytest

from compliance_agent.errors import ProjectScanError
from compliance_agent.safety import ensure_within, resolve_root


def test_resolve_root_rejects_missing_dir(tmp_path):
    with pytest.raises(ProjectScanError):
        resolve_root(str(tmp_path / "nope"))


def test_ensure_within_allows_child(tmp_path):
    out = ensure_within(tmp_path, tmp_path / "NOTICE")
    assert str(out).endswith("NOTICE")


def test_ensure_within_blocks_parent_escape(tmp_path):
    with pytest.raises(ProjectScanError):
        ensure_within(tmp_path, tmp_path / ".." / "evil")


def test_ensure_within_blocks_symlink_escape(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "NOTICE").symlink_to(outside / "evil.txt")
    with pytest.raises(ProjectScanError):
        ensure_within(root, root / "NOTICE")

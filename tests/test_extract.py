import pytest

from compliance_agent.errors import ProjectScanError
from compliance_agent.sources.extract import extract_text


def test_text_file_is_utf8_decoded():
    assert extract_text("doc.txt", b"hello world") == "hello world"
    assert extract_text("policy.md", "héllo".encode()) == "héllo"


def test_pdf_dispatches_to_extractor():
    calls = {}

    def fake_pdf(data):
        calls["data"] = data
        return "extracted contract text"

    out = extract_text("contract.pdf", b"%PDF-1.7 ...", pdf_extractor=fake_pdf)
    assert out == "extracted contract text"
    assert calls["data"] == b"%PDF-1.7 ..."


def test_pdf_uppercase_extension_dispatches():
    out = extract_text("Contract.PDF", b"x", pdf_extractor=lambda d: "ok")
    assert out == "ok"


def test_pdf_missing_dep_raises_clean_error():
    def missing(data):
        raise ImportError("No module named 'pypdf'")

    with pytest.raises(ProjectScanError) as exc:
        extract_text("c.pdf", b"x", pdf_extractor=missing)
    assert "pip install" in str(exc.value)


def test_pdf_extractor_failure_is_wrapped():
    def boom(data):
        raise ValueError("corrupt pdf")

    with pytest.raises(ProjectScanError):
        extract_text("c.pdf", b"x", pdf_extractor=boom)


def test_bad_utf8_text_raises_clean_error():
    with pytest.raises(ProjectScanError):
        extract_text("doc.txt", b"\xff\xfe\x00bad")

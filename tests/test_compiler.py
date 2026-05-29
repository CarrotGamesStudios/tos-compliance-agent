from compliance_agent.compiler import clause_in_source, compile_document
from compliance_agent.compiler.schema import (
    CompiledObligation,
    CompiledSource,
    CompilerOutput,
)
from compliance_agent.config import DEFAULT_MODEL
from compliance_agent.models import Check, Fix
from compliance_agent.packs import load_pack, save_pack

DOC = (
    "Section 4. You must retain all attribution notices in a NOTICE file. "
    "Section 5. You may convey covered works under this License."
)


class FakeModelClient:
    def __init__(self, output):
        self.output = output
        self.calls = []

    def generate_structured(self, *, prompt, schema, model):
        self.calls.append({"model": model, "schema": schema.__name__})
        return self.output


def _ob(ob_id, quote, applies_when, analyzer="missing_notice"):
    return CompiledObligation(
        id=ob_id,
        domain="license",
        source=CompiledSource(clause_quote=quote, url_or_section="§4"),
        applies_when=applies_when,
        requirement="r",
        check=Check(
            kind="deterministic",
            analyzer=analyzer,
            params={"attribution_licenses": ["Apache-2.0"]},
        ),
        severity="medium",
        fix=Fix(kind="auto", codemod="add_notice_entries", guidance="g"),
    )


# ── clause verification ──


def test_clause_in_source_verbatim():
    assert clause_in_source("retain all attribution notices", DOC) is True


def test_clause_in_source_case_and_whitespace_insensitive():
    assert clause_in_source("RETAIN   all\nattribution notices", DOC) is True


def test_clause_in_source_with_ellipsis_in_order():
    assert clause_in_source("You must retain ... in a NOTICE file", DOC) is True


def test_clause_in_source_out_of_order_fails():
    assert clause_in_source("NOTICE file ... You must retain", DOC) is False


def test_clause_in_source_absent_fails():
    assert clause_in_source("this text is nowhere in the document", DOC) is False


def test_clause_in_source_unicode_ellipsis():
    assert clause_in_source("You must retain … in a NOTICE file", DOC) is True


def test_clause_in_source_rejects_distant_stitching():
    # Two legitimate phrases that DO appear, but far apart — must NOT be accepted as one clause.
    doc = "Alpha beta gamma delta. " + ("filler words here " * 60) + "omega psi chi tau."
    assert clause_in_source("Alpha beta gamma delta ... omega psi chi tau", doc) is False


def test_clause_in_source_rejects_too_many_fragments():
    quote = "Section 4 ... You must ... retain all ... attribution ... in a NOTICE"
    assert clause_in_source(quote, DOC) is False  # >4 fragments


def test_clause_in_source_rejects_tiny_elided_fragments():
    # Short stitched tokens ("You", "in") must be rejected when elided.
    assert clause_in_source("You ... NOTICE file", DOC) is False


def test_clause_in_source_rejects_too_short_single_fragment():
    assert clause_in_source("you", DOC) is False  # below global min content length


def test_clause_in_source_backtracks_to_valid_later_occurrence():
    # First fragment appears early; the only VALID tight match is later. Anchored search must
    # not greedily fail on the early occurrence (regression for the agy round-2 finding).
    doc = (
        "retain notices here at the start. "
        + ("padding padding padding " * 40)
        + "retain notices and include a NOTICE file together."
    )
    assert clause_in_source("retain notices ... include a NOTICE file", doc) is True


# ── compile_document ──


def test_compile_keeps_valid_drops_unverified_and_invalid():
    out = CompilerOutput(
        obligations=[
            _ob("d-1", "You must retain all attribution notices in a NOTICE file",
                {"dep_license_in": ["Apache-2.0"]}),
            _ob("d-2", "a clause that does not appear in the document at all",
                {"dep_license_in": ["Apache-2.0"]}),
            # invalid applies_when (string instead of list) -> dropped at validation
            _ob("d-3", "You may convey covered works", {"dep_license_in": "Apache-2.0"}),
        ]
    )
    client = FakeModelClient(out)
    pack, dropped = compile_document(
        doc_text=DOC, doc_id="apache-notice", domain="license",
        model_client=client, url_base="https://example.test", compiled_at="2026-05-28",
    )
    assert [o.id for o in pack.obligations] == ["d-1"]
    reasons = {d["id"]: d["reason"] for d in dropped}
    assert "not found" in reasons["d-2"]
    assert "applies_when" in reasons["d-3"]
    # version is the content hash; provenance + citation stamped by us
    assert pack.source_version and pack.obligations[0].source.provenance == "public"
    assert pack.obligations[0].source.version == pack.source_version
    assert client.calls[0]["model"] == DEFAULT_MODEL


def test_compiled_pack_roundtrips_and_passes_pack_validation(tmp_path):
    out = CompilerOutput(
        obligations=[
            _ob("d-1", "retain all attribution notices", {"dep_license_in": ["Apache-2.0"]})
        ]
    )
    pack, _ = compile_document(
        doc_text=DOC, doc_id="apache-notice", domain="license",
        model_client=FakeModelClient(out), compiled_at="2026-05-28",
    )
    path = save_pack(str(tmp_path), pack)
    reloaded = load_pack(path)  # load_pack re-validates predicates
    assert reloaded.id == "apache-notice"
    assert reloaded.obligations[0].source.clause_quote

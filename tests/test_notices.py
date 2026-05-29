from compliance_agent.notices import attributed_names


def test_parses_entry_lines():
    text = "NOTICE\n\nThis product includes:\n- apachelib (Apache-2.0)\n- mpllib (MPL-2.0)\n"
    assert attributed_names(text) == {"apachelib", "mpllib"}


def test_prose_mention_is_not_an_attribution():
    # A dep name appearing only in prose must NOT count as a listed attribution.
    text = "NOTICE\n\nCopyright 2026 apachelib authors. All rights reserved.\n"
    assert attributed_names(text) == set()


def test_none_and_empty():
    assert attributed_names(None) == set()
    assert attributed_names("") == set()


def test_parses_scoped_npm_names():
    # Scoped npm packages (@scope/name) must be recognized as attribution entries so the
    # content-aware missing_notice check sees them as already attributed.
    text = "NOTICE\n- @aws-sdk/client-s3 (Apache-2.0)\n- @google/genai (Apache-2.0)\n"
    assert attributed_names(text) == {"@aws-sdk/client-s3", "@google/genai"}

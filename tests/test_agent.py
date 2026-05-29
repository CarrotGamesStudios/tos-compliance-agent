import pytest

from compliance_agent.agent import AGENT_INSTRUCTION, build_root_agent


def test_agent_instruction_is_substantive():
    assert "scan_project" in AGENT_INSTRUCTION
    assert "cite" in AGENT_INSTRUCTION.lower()


def test_build_root_agent_requires_gcp_extra():
    # google-adk is a [gcp] extra; base install must not need it. If it's installed, the agent
    # builds; otherwise build_root_agent raises ImportError (proving the lazy guard works).
    try:
        import google.adk  # noqa: F401
    except ImportError:
        with pytest.raises(ImportError):
            build_root_agent()
    else:  # pragma: no cover - only when [gcp] is installed
        agent = build_root_agent()
        assert agent.name == "compliance_agent"


def test_agent_entrypoint_module_imports_without_adk():
    # Importing the deploy entrypoint must NOT import google.adk (lazy via __getattr__).
    import compliance_agent.agent.agent as entry

    try:
        import google.adk  # noqa: F401
    except ImportError:
        with pytest.raises(ImportError):
            _ = entry.root_agent  # access triggers the lazy build -> ImportError without [gcp]
    else:  # pragma: no cover - only when [gcp] is installed
        assert entry.root_agent.name == "compliance_agent"


def test_agent_entrypoint_unknown_attr_raises_attributeerror():
    import compliance_agent.agent.agent as entry

    with pytest.raises(AttributeError):
        _ = entry.nonexistent_attr

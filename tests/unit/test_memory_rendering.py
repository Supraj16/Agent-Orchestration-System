from orchestrator.memory.long_term import MemoryExtraction, _render_summary


def test_render_summary_includes_all_populated_fields():
    extraction = MemoryExtraction(
        what_was_asked="compare two frameworks",
        approach_that_worked="searched then wrote a report",
        tools_used=["web_search", "write_file"],
        facts_discovered=["fact one", "fact two"],
        user_preferences_observed=["prefers concise bullet points"],
    )
    summary = _render_summary(extraction)

    assert "compare two frameworks" in summary
    assert "searched then wrote a report" in summary
    assert "web_search, write_file" in summary
    assert "fact one; fact two" in summary
    assert "prefers concise bullet points" in summary


def test_render_summary_omits_empty_optional_fields():
    extraction = MemoryExtraction(
        what_was_asked="simple request",
        approach_that_worked="direct answer",
    )
    summary = _render_summary(extraction)

    assert "Tools used" not in summary
    assert "Facts discovered" not in summary
    assert "User preferences" not in summary

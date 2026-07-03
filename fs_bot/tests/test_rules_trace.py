"""Rules traceability gate: every numbered rule section in the Reference
Documents is either cited somewhere in fs_bot source or allow-listed as
not applicable (with a reason) in tools/rules_trace.py. New sections, or
citations lost in refactors, fail here."""

from fs_bot.tools.rules_trace import (parse_sections, citation_census,
                                      unaccounted, NOT_APPLICABLE)


def test_reference_documents_parse():
    sections = parse_sections()
    assert len(sections) > 250
    assert "3.2.4" in sections and "A8.7.4" in sections


def test_every_rule_section_accounted_for():
    missing = unaccounted()
    assert missing == [], (
        "Rule sections neither cited in source nor allow-listed: "
        f"{missing}")


def test_allowlist_entries_are_real_and_uncited():
    """The N/A list must not rot: every entry exists in the documents and
    is genuinely uncited (a newly-cited section should leave the list)."""
    sections, hits = citation_census()
    for sec in NOT_APPLICABLE:
        assert sec in sections, sec
        assert not hits[sec], f"{sec} is now cited — drop it from the list"

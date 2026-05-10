"""Tests for core/schema.py — dataclass round-trips."""
from __future__ import annotations

import pytest
from citation_audit.core.schema import (
    AssertionRecord,
    AuditIndex,
    CitationRecord,
)


class TestCitationRecord:
    def test_to_dict_contains_all_fields(self):
        rec = CitationRecord(
            bibtex_label="smith2020",
            reference_text="Smith 2020",
            confirmation_type="direct",
            score=75,
            score_reason="good match",
            assertion_type="asserted-fact",
            bib_mismatches=["journal: A → B"],
        )
        d = rec.to_dict()
        assert d["bibtex_label"] == "smith2020"
        assert d["score"] == 75
        assert d["confirmation_type"] == "direct"
        assert d["bib_mismatches"] == ["journal: A → B"]
        assert d["assertion_type"] == "asserted-fact"

    def test_round_trip(self):
        original = CitationRecord(
            bibtex_label="jones1999",
            score=-100,
            confirmation_type="none",
            assertion_type="original-synthesis",
        )
        restored = CitationRecord.from_dict(original.to_dict())
        assert restored.bibtex_label == original.bibtex_label
        assert restored.score == original.score
        assert restored.assertion_type == original.assertion_type

    def test_from_dict_defaults(self):
        rec = CitationRecord.from_dict({"bibtex_label": "x"})
        assert rec.score == 0
        assert rec.confirmation_type == "none"
        assert rec.assertion_type == "asserted-fact"
        assert rec.bib_mismatches == []


class TestAssertionRecord:
    def test_to_dict_contains_all_fields(self):
        rec = AssertionRecord(
            id="a-abc12345",
            text="Enzyme X has a Km of 70 mM.",
            location="line ~42",
            assertion_type="asserted-fact",
            citation_label=None,
            needs_citation=True,
        )
        d = rec.to_dict()
        assert d["id"] == "a-abc12345"
        assert d["needs_citation"] is True
        assert d["assertion_type"] == "asserted-fact"
        assert d["citation_label"] is None

    def test_round_trip(self):
        original = AssertionRecord(
            id="a-deadbeef",
            text="We propose a framework.",
            location="line ~10",
            assertion_type="own-contribution",
            needs_citation=False,
            notes="author's contribution",
        )
        restored = AssertionRecord.from_dict(original.to_dict())
        assert restored.id == original.id
        assert restored.assertion_type == original.assertion_type
        assert restored.notes == original.notes

    def test_from_dict_defaults(self):
        rec = AssertionRecord.from_dict({"id": "a-1", "text": "hi", "location": ""})
        assert rec.assertion_type == "unknown"
        assert rec.needs_citation is False
        assert rec.citation_label is None


class TestAuditIndex:
    def test_empty_index_round_trip(self):
        idx = AuditIndex(document="foo.tex", audit_date="2026-05-10")
        restored = AuditIndex.from_dict(idx.to_dict())
        assert restored.document == "foo.tex"
        assert restored.citations == {}
        assert restored.assertions == {}

    def test_round_trip_with_records(self):
        idx = AuditIndex(document="doc.tex", audit_date="2026-05-10")
        idx.citations["key1"] = CitationRecord(bibtex_label="key1", score=90)
        idx.assertions["a-00"] = AssertionRecord(
            id="a-00", text="some text", location="line ~1",
            assertion_type="narrative",
        )
        restored = AuditIndex.from_dict(idx.to_dict())
        assert "key1" in restored.citations
        assert restored.citations["key1"].score == 90
        assert "a-00" in restored.assertions
        assert restored.assertions["a-00"].assertion_type == "narrative"

"""Tests for core/index.py — atomic read/write and patch operations."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from citation_audit.core import index as idx_mod
from citation_audit.core.schema import AssertionRecord, CitationRecord


class TestLoad:
    def test_returns_blank_index_when_no_file(self, tmp_path: Path):
        doc = tmp_path / "new.tex"
        doc.write_text("")
        idx = idx_mod.load(doc)
        assert idx.document == "new.tex"
        assert idx.citations == {}
        assert idx.assertions == {}

    def test_loads_existing_index(self, tmp_doc_with_index: Path):
        idx = idx_mod.load(tmp_doc_with_index)
        assert "smith2020" in idx.citations
        assert idx.citations["smith2020"].score == 90


class TestSave:
    def test_creates_directory_and_file(self, tmp_path: Path):
        doc = tmp_path / "sub" / "doc.tex"
        doc.parent.mkdir()
        doc.write_text("")
        from citation_audit.core.schema import AuditIndex
        idx = AuditIndex(document="doc.tex", audit_date="2026-05-10")
        idx_mod.save(doc, idx)
        index_file = tmp_path / "sub" / ".audit" / "doc" / "index.json"
        assert index_file.exists()
        data = json.loads(index_file.read_text())
        assert data["document"] == "doc.tex"

    def test_overwrites_existing_file(self, tmp_doc_with_index: Path):
        idx = idx_mod.load(tmp_doc_with_index)
        idx.citations["smith2020"].score = 50
        idx_mod.save(tmp_doc_with_index, idx)
        reloaded = idx_mod.load(tmp_doc_with_index)
        assert reloaded.citations["smith2020"].score == 50


class TestUpsertCitation:
    def test_inserts_new_citation(self, tmp_path: Path):
        doc = tmp_path / "doc.tex"
        doc.write_text("")
        rec = CitationRecord(bibtex_label="new_key", score=75, confirmation_type="direct")
        idx_mod.upsert_citation(doc, rec)
        reloaded = idx_mod.load(doc)
        assert "new_key" in reloaded.citations
        assert reloaded.citations["new_key"].score == 75

    def test_replaces_existing_citation(self, tmp_doc_with_index: Path):
        rec = CitationRecord(bibtex_label="smith2020", score=100, confirmation_type="direct")
        idx_mod.upsert_citation(tmp_doc_with_index, rec)
        reloaded = idx_mod.load(tmp_doc_with_index)
        assert reloaded.citations["smith2020"].score == 100


class TestUpsertAssertion:
    def test_inserts_assertion(self, tmp_path: Path):
        doc = tmp_path / "doc.tex"
        doc.write_text("")
        rec = AssertionRecord(
            id="a-aabbccdd",
            text="Enzyme X has a Km.",
            location="line ~5",
            assertion_type="asserted-fact",
            needs_citation=True,
        )
        idx_mod.upsert_assertion(doc, rec)
        reloaded = idx_mod.load(doc)
        assert "a-aabbccdd" in reloaded.assertions
        assert reloaded.assertions["a-aabbccdd"].needs_citation is True


class TestPatchCitation:
    def test_patches_score_only(self, tmp_doc_with_index: Path):
        rec = idx_mod.patch_citation(tmp_doc_with_index, "smith2020", score=-100)
        assert rec.score == -100
        # Other fields unchanged
        assert rec.confirmation_type == "direct"

    def test_patches_multiple_fields(self, tmp_doc_with_index: Path):
        idx_mod.patch_citation(
            tmp_doc_with_index, "smith2020",
            score=50,
            confirmation_type="indirect",
            assertion_type="narrative",
        )
        reloaded = idx_mod.load(tmp_doc_with_index)
        rec = reloaded.citations["smith2020"]
        assert rec.score == 50
        assert rec.confirmation_type == "indirect"
        assert rec.assertion_type == "narrative"

    def test_raises_key_error_for_missing_label(self, tmp_doc_with_index: Path):
        with pytest.raises(KeyError, match="nonexistent"):
            idx_mod.patch_citation(tmp_doc_with_index, "nonexistent", score=0)


class TestPatchAssertion:
    def test_raises_key_error_for_missing_id(self, tmp_path: Path):
        doc = tmp_path / "doc.tex"
        doc.write_text("")
        with pytest.raises(KeyError, match="a-missing"):
            idx_mod.patch_assertion(doc, "a-missing", assertion_type="narrative")

    def test_patches_assertion_type(self, tmp_path: Path):
        doc = tmp_path / "doc.tex"
        doc.write_text("")
        rec = AssertionRecord(
            id="a-11223344",
            text="We present our framework.",
            location="line ~1",
            assertion_type="unknown",
        )
        idx_mod.upsert_assertion(doc, rec)
        idx_mod.patch_assertion(doc, "a-11223344", assertion_type="own-contribution")
        reloaded = idx_mod.load(doc)
        assert reloaded.assertions["a-11223344"].assertion_type == "own-contribution"

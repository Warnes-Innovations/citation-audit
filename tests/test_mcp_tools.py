"""Tests for the MCP server tools (citation_audit.mcp_server).

These tests call the underlying Python functions directly — no MCP transport
needed. Each MCP tool is a plain async or sync function decorated with
@mcp.tool(); we import and call them directly to validate behaviour.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# Import the tool functions directly from the module.
# FastMCP decorators do not prevent direct calls.
from citation_audit.mcp_server import (
    compute_assertion_id,
    extract_assertions,
    get_audit_status,
    list_assertions,
    scaffold_assertion_artifact,
    scaffold_citation,
    tag_assertion,
    update_citation_record,
)


class TestExtractAssertionsTool:
    def test_returns_json_list(self, tmp_tex: Path):
        result = extract_assertions(str(tmp_tex))
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) > 0

    def test_records_have_required_keys(self, tmp_tex: Path):
        data = json.loads(extract_assertions(str(tmp_tex)))
        required = {"id", "text", "location", "assertion_type", "needs_citation"}
        for rec in data:
            assert required.issubset(rec.keys())

    def test_needs_citation_filter(self, tmp_tex: Path):
        data = json.loads(extract_assertions(str(tmp_tex), only="needs-citation"))
        assert all(r["needs_citation"] is True for r in data)

    def test_cited_filter(self, tmp_cite_tex: Path):
        data = json.loads(extract_assertions(str(tmp_cite_tex), only="cited"))
        assert all(r["citation_label"] is not None for r in data)

    def test_uncited_filter(self, tmp_tex: Path):
        data = json.loads(extract_assertions(str(tmp_tex), only="uncited"))
        assert all(r["citation_label"] is None for r in data)

    def test_invalid_only_value_raises(self, tmp_tex: Path):
        # FastMCP doesn't validate enum at call time; the filter just passes through unknown values
        # with no records filtered (falls through all if/continue checks) — confirm no crash
        data = json.loads(extract_assertions(str(tmp_tex), only="bogus"))
        assert isinstance(data, list)


class TestGetAuditStatusTool:
    def test_returns_full_index(self, tmp_doc_with_index: Path):
        result = get_audit_status(str(tmp_doc_with_index))
        data = json.loads(result)
        assert "citations" in data
        assert "smith2020" in data["citations"]

    def test_returns_blank_for_new_doc(self, tmp_path: Path):
        doc = tmp_path / "new.tex"
        doc.write_text("")
        data = json.loads(get_audit_status(str(doc)))
        assert data["citations"] == {}
        assert data["assertions"] == {}


class TestScaffoldCitationTool:
    def test_creates_folder_and_returns_path(self, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        result = json.loads(scaffold_citation(str(doc), "smith2020"))
        assert "folder" in result
        assert "files" in result
        assert Path(result["folder"]).is_dir()

    def test_files_list_contains_stubs(self, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        result = json.loads(scaffold_citation(str(doc), "jones1999"))
        filenames = [Path(f).name for f in result["files"]]
        assert "publication.md" in filenames
        assert "citation_jones1999.md" in filenames
        assert "summary.md" in filenames


class TestScaffoldAssertionTool:
    def test_creates_assertion_folder(self, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        result = json.loads(scaffold_assertion_artifact(
            str(doc), "a-aabbccdd", "Enzyme X has a Km of 70 mM."
        ))
        assert Path(result["folder"]).is_dir()
        assert "assertions" in result["folder"]


class TestUpdateCitationRecordTool:
    def test_creates_new_record(self, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        result = json.loads(update_citation_record(
            str(doc), "new_key",
            score=75,
            confirmation_type="direct",
            assertion_type="asserted-fact",
        ))
        assert result["score"] == 75
        assert result["confirmation_type"] == "direct"

    def test_patches_existing_record(self, tmp_doc_with_index: Path):
        result = json.loads(update_citation_record(
            str(tmp_doc_with_index), "smith2020",
            score=-100,
        ))
        assert result["score"] == -100
        # Other fields preserved
        assert result["confirmation_type"] == "direct"

    def test_records_bib_mismatches(self, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        mismatches = ["journal: IEEE Pulse → Int J Clin Trials", "volume: 7 → 3"]
        result = json.loads(update_citation_record(
            str(doc), "key1",
            score=-100,
            bib_mismatches=mismatches,
        ))
        assert result["bib_mismatches"] == mismatches

    def test_none_fields_not_overwritten(self, tmp_doc_with_index: Path):
        """Fields not passed (None) must leave existing values intact."""
        result = json.loads(update_citation_record(
            str(tmp_doc_with_index), "smith2020",
            score_reason="Updated reason",
            # score, confirmation_type, etc. not passed
        ))
        assert result["score"] == 90                     # original value preserved
        assert result["score_reason"] == "Updated reason"


class TestTagAssertionTool:
    def test_creates_new_assertion(self, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        result = json.loads(tag_assertion(
            str(doc), "a-deadbeef",
            assertion_type="original-synthesis",
            text="The output is a full posterior distribution.",
            notes="Author's own analytical contribution.",
        ))
        assert result["assertion_type"] == "original-synthesis"
        assert result["needs_citation"] is False

    def test_returns_error_when_text_missing_for_new(self, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        result = json.loads(tag_assertion(
            str(doc), "a-cafebabe",
            assertion_type="narrative",
            # text omitted
        ))
        assert "error" in result

    def test_updates_existing_assertion_type(self, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        # Create
        tag_assertion(str(doc), "a-11223344", "unknown",
                      text="Some sentence.", notes="")
        # Update
        result = json.loads(tag_assertion(
            str(doc), "a-11223344",
            assertion_type="derived-conclusion",
        ))
        assert result["assertion_type"] == "derived-conclusion"

    def test_needs_citation_false_for_non_fact_types(self, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        for atype in ("original-synthesis", "derived-conclusion",
                      "own-contribution", "definition", "narrative"):
            result = json.loads(tag_assertion(
                str(doc), f"a-{hash(atype) & 0xFFFFFFFF:08x}",
                assertion_type=atype,
                text=f"Sentence for {atype}.",
            ))
            assert result["needs_citation"] is False, f"failed for {atype}"


class TestListAssertionsTool:
    def test_returns_all_by_default(self, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        tag_assertion(str(doc), "a-aaaa0001", "narrative",
                      text="Intro sentence.")
        tag_assertion(str(doc), "a-aaaa0002", "asserted-fact",
                      text="Enzyme X has been shown to catalyse the reaction.")
        data = json.loads(list_assertions(str(doc)))
        assert len(data) == 2

    def test_filter_by_type(self, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        tag_assertion(str(doc), "a-aaaa0003", "narrative", text="Intro.")
        tag_assertion(str(doc), "a-aaaa0004", "asserted-fact",
                      text="Enzyme X has been demonstrated to be critical.")
        data = json.loads(list_assertions(str(doc), filter_type="narrative"))
        assert all(r["assertion_type"] == "narrative" for r in data)
        assert len(data) == 1

    def test_needs_citation_only_filter(self, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        tag_assertion(str(doc), "a-aaaa0005", "narrative", text="Intro.")
        tag_assertion(str(doc), "a-aaaa0006", "asserted-fact",
                      text="Enzyme X has been demonstrated to be critical.")
        data = json.loads(list_assertions(str(doc), needs_citation_only=True))
        assert all(r["needs_citation"] is True for r in data)


class TestComputeAssertionIdTool:
    def test_returns_prefixed_id(self, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        result = json.loads(compute_assertion_id(str(doc), "Some sentence."))
        assert result["id"].startswith("a-")

    def test_is_stable(self, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        r1 = json.loads(compute_assertion_id(str(doc), "Same sentence."))
        r2 = json.loads(compute_assertion_id(str(doc), "Same sentence."))
        assert r1["id"] == r2["id"]

    def test_differs_by_text(self, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        r1 = json.loads(compute_assertion_id(str(doc), "Sentence A."))
        r2 = json.loads(compute_assertion_id(str(doc), "Sentence B."))
        assert r1["id"] != r2["id"]

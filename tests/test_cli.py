"""Tests for the CLI entry point (citation_audit.cli)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from citation_audit.cli import main


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


class TestExtractCommand:
    def test_extract_returns_json_by_default(self, runner: CliRunner, tmp_tex: Path):
        result = runner.invoke(main, ["extract", str(tmp_tex)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) > 0

    def test_extract_records_have_required_keys(self, runner: CliRunner, tmp_tex: Path):
        result = runner.invoke(main, ["extract", str(tmp_tex)])
        data = json.loads(result.output)
        required = {"id", "text", "location", "assertion_type", "needs_citation"}
        for rec in data:
            assert required.issubset(rec.keys())

    def test_extract_table_format(self, runner: CliRunner, tmp_tex: Path):
        result = runner.invoke(main, ["extract", str(tmp_tex), "--format", "table"])
        assert result.exit_code == 0
        assert "TYPE" in result.output

    def test_extract_needs_citation_filter(self, runner: CliRunner, tmp_tex: Path):
        result = runner.invoke(main, ["extract", str(tmp_tex), "--only", "needs-citation"])
        data = json.loads(result.output)
        # Every returned record must need a citation
        assert all(r["needs_citation"] is True for r in data)

    def test_extract_cited_filter_has_citation_label(self, runner: CliRunner, tmp_cite_tex: Path):
        result = runner.invoke(main, ["extract", str(tmp_cite_tex), "--only", "cited"])
        data = json.loads(result.output)
        assert all(r["citation_label"] is not None for r in data)

    def test_extract_uncited_filter_has_no_citation_label(self, runner: CliRunner, tmp_tex: Path):
        result = runner.invoke(main, ["extract", str(tmp_tex), "--only", "uncited"])
        data = json.loads(result.output)
        assert all(r["citation_label"] is None for r in data)

    def test_extract_nonexistent_file_exits_nonzero(self, runner: CliRunner, tmp_path: Path):
        result = runner.invoke(main, ["extract", str(tmp_path / "missing.tex")])
        assert result.exit_code != 0


class TestScaffoldCommand:
    def test_scaffold_creates_folder(self, runner: CliRunner, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        result = runner.invoke(main, ["scaffold", str(doc), "smith2020"])
        assert result.exit_code == 0
        assert (tmp_path / ".audit" / "paper" / "smith2020").is_dir()

    def test_scaffold_output_contains_path(self, runner: CliRunner, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        result = runner.invoke(main, ["scaffold", str(doc), "jones1999"])
        assert "jones1999" in result.output


class TestScaffoldAssertionCommand:
    def test_scaffold_assertion_creates_folder(self, runner: CliRunner, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        result = runner.invoke(main, [
            "scaffold-assertion", str(doc), "a-aabbccdd",
            "--text", "Enzyme X has a Km of 70 mM.",
        ])
        assert result.exit_code == 0
        assert (tmp_path / ".audit" / "paper" / "assertions" / "a-aabbccdd").is_dir()


class TestUpdateCitationCommand:
    def test_creates_new_citation_record(self, runner: CliRunner, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        result = runner.invoke(main, [
            "update-citation", str(doc), "new_key",
            "--score", "75",
            "--confirmation", "direct",
            "--assertion-type", "asserted-fact",
            "--score-reason", "Good match.",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["score"] == 75
        assert data["confirmation_type"] == "direct"

    def test_patches_existing_citation(self, runner: CliRunner, tmp_doc_with_index: Path):
        result = runner.invoke(main, [
            "update-citation", str(tmp_doc_with_index), "smith2020",
            "--score", "-100",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["score"] == -100
        # confirmation_type preserved
        assert data["confirmation_type"] == "direct"

    def test_bib_mismatch_recorded(self, runner: CliRunner, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        result = runner.invoke(main, [
            "update-citation", str(doc), "key1",
            "--score", "-100",
            "--bib-mismatch", "journal: IEEE Pulse → Int J Clin Trials",
            "--bib-mismatch", "volume: 7 → 3",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["bib_mismatches"]) == 2


class TestTagAssertionCommand:
    def test_creates_new_assertion(self, runner: CliRunner, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        result = runner.invoke(main, [
            "tag-assertion", str(doc), "a-deadbeef",
            "--type", "original-synthesis",
            "--text", "The output is a full posterior distribution.",
            "--notes", "Author's own analytical contribution.",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["assertion_type"] == "original-synthesis"
        assert data["needs_citation"] is False

    def test_missing_text_for_new_assertion_fails(self, runner: CliRunner, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        result = runner.invoke(main, [
            "tag-assertion", str(doc), "a-cafebabe",
            "--type", "narrative",
            # --text intentionally omitted
        ])
        assert result.exit_code != 0

    def test_updates_existing_assertion(self, runner: CliRunner, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        # Create first
        runner.invoke(main, [
            "tag-assertion", str(doc), "a-11223344",
            "--type", "unknown",
            "--text", "Some sentence.",
        ])
        # Update
        result = runner.invoke(main, [
            "tag-assertion", str(doc), "a-11223344",
            "--type", "derived-conclusion",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["assertion_type"] == "derived-conclusion"


class TestListCommand:
    def test_list_table_format(self, runner: CliRunner, tmp_doc_with_index: Path):
        result = runner.invoke(main, ["list", str(tmp_doc_with_index)])
        assert result.exit_code == 0
        assert "smith2020" in result.output

    def test_list_json_format(self, runner: CliRunner, tmp_doc_with_index: Path):
        result = runner.invoke(main, ["list", str(tmp_doc_with_index), "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "citations" in data
        assert "smith2020" in data["citations"]

    def test_list_citations_only(self, runner: CliRunner, tmp_doc_with_index: Path):
        result = runner.invoke(main, [
            "list", str(tmp_doc_with_index), "--what", "citations", "--format", "json"
        ])
        data = json.loads(result.output)
        assert "citations" in data
        assert "assertions" not in data

    def test_list_assertions_only(self, runner: CliRunner, tmp_doc_with_index: Path):
        result = runner.invoke(main, [
            "list", str(tmp_doc_with_index), "--what", "assertions", "--format", "json"
        ])
        data = json.loads(result.output)
        assert "assertions" in data
        assert "citations" not in data


class TestReportCommand:
    def test_report_markdown_contains_summary_header(self, runner: CliRunner,
                                                      tmp_doc_with_index: Path):
        result = runner.invoke(main, ["report", str(tmp_doc_with_index)])
        assert result.exit_code == 0
        assert "# Audit Report" in result.output
        assert "smith2020" in result.output

    def test_report_json_format(self, runner: CliRunner, tmp_doc_with_index: Path):
        result = runner.invoke(main, ["report", str(tmp_doc_with_index), "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["document"] == "mydoc.tex"

"""Tests for core/scaffold.py — stub artifact folder creation."""
from __future__ import annotations

from pathlib import Path

import pytest
from citation_audit.core import scaffold as scf


class TestScaffoldCitation:
    def test_creates_folder(self, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        folder = scf.scaffold_citation(doc, "smith2020")
        assert folder.is_dir()
        assert folder.name == "smith2020"

    def test_creates_required_stubs(self, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        folder = scf.scaffold_citation(doc, "jones1999")
        assert (folder / "publication.md").exists()
        assert (folder / "citation_jones1999.md").exists()
        assert (folder / "summary.md").exists()

    def test_does_not_overwrite_existing_files(self, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        folder = scf.scaffold_citation(doc, "key1")
        pub = folder / "publication.md"
        pub.write_text("custom content")
        # Call again — should not overwrite
        scf.scaffold_citation(doc, "key1")
        assert pub.read_text() == "custom content"

    def test_publication_stub_contains_label(self, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        folder = scf.scaffold_citation(doc, "viceconti2016")
        content = (folder / "publication.md").read_text()
        assert "viceconti2016" in content

    def test_nested_audit_dir_created(self, tmp_path: Path):
        doc = tmp_path / "subdir" / "paper.tex"
        doc.parent.mkdir()
        doc.write_text("")
        folder = scf.scaffold_citation(doc, "key1")
        assert (tmp_path / "subdir" / ".audit" / "paper" / "key1").is_dir()


class TestScaffoldAssertion:
    def test_creates_assertion_folder(self, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        folder = scf.scaffold_assertion(doc, "a-aabbccdd", "Enzyme X has a Km of 70 mM.")
        assert folder.is_dir()
        assert (folder / "assertion.md").exists()

    def test_assertion_stub_contains_text(self, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        text = "Clinical trials have demonstrated efficacy."
        folder = scf.scaffold_assertion(doc, "a-00112233", text)
        content = (folder / "assertion.md").read_text()
        assert text in content

    def test_does_not_overwrite_existing_assertion(self, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        scf.scaffold_assertion(doc, "a-deadbeef", "Original text.")
        folder = tmp_path / ".audit" / "paper" / "assertions" / "a-deadbeef"
        custom = folder / "assertion.md"
        custom.write_text("my notes")
        scf.scaffold_assertion(doc, "a-deadbeef", "Different text.")
        assert custom.read_text() == "my notes"

    def test_folder_path_under_assertions(self, tmp_path: Path):
        doc = tmp_path / "paper.tex"
        doc.write_text("")
        folder = scf.scaffold_assertion(doc, "a-cafebabe", "Some claim.")
        assert "assertions" in folder.parts

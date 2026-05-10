"""Tests for core/extractor.py — LaTeX parsing and sentence splitting."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from citation_audit.core.extractor import assertion_id, extract_sentences


class TestAssertionId:
    def test_returns_prefixed_id(self):
        aid = assertion_id("mydoc", "Some sentence.")
        assert aid.startswith("a-")
        assert len(aid) == 10  # "a-" + 8 hex chars

    def test_is_stable(self):
        aid1 = assertion_id("doc", "Enzyme X has a Km of 70 mM.")
        aid2 = assertion_id("doc", "Enzyme X has a Km of 70 mM.")
        assert aid1 == aid2

    def test_differs_by_doc_stem(self):
        aid1 = assertion_id("doc_a", "Same sentence.")
        aid2 = assertion_id("doc_b", "Same sentence.")
        assert aid1 != aid2

    def test_differs_by_text(self):
        aid1 = assertion_id("doc", "Sentence A.")
        aid2 = assertion_id("doc", "Sentence B.")
        assert aid1 != aid2


class TestExtractSentences:
    def _write(self, tmp_path: Path, content: str) -> Path:
        p = tmp_path / "test.tex"
        p.write_text(content)
        return p

    def test_returns_list_of_sentences(self, tmp_tex: Path):
        sentences = extract_sentences(tmp_tex)
        assert isinstance(sentences, list)
        assert len(sentences) > 0

    def test_citation_markers_extracted(self, tmp_path: Path):
        tex = textwrap.dedent(r"""
            \begin{document}
            Studies have demonstrated improved outcomes \citep{oates1999_ARfail}.
            \end{document}
        """)
        p = self._write(tmp_path, tex)
        sentences = extract_sentences(p)
        cited = [s for s in sentences if s.citations]
        assert len(cited) >= 1
        assert "oates1999_ARfail" in cited[0].citations

    def test_multi_cite_flattened(self, tmp_path: Path):
        tex = textwrap.dedent(r"""
            \begin{document}
            This is confirmed by multiple studies \citep{jones2019,lee2021}.
            \end{document}
        """)
        p = self._write(tmp_path, tex)
        sentences = extract_sentences(p)
        cited = [s for s in sentences if s.citations]
        assert len(cited) >= 1
        assert "jones2019" in cited[0].citations
        assert "lee2021" in cited[0].citations

    def test_removes_figure_environment(self, tmp_path: Path):
        tex = textwrap.dedent(r"""
            \begin{document}
            This sentence is visible.
            \begin{figure}
            Caption text that should be removed.
            \end{figure}
            Another visible sentence follows.
            \end{document}
        """)
        p = self._write(tmp_path, tex)
        sentences = extract_sentences(p)
        texts = " ".join(s.text for s in sentences)
        assert "Caption text" not in texts

    def test_removes_equation_environment(self, tmp_path: Path):
        tex = textwrap.dedent(r"""
            \begin{document}
            The equation below defines the model.
            \begin{equation}
            x = \frac{a}{b}
            \end{equation}
            The parameters are estimated by least squares.
            \end{document}
        """)
        p = self._write(tmp_path, tex)
        sentences = extract_sentences(p)
        texts = " ".join(s.text for s in sentences)
        assert r"\frac" not in texts

    def test_strips_comments(self, tmp_path: Path):
        tex = textwrap.dedent(r"""
            \begin{document}
            This is a real sentence. % This is a comment that should be removed.
            \end{document}
        """)
        p = self._write(tmp_path, tex)
        sentences = extract_sentences(p)
        texts = " ".join(s.text for s in sentences)
        assert "comment" not in texts

    def test_short_fragments_excluded(self, tmp_path: Path):
        tex = textwrap.dedent(r"""
            \begin{document}
            Hi.
            This is a proper sentence with enough content to pass the length filter.
            \end{document}
        """)
        p = self._write(tmp_path, tex)
        sentences = extract_sentences(p)
        assert all(len(s.text) >= 20 for s in sentences)

    def test_line_numbers_are_positive(self, tmp_tex: Path):
        sentences = extract_sentences(tmp_tex)
        assert all(s.line >= 1 for s in sentences)

    def test_paragraph_index_increases(self, tmp_tex: Path):
        sentences = extract_sentences(tmp_tex)
        para_indices = [s.paragraph for s in sentences]
        assert para_indices == sorted(para_indices)

    def test_latex_command_stripped_from_text(self, tmp_path: Path):
        tex = textwrap.dedent(r"""
            \begin{document}
            The \textbf{enzyme} has been shown to catalyse the reaction in vivo.
            \end{document}
        """)
        p = self._write(tmp_path, tex)
        sentences = extract_sentences(p)
        assert len(sentences) >= 1
        assert r"\textbf" not in sentences[0].text
        assert "enzyme" in sentences[0].text

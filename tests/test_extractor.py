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


class TestExtractSentencesMarkdown:
    def _write(self, tmp_path: Path, content: str, name: str = "test.md") -> Path:
        p = tmp_path / name
        p.write_text(textwrap.dedent(content))
        return p

    def test_pandoc_citation_extracted(self, tmp_path: Path):
        p = self._write(tmp_path, """
            Studies have demonstrated improved outcomes [@smith2020].
        """)
        sentences = extract_sentences(p)
        cited = [s for s in sentences if s.citations]
        assert len(cited) >= 1
        assert "smith2020" in cited[0].citations

    def test_pandoc_multi_citation_flattened(self, tmp_path: Path):
        p = self._write(tmp_path, """
            This is confirmed by multiple studies [@jones2019; @lee2021].
        """)
        sentences = extract_sentences(p)
        cited = [s for s in sentences if s.citations]
        assert len(cited) >= 1
        assert "jones2019" in cited[0].citations
        assert "lee2021" in cited[0].citations

    def test_suppressed_author_citation(self, tmp_path: Path):
        p = self._write(tmp_path, """
            The method was introduced in 2018 [-@brown2018] and has since been widely adopted.
        """)
        sentences = extract_sentences(p)
        cited = [s for s in sentences if s.citations]
        assert len(cited) >= 1
        assert "brown2018" in cited[0].citations

    def test_footnote_citation_extracted(self, tmp_path: Path):
        p = self._write(tmp_path, """
            Neural networks achieve high accuracy on this benchmark.[^lecun1998]
            This sentence is long enough to pass the length filter and be included.
        """)
        sentences = extract_sentences(p)
        cited = [s for s in sentences if s.citations]
        assert len(cited) >= 1
        assert "lecun1998" in cited[0].citations

    def test_yaml_front_matter_removed(self, tmp_path: Path):
        p = self._write(tmp_path, """
            ---
            title: My Document
            author: Jane Doe
            ---

            This is the body of the document, which is a real sentence.
        """)
        sentences = extract_sentences(p)
        texts = " ".join(s.text for s in sentences)
        assert "title" not in texts
        assert "Jane Doe" not in texts
        assert "body" in texts

    def test_fenced_code_block_removed(self, tmp_path: Path):
        p = self._write(tmp_path, """
            The algorithm is implemented as follows.

            ```python
            def secret_internal_logic(): pass
            ```

            The implementation details are omitted here for brevity.
        """)
        sentences = extract_sentences(p)
        texts = " ".join(s.text for s in sentences)
        assert "secret_internal_logic" not in texts

    def test_heading_kept_as_sentence(self, tmp_path: Path):
        p = self._write(tmp_path, """
            ## Results and Discussion
        """)
        sentences = extract_sentences(p)
        texts = " ".join(s.text for s in sentences)
        assert "Results and Discussion" in texts
        assert "#" not in texts

    def test_inline_formatting_stripped(self, tmp_path: Path):
        p = self._write(tmp_path, """
            The **primary outcome** was a *statistically significant* improvement in accuracy.
        """)
        sentences = extract_sentences(p)
        assert len(sentences) >= 1
        assert "**" not in sentences[0].text
        assert "*" not in sentences[0].text
        assert "primary outcome" in sentences[0].text

    def test_image_removed(self, tmp_path: Path):
        p = self._write(tmp_path, """
            The results are shown below.
            ![Figure 1: Accuracy over epochs](figures/accuracy.png)
            Performance improved monotonically across all training epochs tested.
        """)
        sentences = extract_sentences(p)
        texts = " ".join(s.text for s in sentences)
        assert "figures/accuracy.png" not in texts
        assert "Figure 1" not in texts

    def test_link_text_kept_url_removed(self, tmp_path: Path):
        p = self._write(tmp_path, """
            More details are available in the supplementary materials provided online.
        """)
        sentences = extract_sentences(p)
        texts = " ".join(s.text for s in sentences)
        assert "http" not in texts

    def test_unsupported_suffix_raises(self, tmp_path: Path):
        import pytest
        p = tmp_path / "document.rst"
        p.write_text("Some content.")
        with pytest.raises(ValueError, match="Unsupported file type"):
            extract_sentences(p)

    def test_markdown_suffix_variants(self, tmp_path: Path):
        """Both .md and .markdown suffixes are accepted."""
        content = "This sentence is long enough to be included in extraction results.\n"
        for suffix in (".md", ".markdown"):
            p = tmp_path / f"doc{suffix}"
            p.write_text(content)
            sentences = extract_sentences(p)
            assert len(sentences) >= 1


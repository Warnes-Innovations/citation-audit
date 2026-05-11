"""Tests for citation_audit.core.library."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from citation_audit.core.library import (
    MAX_FILE_BYTES,
    CitingRef,
    LibraryEntry,
    _fetch_with_cap,
    add_citing_doc,
    doi_slug,
    download_paper,
    get_entry,
    library_json_path,
    library_root,
    load_library,
    papers_dir,
    save_library,
    sha256_of_file,
    store_paper,
    upsert_entry,
)


# ---------------------------------------------------------------------------
# doi_slug
# ---------------------------------------------------------------------------

class TestDoiSlug:
    def test_slash_becomes_double_underscore(self):
        assert doi_slug("10.1038/s41586-021-03819-2") == "10.1038__s41586-021-03819-2"

    def test_alphanumeric_unchanged(self):
        assert doi_slug("10.1000-abc") == "10.1000-abc"

    def test_special_chars_replaced(self):
        slug = doi_slug("10.1234/a b+c")
        for ch in (" ", "/", "+"):
            assert ch not in slug


# ---------------------------------------------------------------------------
# CitingRef.from_dict / to_dict
# ---------------------------------------------------------------------------

class TestCitingRef:
    def test_round_trip_with_github(self):
        ref = CitingRef(path="doc.tex", github="Owner/repo")
        assert CitingRef.from_dict(ref.to_dict()) == ref

    def test_round_trip_local(self):
        ref = CitingRef(path="doc.tex", local_path="/abs/path/doc.tex")
        assert CitingRef.from_dict(ref.to_dict()) == ref

    def test_from_doc_path_detects_github(self, tmp_path):
        """When git returns a GitHub remote, CitingRef should carry it."""
        doc = tmp_path / "paper.tex"
        doc.write_text("hello")

        def fake_run(cmd, **kw):
            m = MagicMock()
            if "rev-parse" in cmd:
                m.returncode = 0
                m.stdout = str(tmp_path) + "\n"
            elif "remote" in cmd:
                m.returncode = 0
                m.stdout = "https://github.com/OwnerX/repoY.git\n"
            else:
                m.returncode = 1
                m.stdout = ""
            return m

        with patch("citation_audit.core.library.subprocess.run", side_effect=fake_run):
            ref = CitingRef.from_doc_path(doc)

        assert ref.github == "OwnerX/repoY"
        assert ref.path == "paper.tex"
        assert ref.local_path is None

    def test_from_doc_path_fallback_no_git(self, tmp_path):
        """When git is absent (returncode != 0), falls back to absolute path."""
        doc = tmp_path / "my.tex"
        doc.write_text("x")

        def fake_run(cmd, **kw):
            m = MagicMock()
            m.returncode = 1
            m.stdout = ""
            return m

        with patch("citation_audit.core.library.subprocess.run", side_effect=fake_run):
            ref = CitingRef.from_doc_path(doc)

        assert ref.github is None
        assert ref.local_path == str(doc)
        assert ref.path == "my.tex"


# ---------------------------------------------------------------------------
# LibraryEntry serialization
# ---------------------------------------------------------------------------

class TestLibraryEntry:
    def test_round_trip_full(self):
        entry = LibraryEntry(
            doi="10.1/test",
            title="Test Paper",
            authors=["Alice", "Bob"],
            year=2024,
            journal="Test Journal",
            source_type="open_access_pdf",
            filename="10.1__test.pdf",
            sha256="abc123",
            citing_docs=[CitingRef(path="doc.tex", github="A/B")],
        )
        reloaded = LibraryEntry.from_dict(entry.to_dict())
        assert reloaded.doi == entry.doi
        assert reloaded.authors == entry.authors
        assert reloaded.citing_docs[0].github == "A/B"

    def test_empty_fields_omitted(self):
        entry = LibraryEntry(doi="10.x/y")
        d = entry.to_dict()
        assert "title" not in d
        assert "authors" not in d
        assert "citing_docs" not in d


# ---------------------------------------------------------------------------
# load_library / save_library
# ---------------------------------------------------------------------------

class TestLibraryJson:
    def test_missing_file_returns_empty(self, tmp_path):
        assert load_library(tmp_path) == {}

    def test_round_trip(self, tmp_path):
        entries = {
            "10.1/a": LibraryEntry(doi="10.1/a", title="A"),
            "10.1/b": LibraryEntry(doi="10.1/b", title="B"),
        }
        save_library(tmp_path, entries)
        loaded = load_library(tmp_path)
        assert set(loaded.keys()) == {"10.1/a", "10.1/b"}
        assert loaded["10.1/a"].title == "A"

    def test_atomic_write_creates_file(self, tmp_path):
        entries = {"10.x/y": LibraryEntry(doi="10.x/y")}
        save_library(tmp_path, entries)
        assert library_json_path(tmp_path).exists()


# ---------------------------------------------------------------------------
# upsert_entry
# ---------------------------------------------------------------------------

class TestUpsertEntry:
    def test_insert_new(self, tmp_path):
        upsert_entry(tmp_path, LibraryEntry(doi="10.1/new", title="New"))
        assert get_entry(tmp_path, "10.1/new") is not None

    def test_replace_existing(self, tmp_path):
        upsert_entry(tmp_path, LibraryEntry(doi="10.1/x", title="Old"))
        upsert_entry(tmp_path, LibraryEntry(doi="10.1/x", title="New"))
        assert get_entry(tmp_path, "10.1/x").title == "New"

    def test_no_doi_uses_sha256_key(self, tmp_path):
        entry = LibraryEntry(sha256="deadbeef" * 8, title="NoDOI")
        upsert_entry(tmp_path, entry)
        loaded = load_library(tmp_path)
        assert "sha256:deadbeef" * 8 in loaded or any(
            "sha256:" in k for k in loaded
        )

    def test_missing_doi_and_sha256_raises(self, tmp_path):
        with pytest.raises(ValueError):
            upsert_entry(tmp_path, LibraryEntry(title="No key"))


# ---------------------------------------------------------------------------
# add_citing_doc
# ---------------------------------------------------------------------------

class TestAddCitingDoc:
    def test_adds_ref(self, tmp_path):
        upsert_entry(tmp_path, LibraryEntry(doi="10.x/y", title="T"))
        ref = CitingRef(path="doc.tex", github="A/B")
        add_citing_doc(tmp_path, "10.x/y", ref)
        entry = get_entry(tmp_path, "10.x/y")
        assert len(entry.citing_docs) == 1
        assert entry.citing_docs[0].github == "A/B"

    def test_idempotent(self, tmp_path):
        upsert_entry(tmp_path, LibraryEntry(doi="10.x/z"))
        ref = CitingRef(path="doc.tex")
        add_citing_doc(tmp_path, "10.x/z", ref)
        add_citing_doc(tmp_path, "10.x/z", ref)
        entry = get_entry(tmp_path, "10.x/z")
        assert len(entry.citing_docs) == 1

    def test_unknown_doi_raises(self, tmp_path):
        with pytest.raises(KeyError):
            add_citing_doc(tmp_path, "10.x/missing", CitingRef(path="x.tex"))


# ---------------------------------------------------------------------------
# library_root
# ---------------------------------------------------------------------------

class TestLibraryRoot:
    def test_env_var_takes_precedence(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PAPER_LIBRARY_PATH", str(tmp_path))
        assert library_root() == tmp_path

    def test_returns_none_when_unconfigured(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PAPER_LIBRARY_PATH", raising=False)
        monkeypatch.chdir(tmp_path)
        # Temporarily rename ~/.citation-papers if present to avoid interference
        default = Path.home() / ".citation-papers"
        if not default.exists():
            assert library_root() is None


# ---------------------------------------------------------------------------
# _fetch_with_cap (mocked HTTP)
# ---------------------------------------------------------------------------

class TestFetchWithCap:
    def _make_response(self, content: bytes, content_length: Optional[int] = None):
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.url = "http://example.com/paper.pdf"
        resp.headers = MagicMock()
        resp.headers.get = lambda k: str(content_length) if content_length else None
        # Simulate chunked reads
        chunks = [content[i : i + 65536] for i in range(0, len(content), 65536)] + [b""]
        resp.read = MagicMock(side_effect=chunks)
        return resp

    def test_small_file_succeeds(self):
        data = b"%PDF small content"
        resp = self._make_response(data)
        with patch("citation_audit.core.library.urlopen", return_value=resp):
            result, url = _fetch_with_cap("http://example.com/paper.pdf")
        assert result == data

    def test_content_length_cap_raises(self):
        resp = self._make_response(b"x", content_length=MAX_FILE_BYTES + 1)
        with patch("citation_audit.core.library.urlopen", return_value=resp):
            with pytest.raises(ValueError, match="cap"):
                _fetch_with_cap("http://example.com/big.pdf")

    def test_streaming_cap_raises(self):
        big = b"x" * (MAX_FILE_BYTES + 1)
        resp = self._make_response(big)  # no content-length header
        with patch("citation_audit.core.library.urlopen", return_value=resp):
            with pytest.raises(ValueError, match="cap"):
                _fetch_with_cap("http://example.com/huge.pdf")


# ---------------------------------------------------------------------------
# download_paper (mocked HTTP)
# ---------------------------------------------------------------------------

class TestDownloadPaper:
    def _unpaywall_resp(self, pdf_url: Optional[str]) -> bytes:
        best = {}
        if pdf_url:
            best = {"url_for_pdf": pdf_url}
        return json.dumps({"best_oa_location": best}).encode()

    def test_unpaywall_success(self, tmp_path):
        pdf_content = b"%PDF-1.4 dummy"
        unpaywall_data = self._unpaywall_resp("http://example.com/paper.pdf")

        call_count = 0

        def fake_fetch(url, email="x"):
            nonlocal call_count
            call_count += 1
            if "unpaywall" in url:
                return unpaywall_data, url
            if url.endswith(".pdf"):
                return pdf_content, url
            raise Exception("unexpected url")

        with patch("citation_audit.core.library._fetch_with_cap", side_effect=fake_fetch):
            fname, stype, surl = download_paper("10.1/test", tmp_path)

        assert stype == "open_access_pdf"
        assert fname is not None
        assert (tmp_path / fname).read_bytes() == pdf_content

    def test_oversized_returns_oversized_type(self, tmp_path):
        pdf_url = "http://example.com/big.pdf"
        unpaywall_data = self._unpaywall_resp(pdf_url)

        def fake_fetch(url, email="x"):
            if "unpaywall" in url:
                return unpaywall_data, url
            if url.endswith(".pdf"):
                raise ValueError("Download exceeded cap")
            raise Exception("unexpected")

        with patch("citation_audit.core.library._fetch_with_cap", side_effect=fake_fetch):
            fname, stype, surl = download_paper("10.1/huge", tmp_path)

        assert fname is None
        assert stype == "oversized"

    def test_all_fallbacks_fail_returns_abstract_only(self, tmp_path):
        from urllib.error import URLError

        def fake_fetch(url, email="x"):
            raise URLError("connection refused")

        with patch("citation_audit.core.library._fetch_with_cap", side_effect=fake_fetch):
            fname, stype, surl = download_paper("10.1/gone", tmp_path)

        assert fname is None
        assert stype == "abstract_only"


# ---------------------------------------------------------------------------
# store_paper
# ---------------------------------------------------------------------------

class TestStorePaper:
    def test_existing_file_with_matching_sha256_skips_download(self, tmp_path):
        """If the file already exists with correct SHA-256, download is skipped."""
        pdf_content = b"%PDF existing"
        slug = doi_slug("10.1/skip")
        fname = f"{slug}.pdf"
        fpath = papers_dir(tmp_path) / fname
        fpath.write_bytes(pdf_content)
        digest = hashlib.sha256(pdf_content).hexdigest()

        existing = LibraryEntry(
            doi="10.1/skip",
            filename=fname,
            sha256=digest,
            source_type="open_access_pdf",
        )
        upsert_entry(tmp_path, existing)

        with patch("citation_audit.core.library.download_paper") as mock_dl:
            result = store_paper(tmp_path, LibraryEntry(doi="10.1/skip"))

        mock_dl.assert_not_called()
        assert result.sha256 == digest

    def test_new_entry_triggers_download(self, tmp_path):
        pdf_content = b"%PDF new"
        slug = doi_slug("10.1/new")
        fname = f"{slug}.pdf"

        def fake_download(doi, dest_dir, email="x"):
            (dest_dir / fname).write_bytes(pdf_content)
            return fname, "open_access_pdf", "http://example.com/new.pdf"

        with patch("citation_audit.core.library.download_paper", side_effect=fake_download):
            result = store_paper(tmp_path, LibraryEntry(doi="10.1/new"))

        assert result.filename == fname
        assert result.source_type == "open_access_pdf"
        assert result.sha256 is not None
        assert get_entry(tmp_path, "10.1/new") is not None

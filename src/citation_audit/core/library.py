"""Paper library — read/write library.json and download source PDFs/text.

The library lives in a separate Git repository cloned beside the project
(default: ``~/.citation-papers`` or the path in the ``PAPER_LIBRARY_PATH``
environment variable).  Within that repo the layout is::

    library.json
    papers/
        10.1038__s41586-021-03819-2.pdf
        no-doi__sha256abc12345678.pdf

``library.json`` is written atomically.  Each entry uses :class:`LibraryEntry`.

Citing-document references use the richer :class:`CitingRef` model so that
agents and users can navigate back to the exact passage:

    {
      "github": "Warnes-Innovations/multiscale-knowledge",
      "path":   "knowledge-system.tex"
    }

or, when no GitHub remote is known:

    {
      "local_path": "/Users/warnes/src/my-project/doc.tex"
    }
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

MAX_FILE_BYTES: int = 100 * 1024 * 1024  # 100 MB hard cap

_DEFAULT_EMAIL = "citation-audit@warnes-innovations.com"

# ---------------------------------------------------------------------------
# Helpers for library location
# ---------------------------------------------------------------------------

def library_root() -> Optional[Path]:
    """
    Return the paper library root directory, or None if not configured.

    Resolution order:
    1. ``PAPER_LIBRARY_PATH`` environment variable (absolute path to the
       cloned ``citation-papers`` repository root).
    2. ``~/.citation-papers`` if that directory exists.
    """
    env = os.environ.get("PAPER_LIBRARY_PATH")
    if env:
        p = Path(env).expanduser().resolve()
        if p.is_dir():
            return p
    default = Path.home() / ".citation-papers"
    if default.is_dir():
        return default
    return None


def papers_dir(root: Path) -> Path:
    d = root / "papers"
    d.mkdir(parents=True, exist_ok=True)
    return d


def library_json_path(root: Path) -> Path:
    return root / "library.json"


# ---------------------------------------------------------------------------
# DOI slug (safe filename component)
# ---------------------------------------------------------------------------

def doi_slug(doi: str) -> str:
    """Convert a DOI to a filesystem-safe slug (slashes → __)."""
    return re.sub(r"[^A-Za-z0-9._-]", "__", doi).strip("_")


# ---------------------------------------------------------------------------
# CitingRef
# ---------------------------------------------------------------------------

@dataclass
class CitingRef:
    """A reference back to a passage in a citing document."""
    path: str                       # repo-relative path, e.g. "knowledge-system.tex"
    github: Optional[str] = None    # "Owner/repo", if known
    local_path: Optional[str] = None  # absolute local path when no GitHub remote

    def to_dict(self) -> dict:
        d: dict = {"path": self.path}
        if self.github:
            d["github"] = self.github
        if self.local_path:
            d["local_path"] = self.local_path
        return d

    @staticmethod
    def from_dict(d: dict) -> "CitingRef":
        return CitingRef(
            path       = d["path"],
            github     = d.get("github"),
            local_path = d.get("local_path"),
        )

    @staticmethod
    def from_doc_path(doc_path: Path) -> "CitingRef":
        """
        Build a CitingRef from a local document path, resolving the GitHub
        remote from the containing Git repo when possible.
        """
        resolved = doc_path.expanduser().resolve()
        github_repo: Optional[str] = None
        relative_path: Optional[str] = None
        local_abs: Optional[str] = None

        # Try to detect the git root and remote
        try:
            result = subprocess.run(
                ["git", "-C", str(resolved.parent), "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                git_root = Path(result.stdout.strip())
                relative_path = str(resolved.relative_to(git_root))
                # Get first 'origin' remote URL
                remote_result = subprocess.run(
                    ["git", "-C", str(resolved.parent), "remote", "get-url", "origin"],
                    capture_output=True, text=True, timeout=5,
                )
                if remote_result.returncode == 0:
                    url = remote_result.stdout.strip()
                    # Extract Owner/repo from https://github.com/Owner/repo(.git)?
                    # or git@github.com:Owner/repo(.git)
                    m = re.search(
                        r"github\.com[:/]([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?$",
                        url,
                    )
                    if m:
                        github_repo = m.group(1)
        except Exception:
            pass

        if relative_path is None:
            relative_path = resolved.name
            local_abs = str(resolved)

        return CitingRef(
            path       = relative_path,
            github     = github_repo,
            local_path = local_abs,
        )


# ---------------------------------------------------------------------------
# LibraryEntry
# ---------------------------------------------------------------------------

@dataclass
class LibraryEntry:
    """One paper in the shared library."""
    doi:           Optional[str]      = None
    pmid:          Optional[str]      = None
    filename:      Optional[str]      = None   # relative to papers/
    sha256:        Optional[str]      = None
    title:         str                = ""
    authors:       list[str]          = field(default_factory=list)
    year:          Optional[int]      = None
    journal:       str                = ""
    source_type:   str                = "unknown"   # open_access_pdf | pmc_pdf | preprint_pdf |
                                                     # publisher_text | abstract_only | oversized
    download_date: Optional[str]      = None
    open_access:   bool               = False
    abstract:      str                = ""
    citing_docs:   list[CitingRef]    = field(default_factory=list)

    # ----- serialization -----

    def to_dict(self) -> dict:
        d: dict = {}
        for attr in ("doi", "pmid", "filename", "sha256", "title",
                     "year", "journal", "source_type", "download_date", "open_access",
                     "abstract"):
            val = getattr(self, attr)
            if val is not None and val != "" and val is not False:
                d[attr] = val
        if self.authors:
            d["authors"] = self.authors
        if self.citing_docs:
            d["citing_docs"] = [r.to_dict() for r in self.citing_docs]
        return d

    @staticmethod
    def from_dict(d: dict) -> "LibraryEntry":
        return LibraryEntry(
            doi           = d.get("doi"),
            pmid          = d.get("pmid"),
            filename      = d.get("filename"),
            sha256        = d.get("sha256"),
            title         = d.get("title", ""),
            authors       = d.get("authors", []),
            year          = d.get("year"),
            journal       = d.get("journal", ""),
            source_type   = d.get("source_type", "unknown"),
            download_date = d.get("download_date"),
            open_access   = d.get("open_access", False),
            abstract      = d.get("abstract", ""),
            citing_docs   = [CitingRef.from_dict(r) for r in d.get("citing_docs", [])],
        )


# ---------------------------------------------------------------------------
# library.json atomic read / write
# ---------------------------------------------------------------------------

def load_library(root: Path) -> dict[str, LibraryEntry]:
    """Load library.json; return dict keyed by DOI (or sha256 for no-DOI entries)."""
    p = library_json_path(root)
    if not p.exists():
        return {}
    raw: list[dict] = json.loads(p.read_text())
    entries: dict[str, LibraryEntry] = {}
    for item in raw:
        entry = LibraryEntry.from_dict(item)
        key = entry.doi or (f"sha256:{entry.sha256}" if entry.sha256 else None)
        if key:
            entries[key] = entry
    return entries


def save_library(root: Path, entries: dict[str, LibraryEntry]) -> None:
    """Write library.json atomically."""
    p = library_json_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps([e.to_dict() for e in entries.values()], indent=2)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".library-", suffix=".json")
    try:
        os.write(fd, data.encode())
        os.close(fd)
        os.replace(tmp, p)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def get_entry(root: Path, doi: str) -> Optional[LibraryEntry]:
    """Look up a library entry by DOI.  Returns None if not found."""
    entries = load_library(root)
    return entries.get(doi)


def upsert_entry(root: Path, entry: LibraryEntry) -> None:
    """Insert or replace a library entry by DOI (or sha256 fallback key)."""
    entries = load_library(root)
    key = entry.doi or (f"sha256:{entry.sha256}" if entry.sha256 else None)
    if key is None:
        raise ValueError("LibraryEntry must have at least a doi or sha256.")
    entries[key] = entry
    save_library(root, entries)


def add_citing_doc(root: Path, doi: str, ref: CitingRef) -> None:
    """Append a citing document reference to an existing entry (idempotent by path)."""
    entries = load_library(root)
    if doi not in entries:
        raise KeyError(f"DOI '{doi}' not found in library.")
    entry = entries[doi]
    existing_paths = {r.path for r in entry.citing_docs}
    if ref.path not in existing_paths:
        entry.citing_docs.append(ref)
        save_library(root, entries)


# ---------------------------------------------------------------------------
# SHA-256 helpers
# ---------------------------------------------------------------------------

def _sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# HTTP fetch with 100 MB cap
# ---------------------------------------------------------------------------

def _fetch_with_cap(url: str, email: str = _DEFAULT_EMAIL) -> tuple[bytes, str]:
    """
    Download *url* and return (content_bytes, final_url).

    Raises ``ValueError`` if the response exceeds MAX_FILE_BYTES.
    Raises ``urllib.error.HTTPError`` / ``URLError`` on network errors.
    """
    req = Request(url, headers={"User-Agent": f"citation-audit/0.1 (mailto:{email})"})
    with urlopen(req, timeout=60) as resp:
        content_length = resp.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_FILE_BYTES:
            raise ValueError(
                f"Content-Length {content_length} exceeds {MAX_FILE_BYTES} byte cap"
            )
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_FILE_BYTES:
                raise ValueError(
                    f"Download exceeded {MAX_FILE_BYTES} byte cap after {total} bytes"
                )
            chunks.append(chunk)
        return b"".join(chunks), resp.url


# ---------------------------------------------------------------------------
# Download sequence
# ---------------------------------------------------------------------------

def download_paper(
    doi: str,
    dest_dir: Path,
    email: str = _DEFAULT_EMAIL,
) -> tuple[Optional[str], str, str]:
    """
    Attempt to download the paper identified by *doi* into *dest_dir*.

    Returns ``(filename_or_None, source_type, source_url)`` where:
    - ``filename_or_None`` is the saved filename relative to *dest_dir*, or
      ``None`` when no file was saved (abstract-only or oversized).
    - ``source_type`` is one of:
      ``open_access_pdf | pmc_pdf | preprint_pdf | publisher_text |
      abstract_only | oversized``
    - ``source_url`` is the URL that was (or would have been) used.

    File size is capped at MAX_FILE_BYTES (100 MB).  Existing files are not
    overwritten; the caller should check before calling this function.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    slug = doi_slug(doi)

    # 1. Unpaywall
    try:
        url = f"https://api.unpaywall.org/v2/{doi}?email={email}"
        data, _ = _fetch_with_cap(url)
        info = json.loads(data)
        best = info.get("best_oa_location") or {}
        pdf_url = best.get("url_for_pdf") or best.get("url")
        if pdf_url and pdf_url.lower().endswith(".pdf"):
            try:
                content, final_url = _fetch_with_cap(pdf_url, email)
                fname = f"{slug}.pdf"
                (dest_dir / fname).write_bytes(content)
                return fname, "open_access_pdf", final_url
            except ValueError as exc:
                if "cap" in str(exc).lower():
                    return None, "oversized", pdf_url
    except (HTTPError, URLError, json.JSONDecodeError, KeyError):
        pass

    # 2. PubMed Central
    try:
        pm_url = (
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            f"?db=pmc&term={doi}[doi]&retmode=json"
        )
        data, _ = _fetch_with_cap(pm_url)
        pmcids = json.loads(data).get("esearchresult", {}).get("idlist", [])
        if pmcids:
            pmcid = pmcids[0]
            pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/pdf/"
            try:
                content, final_url = _fetch_with_cap(pdf_url, email)
                if content[:4] == b"%PDF":
                    fname = f"{slug}.pdf"
                    (dest_dir / fname).write_bytes(content)
                    return fname, "pmc_pdf", final_url
            except ValueError as exc:
                if "cap" in str(exc).lower():
                    return None, "oversized", pdf_url
    except (HTTPError, URLError, json.JSONDecodeError, KeyError):
        pass

    # 3. bioRxiv / medRxiv
    for server in ("biorxiv", "medrxiv"):
        try:
            url = f"https://api.biorxiv.org/details/{server}/{doi}/na/json"
            data, _ = _fetch_with_cap(url)
            collection = json.loads(data).get("collection", [])
            if collection:
                pdf_url = f"https://www.{server}.org/content/{doi}.full.pdf"
                try:
                    content, final_url = _fetch_with_cap(pdf_url, email)
                    if content[:4] == b"%PDF":
                        fname = f"{slug}.pdf"
                        (dest_dir / fname).write_bytes(content)
                        return fname, "preprint_pdf", final_url
                except ValueError as exc:
                    if "cap" in str(exc).lower():
                        return None, "oversized", pdf_url
        except (HTTPError, URLError, json.JSONDecodeError):
            continue

    # 4. Semantic Scholar
    try:
        ss_url = (
            f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
            f"?fields=openAccessPdf"
        )
        data, _ = _fetch_with_cap(ss_url)
        oa = json.loads(data).get("openAccessPdf") or {}
        pdf_url = oa.get("url")
        if pdf_url:
            try:
                content, final_url = _fetch_with_cap(pdf_url, email)
                if content[:4] == b"%PDF":
                    fname = f"{slug}.pdf"
                    (dest_dir / fname).write_bytes(content)
                    return fname, "open_access_pdf", final_url
            except ValueError as exc:
                if "cap" in str(exc).lower():
                    return None, "oversized", pdf_url
    except (HTTPError, URLError, json.JSONDecodeError, KeyError):
        pass

    # 5. Publisher landing page → extract text
    try:
        doi_url = f"https://doi.org/{doi}"
        content, final_url = _fetch_with_cap(doi_url, email)
        text = content.decode("utf-8", errors="replace")
        # Strip HTML tags crudely for storage
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s{3,}", "\n\n", text)
        fname = f"{slug}.txt"
        (dest_dir / fname).write_text(text[:200_000], encoding="utf-8")
        return fname, "publisher_text", final_url
    except (HTTPError, URLError, ValueError):
        pass

    return None, "abstract_only", f"https://doi.org/{doi}"


# ---------------------------------------------------------------------------
# High-level: store paper in library
# ---------------------------------------------------------------------------

def store_paper(
    root: Path,
    entry: LibraryEntry,
    email: str = _DEFAULT_EMAIL,
) -> LibraryEntry:
    """
    Add *entry* to the library.  If entry.doi is set and a PDF is not already
    present, attempt download.  Updates entry in place and persists library.json.

    Returns the (possibly updated) entry.
    """
    if entry.doi is None and entry.sha256 is None:
        raise ValueError("Entry must have at least a doi or sha256.")

    pdir = papers_dir(root)
    existing_entries = load_library(root)

    key = entry.doi or f"sha256:{entry.sha256}"

    # Check if already present with a file
    if key in existing_entries:
        existing = existing_entries[key]
        if existing.filename:
            fpath = pdir / existing.filename
            if fpath.exists():
                # Verify SHA-256 matches; if so, skip download
                actual = sha256_of_file(fpath)
                if actual == existing.sha256:
                    # Merge any new citing_docs
                    existing_paths = {r.path for r in existing.citing_docs}
                    for ref in entry.citing_docs:
                        if ref.path not in existing_paths:
                            existing.citing_docs.append(ref)
                    upsert_entry(root, existing)
                    return existing

    # Attempt download if we have a DOI and no file yet
    if entry.doi and not entry.filename:
        fname, stype, surl = download_paper(entry.doi, pdir, email=email)
        entry.source_type   = stype
        entry.download_date = str(date.today())
        if fname:
            fpath = pdir / fname
            entry.filename = fname
            entry.sha256   = sha256_of_file(fpath)
        # oversized / abstract_only → no file written; source_type already set

    upsert_entry(root, entry)
    return entry

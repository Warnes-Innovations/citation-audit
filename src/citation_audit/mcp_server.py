"""MCP server — exposes citation-audit operations as MCP tools."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .core import extractor, classifier, index as idx_mod, scaffold as scf_mod
from .core import library as lib_mod
from .core.library import CitingRef, LibraryEntry
from .core.schema import AssertionRecord, CitationRecord
from .core.extractor import assertion_id as _assertion_id

mcp = FastMCP(
    "citation-audit",
    instructions=(
        "Tools for auditing citations in LaTeX documents. "
        "Extracts and classifies assertions, manages .audit/ artifact folders, "
        "and maintains index.json records for citations and uncited assertions."
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _p(doc: str) -> Path:
    return Path(doc).expanduser().resolve()


def _json(obj) -> str:
    return json.dumps(obj, indent=2)


# ---------------------------------------------------------------------------
# Tool: extract_assertions
# ---------------------------------------------------------------------------

@mcp.tool()
def extract_assertions(
    doc: str,
    only: str = "all",
) -> str:
    """
    Parse a LaTeX document and classify every sentence by assertion type.

    Parameters
    ----------
    doc : str
        Absolute path to the .tex file.
    only : str
        Filter results: "all" | "cited" | "uncited" | "needs-citation".
        "needs-citation" returns only asserted-facts with no citation marker.

    Returns
    -------
    JSON list of assertion records with fields:
      id, text, location, assertion_type, citation_label, needs_citation
    """
    p = _p(doc)
    sentences = extractor.extract_sentences(p)
    records = []
    for s in sentences:
        atype, needs = classifier.classify(s)
        if only == "cited" and not s.citations:
            continue
        if only == "uncited" and s.citations:
            continue
        if only == "needs-citation" and not needs:
            continue
        records.append({
            "id":             _assertion_id(p.stem, s.text),
            "text":           s.text,
            "location":       f"line ~{s.line}",
            "assertion_type": atype,
            "citation_label": s.citations[0] if len(s.citations) == 1 else (s.citations or None),
            "needs_citation": needs,
        })
    return _json(records)


# ---------------------------------------------------------------------------
# Tool: get_audit_status
# ---------------------------------------------------------------------------

@mcp.tool()
def get_audit_status(doc: str) -> str:
    """
    Return the current audit index for a document as JSON.

    Includes all citation records (scores, confirmation types, bib mismatches)
    and all recorded assertion records.

    Parameters
    ----------
    doc : str
        Absolute path to the .tex file (not the index.json).
    """
    p = _p(doc)
    idx = idx_mod.load(p)
    return _json(idx.to_dict())


# ---------------------------------------------------------------------------
# Tool: scaffold_citation
# ---------------------------------------------------------------------------

@mcp.tool()
def scaffold_citation(doc: str, label: str) -> str:
    """
    Create .audit/<doc>/<label>/ stub artifact files (publication.md,
    citation_<label>.md, summary.md).  Existing files are not overwritten.

    Parameters
    ----------
    doc : str
        Absolute path to the .tex file.
    label : str
        BibTeX key (e.g. "viceconti2016_virtualpatients").

    Returns
    -------
    JSON with {"folder": "<path>", "files": [...]}
    """
    p = _p(doc)
    folder = scf_mod.scaffold_citation(p, label)
    files = [str(f) for f in folder.iterdir()]
    return _json({"folder": str(folder), "files": files})


# ---------------------------------------------------------------------------
# Tool: scaffold_assertion_artifact
# ---------------------------------------------------------------------------

@mcp.tool()
def scaffold_assertion_artifact(doc: str, assertion_id: str, text: str) -> str:
    """
    Create .audit/<doc>/assertions/<id>/ stub for an uncited assertion.

    Parameters
    ----------
    doc : str
        Absolute path to the .tex file.
    assertion_id : str
        Stable assertion ID (from extract_assertions or compute_assertion_id).
    text : str
        The exact sentence text.

    Returns
    -------
    JSON with {"folder": "<path>"}
    """
    p = _p(doc)
    folder = scf_mod.scaffold_assertion(p, assertion_id, text)
    return _json({"folder": str(folder)})


# ---------------------------------------------------------------------------
# Tool: update_citation_record
# ---------------------------------------------------------------------------

@mcp.tool()
def update_citation_record(
    doc: str,
    label: str,
    score: Optional[int] = None,
    confirmation_type: Optional[str] = None,
    assertion_type: Optional[str] = None,
    bib_mismatches: Optional[list[str]] = None,
    score_reason: Optional[str] = None,
    reference_text: Optional[str] = None,
    confirmation_source: Optional[str] = None,
) -> str:
    """
    Insert or patch a citation record in index.json.

    Only fields explicitly provided (non-None) are written; others are preserved.

    Parameters
    ----------
    doc : str
        Absolute path to the .tex file.
    label : str
        BibTeX key.
    score : int, optional
        Support score −100..+100.
    confirmation_type : str, optional
        "direct" | "indirect" | "none"
    assertion_type : str, optional
        Classification of the *citing* claim.
    bib_mismatches : list[str], optional
        List of mismatch strings, e.g. ["journal: A → B"].
    score_reason : str, optional
    reference_text : str, optional
        Full formatted reference string.
    confirmation_source : str, optional
        Where confirmation was obtained (URL, DOI, PubMed).

    Returns
    -------
    JSON of the updated CitationRecord.
    """
    p = _p(doc)
    idx = idx_mod.load(p)
    if label not in idx.citations:
        idx.citations[label] = CitationRecord(bibtex_label=label)
        idx_mod.save(p, idx)

    fields = {k: v for k, v in {
        "score":               score,
        "confirmation_type":   confirmation_type,
        "assertion_type":      assertion_type,
        "bib_mismatches":      bib_mismatches,
        "score_reason":        score_reason,
        "reference_text":      reference_text,
        "confirmation_source": confirmation_source,
    }.items() if v is not None}

    rec = idx_mod.patch_citation(p, label, **fields)
    return _json(rec.to_dict())


# ---------------------------------------------------------------------------
# Tool: tag_assertion
# ---------------------------------------------------------------------------

@mcp.tool()
def tag_assertion(
    doc: str,
    assertion_id: str,
    assertion_type: str,
    text: Optional[str] = None,
    location: Optional[str] = None,
    citation_label: Optional[str] = None,
    notes: str = "",
) -> str:
    """
    Record or update the assertion_type for a sentence in index.json.

    Use this to mark uncited passages as original-synthesis, derived-conclusion,
    own-contribution, definition, established-convention, or narrative — so the
    auditor knows these do not require a citation.

    Parameters
    ----------
    doc : str
        Absolute path to the .tex file.
    assertion_id : str
        Stable assertion ID.
    assertion_type : str
        One of: asserted-fact, original-synthesis, derived-conclusion,
        own-contribution, definition, established-convention, narrative, unknown.
    text : str, optional
        Exact sentence text (required only when creating a new record).
    location : str, optional
    citation_label : str, optional
        BibTeX label if this assertion has a citation.
    notes : str, optional
        Rationale or follow-up note.

    Returns
    -------
    JSON of the AssertionRecord.
    """
    p = _p(doc)
    idx = idx_mod.load(p)

    if assertion_id in idx.assertions:
        fields: dict = {"assertion_type": assertion_type}
        if notes:
            fields["notes"] = notes
        rec = idx_mod.patch_assertion(p, assertion_id, **fields)
    else:
        if not text:
            return _json({"error": "text is required when creating a new assertion record"})
        rec = AssertionRecord(
            id             = assertion_id,
            text           = text,
            location       = location or "",
            assertion_type = assertion_type,  # type: ignore[arg-type]
            citation_label = citation_label,
            needs_citation = (assertion_type == "asserted-fact"),
            notes          = notes,
        )
        idx_mod.upsert_assertion(p, rec)

    return _json(rec.to_dict())


# ---------------------------------------------------------------------------
# Tool: list_assertions
# ---------------------------------------------------------------------------

@mcp.tool()
def list_assertions(
    doc: str,
    filter_type: Optional[str] = None,
    needs_citation_only: bool = False,
) -> str:
    """
    Return recorded assertion records from index.json.

    Parameters
    ----------
    doc : str
        Absolute path to the .tex file.
    filter_type : str, optional
        Return only assertions of this assertion_type.
    needs_citation_only : bool
        If True, return only assertions where needs_citation is True.

    Returns
    -------
    JSON list of AssertionRecord dicts.
    """
    p = _p(doc)
    idx = idx_mod.load(p)
    results = list(idx.assertions.values())
    if filter_type:
        results = [r for r in results if r.assertion_type == filter_type]
    if needs_citation_only:
        results = [r for r in results if r.needs_citation]
    return _json([r.to_dict() for r in results])


# ---------------------------------------------------------------------------
# Tool: compute_assertion_id
# ---------------------------------------------------------------------------

@mcp.tool()
def compute_assertion_id(doc: str, text: str) -> str:
    """
    Return the stable assertion ID for a given sentence text.

    Useful for looking up whether an assertion is already recorded before
    calling tag_assertion or scaffold_assertion_artifact.

    Parameters
    ----------
    doc : str
        Absolute path to the .tex file (stem is used in the hash).
    text : str
        Exact assertion text.

    Returns
    -------
    JSON with {"id": "<a-xxxxxxxx>"}
    """
    p = _p(doc)
    return _json({"id": _assertion_id(p.stem, text)})


# ---------------------------------------------------------------------------
# Library tools
# ---------------------------------------------------------------------------

@mcp.tool()
def get_library_entry(doi: str) -> str:
    """
    Look up a paper in the shared library by DOI.

    Returns the full LibraryEntry as JSON, or {"found": false} if absent.
    Agents should call this before attempting to download a paper so that
    re-downloads and duplicate storage are avoided.

    Parameters
    ----------
    doi : str
        Raw DOI string, e.g. "10.1038/s41586-021-03819-2".
    """
    root = lib_mod.library_root()
    if root is None:
        return _json({"found": False, "reason": "library not configured"})
    entry = lib_mod.get_entry(root, doi)
    if entry is None:
        return _json({"found": False})
    d = entry.to_dict()
    d["found"] = True
    if entry.filename:
        fpath = lib_mod.papers_dir(root) / entry.filename
        d["local_path"] = str(fpath) if fpath.exists() else None
    return _json(d)


@mcp.tool()
def store_library_paper(
    doi: str,
    title: str = "",
    authors: Optional[list[str]] = None,
    year: Optional[int] = None,
    journal: str = "",
    pmid: Optional[str] = None,
    abstract: str = "",
    doc: Optional[str] = None,
    email: Optional[str] = None,
) -> str:
    """
    Add a paper to the shared library and attempt to download it.

    Checks the library first; if the paper is already present with a valid
    file and matching SHA-256, the download is skipped.  The 100 MB cap is
    enforced; oversized papers are recorded with source_type "oversized".

    Parameters
    ----------
    doi : str
        Raw DOI string.
    title : str, optional
    authors : list[str], optional
    year : int, optional
    journal : str, optional
    pmid : str, optional
    abstract : str, optional
    doc : str, optional
        Absolute path to the citing document; used to record a CitingRef.
    email : str, optional
        Contact e-mail for Unpaywall / Crossref polite pool.

    Returns
    -------
    JSON of the stored LibraryEntry plus "local_path" when a file exists.
    """
    root = lib_mod.library_root()
    if root is None:
        return _json({"error": "paper library not configured — set PAPER_LIBRARY_PATH"})

    citing: list[CitingRef] = []
    if doc:
        citing.append(CitingRef.from_doc_path(Path(doc)))

    entry = LibraryEntry(
        doi         = doi,
        pmid        = pmid,
        title       = title,
        authors     = authors or [],
        year        = year,
        journal     = journal,
        abstract    = abstract,
        citing_docs = citing,
    )
    kw = {}
    if email:
        kw["email"] = email
    entry = lib_mod.store_paper(root, entry, **kw)

    result = entry.to_dict()
    if entry.filename:
        fpath = lib_mod.papers_dir(root) / entry.filename
        result["local_path"] = str(fpath) if fpath.exists() else None
    return _json(result)


@mcp.tool()
def record_citing_doc(doi: str, doc: str) -> str:
    """
    Record that a document cites the paper identified by DOI.

    Appends a CitingRef (with GitHub repo + path when detectable) to the
    library entry.  Idempotent: duplicate paths are ignored.

    Parameters
    ----------
    doi : str
        Raw DOI string.
    doc : str
        Absolute path to the citing document.

    Returns
    -------
    JSON with {"ok": true} or {"error": "<message>"}.
    """
    root = lib_mod.library_root()
    if root is None:
        return _json({"error": "paper library not configured"})
    ref = CitingRef.from_doc_path(Path(doc))
    try:
        lib_mod.add_citing_doc(root, doi, ref)
        return _json({"ok": True, "ref": ref.to_dict()})
    except KeyError as exc:
        return _json({"error": str(exc)})


@mcp.tool()
def list_library(format: str = "json") -> str:
    """
    Return all entries in the shared library.

    Parameters
    ----------
    format : str
        "json" (default) — full entry objects.
        "summary" — compact list with doi, year, title, source_type.
    """
    root = lib_mod.library_root()
    if root is None:
        return _json({"error": "paper library not configured"})
    entries = lib_mod.load_library(root)
    if format == "summary":
        return _json([
            {"doi": e.doi, "year": e.year, "title": e.title, "source_type": e.source_type}
            for e in entries.values()
        ])
    return _json([e.to_dict() for e in entries.values()])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    mcp.run()


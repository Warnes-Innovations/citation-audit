"""Read and write .audit/<doc>/index.json atomically."""
from __future__ import annotations

import json
import tempfile
import os
from pathlib import Path
from datetime import date

from .schema import AuditIndex, CitationRecord, AssertionRecord


def audit_dir(doc_path: Path) -> Path:
    """Return .audit/<doc-stem>/ relative to the document's parent directory."""
    return doc_path.parent / ".audit" / doc_path.stem


def index_path(doc_path: Path) -> Path:
    return audit_dir(doc_path) / "index.json"


def load(doc_path: Path) -> AuditIndex:
    """Load index.json; return a blank AuditIndex if it does not exist."""
    p = index_path(doc_path)
    if not p.exists():
        return AuditIndex(document=doc_path.name, audit_date=str(date.today()))
    return AuditIndex.from_dict(json.loads(p.read_text()))


def save(doc_path: Path, idx: AuditIndex) -> None:
    """Write index.json atomically via a temp file."""
    p = index_path(doc_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(idx.to_dict(), indent=2)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".index-", suffix=".json")
    try:
        os.write(fd, data.encode())
        os.close(fd)
        os.replace(tmp, p)
    except Exception:
        os.close(fd)
        os.unlink(tmp)
        raise


def upsert_citation(doc_path: Path, record: CitationRecord) -> AuditIndex:
    """Insert or replace a citation record; returns the updated index."""
    idx = load(doc_path)
    idx.citations[record.bibtex_label] = record
    idx.audit_date = str(date.today())
    save(doc_path, idx)
    return idx


def upsert_assertion(doc_path: Path, record: AssertionRecord) -> AuditIndex:
    """Insert or replace an assertion record; returns the updated index."""
    idx = load(doc_path)
    idx.assertions[record.id] = record
    idx.audit_date = str(date.today())
    save(doc_path, idx)
    return idx


def patch_citation(doc_path: Path, label: str, **fields) -> CitationRecord:
    """Update only the specified fields on an existing citation; raises KeyError if absent."""
    idx = load(doc_path)
    if label not in idx.citations:
        raise KeyError(f"Citation '{label}' not found in {index_path(doc_path)}")
    rec = idx.citations[label]
    for k, v in fields.items():
        if hasattr(rec, k):
            setattr(rec, k, v)
    idx.audit_date = str(date.today())
    save(doc_path, idx)
    return rec


def patch_assertion(doc_path: Path, assertion_id: str, **fields) -> AssertionRecord:
    """Update only the specified fields on an existing assertion; raises KeyError if absent."""
    idx = load(doc_path)
    if assertion_id not in idx.assertions:
        raise KeyError(f"Assertion '{assertion_id}' not found in {index_path(doc_path)}")
    rec = idx.assertions[assertion_id]
    for k, v in fields.items():
        if hasattr(rec, k):
            setattr(rec, k, v)
    idx.audit_date = str(date.today())
    save(doc_path, idx)
    return rec

"""Create .audit/<doc>/<label>/ stub artifact folders."""
from __future__ import annotations

from pathlib import Path

from .index import audit_dir


_PUBLICATION_STUB = """\
# Publication — {label}

- **bibtex_label**: {label}
- **confirmation_type**: none
- **confirmation_source**:
- **doi**:
- **doi_url**:
- **pubmed_url**:
- **scholar_url**:
- **open_access_url**:
- **bib_doi_written**: false

## Bibliographic Details

(populate after CrossRef / PubMed lookup)

## Abstract

(populate after source retrieval)
"""

_CITATION_STUB = """\
# Citation — {label}

## Citing Text

(populate with exact sentence(s) from document)

## Assertion Type

(one of: asserted-fact, original-synthesis, derived-conclusion,
 own-contribution, definition, established-convention, narrative)

## Source Text

(exact passage from source that supports or contradicts the claim)

## Support Score

**Score**: 0

**Reason**: (not yet assessed)
"""

_SUMMARY_STUB = """\
# Summary — {label}

- **Score**: 0
- **confirmation_type**: none
- **BibTeX mismatches**: none identified
- **Action required**: pending assessment
"""


def scaffold_citation(doc_path: Path, label: str) -> Path:
    """
    Create .audit/<doc>/<label>/ with stub files if they do not already exist.
    Returns the folder path.
    """
    folder = audit_dir(doc_path) / label
    folder.mkdir(parents=True, exist_ok=True)

    _write_if_absent(folder / "publication.md",         _PUBLICATION_STUB.format(label=label))
    _write_if_absent(folder / f"citation_{label}.md",   _CITATION_STUB.format(label=label))
    _write_if_absent(folder / "summary.md",             _SUMMARY_STUB.format(label=label))

    return folder


def scaffold_assertion(doc_path: Path, assertion_id: str, text: str) -> Path:
    """
    Create .audit/<doc>/assertions/<id>/ stub for an uncited assertion.
    Returns the folder path.
    """
    folder = audit_dir(doc_path) / "assertions" / assertion_id
    folder.mkdir(parents=True, exist_ok=True)

    stub = f"""\
# Assertion — {assertion_id}

## Text

{text}

## Assertion Type

(one of: asserted-fact, original-synthesis, derived-conclusion,
 own-contribution, definition, established-convention, narrative)

## Notes

(rationale for classification; citation recommendation if needed)
"""
    _write_if_absent(folder / "assertion.md", stub)
    return folder


def _write_if_absent(path: Path, content: str) -> None:
    if not path.exists():
        path.write_text(content)

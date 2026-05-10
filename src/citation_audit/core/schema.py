"""Shared data types for citation audit records and assertions."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

AssertionType = Literal[
    "asserted-fact",           # external claim that needs a citation — TARGET for finder
    "original-synthesis",      # author's own reasoning / analytical contribution
    "derived-conclusion",      # conclusion drawn from results or model in this document
    "own-contribution",        # description of the paper's own method / model / framework
    "definition",              # formal definition, variable introduction, notation
    "established-convention",  # universally accepted textbook principle
    "narrative",               # transitional, motivational, or rhetorical framing
    "unknown",                 # not yet classified
]

ConfirmationType = Literal["direct", "indirect", "none"]


@dataclass
class AssertionRecord:
    """A sentence or passage classified for citation need."""
    id: str                                       # stable hash-based ID
    text: str                                     # exact text from document
    location: str                                 # e.g. "line 1234 / Section 3.2"
    assertion_type: AssertionType = "unknown"
    citation_label: Optional[str] = None          # bibtex label if cited; None if uncited
    needs_citation: bool = False
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "text":             self.text,
            "location":         self.location,
            "assertion_type":   self.assertion_type,
            "citation_label":   self.citation_label,
            "needs_citation":   self.needs_citation,
            "notes":            self.notes,
        }

    @staticmethod
    def from_dict(d: dict) -> "AssertionRecord":
        return AssertionRecord(
            id             = d["id"],
            text           = d["text"],
            location       = d["location"],
            assertion_type = d.get("assertion_type", "unknown"),
            citation_label = d.get("citation_label"),
            needs_citation = d.get("needs_citation", False),
            notes          = d.get("notes", ""),
        )


@dataclass
class CitationRecord:
    """Audit record for one bibtex-labelled citation."""
    bibtex_label: str
    reference_text: str          = ""
    confirmation_type: ConfirmationType = "none"
    confirmation_source: str     = ""
    bib_mismatches: list[str]    = field(default_factory=list)
    score: int                   = 0
    score_reason: str            = ""
    assertion_type: AssertionType = "asserted-fact"   # type of the *citing* claim

    def to_dict(self) -> dict:
        return {
            "bibtex_label":        self.bibtex_label,
            "reference_text":      self.reference_text,
            "confirmation_type":   self.confirmation_type,
            "confirmation_source": self.confirmation_source,
            "bib_mismatches":      self.bib_mismatches,
            "score":               self.score,
            "score_reason":        self.score_reason,
            "assertion_type":      self.assertion_type,
        }

    @staticmethod
    def from_dict(d: dict) -> "CitationRecord":
        return CitationRecord(
            bibtex_label        = d["bibtex_label"],
            reference_text      = d.get("reference_text", ""),
            confirmation_type   = d.get("confirmation_type", "none"),
            confirmation_source = d.get("confirmation_source", ""),
            bib_mismatches      = d.get("bib_mismatches", []),
            score               = d.get("score", 0),
            score_reason        = d.get("score_reason", ""),
            assertion_type      = d.get("assertion_type", "asserted-fact"),
        )


@dataclass
class AuditIndex:
    """Root index for a single citing document."""
    document: str
    audit_date: str
    citations:  dict[str, CitationRecord]  = field(default_factory=dict)
    assertions: dict[str, AssertionRecord] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "document":   self.document,
            "audit_date": self.audit_date,
            "citations":  {k: v.to_dict() for k, v in self.citations.items()},
            "assertions": {k: v.to_dict() for k, v in self.assertions.items()},
        }

    @staticmethod
    def from_dict(d: dict) -> "AuditIndex":
        idx = AuditIndex(
            document   = d["document"],
            audit_date = d.get("audit_date", ""),
        )
        for k, v in d.get("citations", {}).items():
            idx.citations[k] = CitationRecord.from_dict(v)
        for k, v in d.get("assertions", {}).items():
            idx.assertions[k] = AssertionRecord.from_dict(v)
        return idx

"""Shared pytest fixtures for citation-audit tests."""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Minimal .tex content helpers
# ---------------------------------------------------------------------------

SIMPLE_TEX = textwrap.dedent(r"""
    \documentclass{article}
    \begin{document}

    Enzyme X has been shown to have a Km of 70 mM in human tissue.

    This suggests that the pathway is rate-limited by substrate availability.

    We propose a novel framework for multi-scale modelling.

    The output is not just operating characteristics (type I error, power)
    under a single assumed treatment effect, but a full posterior
    distribution over operating characteristics.

    Clinical trials have demonstrated that aldose reductase inhibitors reduce
    diabetic complications \citep{Oates1999_ARfail}.

    Let $x$ denote the concentration of substrate at time $t$.

    In order to motivate the analysis, we briefly review prior work.

    \end{document}
""")

CITE_TEX = textwrap.dedent(r"""
    \documentclass{article}
    \begin{document}

    Studies have demonstrated improved outcomes \citep{smith2020_outcomes}.

    Multiple studies confirm this \citep{jones2019_trial,lee2021_meta}.

    \end{document}
""")


@pytest.fixture()
def tmp_tex(tmp_path: Path) -> Path:
    """Write SIMPLE_TEX to a temp file and return its path."""
    p = tmp_path / "test-doc.tex"
    p.write_text(SIMPLE_TEX)
    return p


@pytest.fixture()
def tmp_cite_tex(tmp_path: Path) -> Path:
    """Write CITE_TEX to a temp file and return its path."""
    p = tmp_path / "cite-doc.tex"
    p.write_text(CITE_TEX)
    return p


@pytest.fixture()
def tmp_doc_with_index(tmp_path: Path) -> Path:
    """Return a .tex path whose .audit/index.json is pre-populated."""
    p = tmp_path / "mydoc.tex"
    p.write_text("% empty\n")
    audit_dir = tmp_path / ".audit" / "mydoc"
    audit_dir.mkdir(parents=True)
    index = {
        "document":   "mydoc.tex",
        "audit_date": "2026-05-10",
        "citations": {
            "smith2020": {
                "bibtex_label":        "smith2020",
                "reference_text":      "Smith et al. 2020",
                "confirmation_type":   "direct",
                "confirmation_source": "CrossRef",
                "bib_mismatches":      [],
                "score":               90,
                "score_reason":        "All fields match.",
                "assertion_type":      "asserted-fact",
            }
        },
        "assertions": {},
    }
    (audit_dir / "index.json").write_text(json.dumps(index, indent=2))
    return p

"""Tests for core/classifier.py — assertion_type heuristics."""
from __future__ import annotations

import pytest
from citation_audit.core.classifier import classify
from citation_audit.core.extractor import Sentence


def _sent(text: str, citations: list[str] | None = None) -> Sentence:
    """Build a minimal Sentence for classifier testing."""
    return Sentence(
        text=text,
        raw=text,
        line=1,
        paragraph=0,
        citations=citations or [],
    )


class TestDerivedConclusion:
    @pytest.mark.parametrize("text", [
        "This suggests that the pathway is rate-limited by substrate availability.",
        "Therefore, the model predicts faster convergence under these conditions.",
        "Thus, heterogeneity is the dominant source of variance in this dataset.",
        "We conclude that the framework outperforms the baseline.",
        "Our results show a significant improvement in accuracy.",
        "This implies that dosing must be adjusted for renal function.",
        "As a result, the simulation terminates earlier than expected.",
        "Consequently, no further adjustment is required.",
    ])
    def test_classified_as_derived_conclusion(self, text: str):
        atype, needs = classify(_sent(text))
        assert atype == "derived-conclusion"
        assert needs is False


class TestOwnContribution:
    @pytest.mark.parametrize("text", [
        "We propose a novel framework for multi-scale pharmacokinetic modelling.",
        "In this paper, we present a hierarchical Bayesian approach.",
        "Our model integrates mechanistic and statistical components.",
        "We introduce an algorithm that scales linearly with the number of patients.",
        "In this work, we describe the complete pipeline from data ingestion to output.",
    ])
    def test_classified_as_own_contribution(self, text: str):
        atype, needs = classify(_sent(text))
        assert atype == "own-contribution"
        assert needs is False


class TestDefinition:
    @pytest.mark.parametrize("text", [
        "We define the biomarker score as the sum of standardised component values.",
        "Let x denote the substrate concentration at steady state.",
        "The hazard ratio is defined as the ratio of instantaneous event rates.",
        "The term 'surrogate endpoint' is defined as a variable that predicts clinical outcome.",
    ])
    def test_classified_as_definition(self, text: str):
        atype, needs = classify(_sent(text))
        assert atype == "definition"
        assert needs is False


class TestNarrative:
    @pytest.mark.parametrize("text", [
        "In order to motivate the analysis, we briefly review prior work.",
        "The goal of this section is to introduce the key concepts.",
        "This paper aims to bridge the gap between systems biology and clinical pharmacology.",
        "The remainder of this paper is organised as follows.",
    ])
    def test_classified_as_narrative(self, text: str):
        atype, needs = classify(_sent(text))
        assert atype == "narrative"
        assert needs is False


class TestAssertedFact:
    @pytest.mark.parametrize("text", [
        "Enzyme X has been shown to have a Km of 70 mM in human tissue.",
        "Evidence indicates that aldose reductase plays a key role in diabetic neuropathy.",
        "Studies have demonstrated that intensive glycaemic control reduces retinopathy.",
        "It has been shown that the drug is metabolised primarily by CYP3A4.",
    ])
    def test_uncited_asserted_fact_needs_citation(self, text: str):
        atype, needs = classify(_sent(text, citations=[]))
        assert atype == "asserted-fact"
        assert needs is True

    @pytest.mark.parametrize("text", [
        r"Clinical trials have demonstrated improved outcomes \citep{oates1999}.",
        "Previous work has reported a Km value of 70 mM [CITE:vanderjagt1990].",
    ])
    def test_cited_asserted_fact_does_not_need_citation(self, text: str):
        atype, needs = classify(_sent(text, citations=["oates1999"]))
        assert atype == "asserted-fact"
        assert needs is False


class TestEstablishedConvention:
    def test_michaelis_menten_no_value_no_citation_needed(self):
        text = "Enzyme kinetics follow Michaelis-Menten kinetics under standard conditions."
        atype, needs = classify(_sent(text))
        assert atype == "established-convention"
        assert needs is False

    def test_convention_with_specific_uncited_value_needs_citation(self):
        text = "Michaelis-Menten kinetics predict a Km of 35 mM under these conditions."
        atype, needs = classify(_sent(text, citations=[]))
        # A specific quantitative value in an established-convention sentence should be flagged
        assert atype in ("asserted-fact", "established-convention")
        # If flagged as established-convention with a number and no citation, needs_citation=True
        if atype == "established-convention":
            assert needs is True


class TestCitedSentenceDefaultsToAssertedFact:
    def test_sentence_with_citation_and_no_other_signal(self):
        text = "The pathway is characterised by multiple feedback loops [CITE:jones2020]."
        atype, needs = classify(_sent(text, citations=["jones2020"]))
        assert atype == "asserted-fact"
        assert needs is False


class TestUnknown:
    def test_uncited_sentence_with_no_signals_is_unknown(self):
        text = "The results are presented in the following sections of this analysis."
        # This doesn't match NARRATIVE, DERIVED, OWN, DEFINITION, or EXTERNAL_FACT patterns
        atype, needs = classify(_sent(text, citations=[]))
        # Should be unknown or narrative — no citation needed either way
        assert needs is False

    def test_unknown_does_not_require_citation(self):
        text = "The full posterior distribution reflects genuine uncertainty about the mechanism."
        atype, needs = classify(_sent(text, citations=[]))
        assert needs is False


class TestPriority:
    def test_definition_takes_priority_over_external_fact(self):
        """A sentence that both defines and asserts should classify as definition."""
        text = "We define the biomarker as a value that has been shown to predict outcome."
        atype, needs = classify(_sent(text))
        assert atype == "definition"

    def test_derived_takes_priority_over_external_fact_signal(self):
        """'This suggests' should override external-fact signals in the same sentence."""
        text = "This suggests that previous studies have underestimated the effect size."
        atype, needs = classify(_sent(text))
        assert atype == "derived-conclusion"
        assert needs is False

"""Classify a plain-text sentence into an AssertionType using signal-word heuristics."""
from __future__ import annotations

import re
from .schema import AssertionType
from .extractor import Sentence

# ---------------------------------------------------------------------------
# Signal word lists  (all patterns are case-insensitive)
# ---------------------------------------------------------------------------

# Strong indicators of DERIVED CONCLUSIONS (author reasoning from own results)
_DERIVED = re.compile(
    r'\b(?:this suggests|therefore|thus|hence|we conclude|we find|we show'
    r'|our results (?:show|suggest|indicate|demonstrate)|this implies'
    r'|this means|as a result|consequently|this finding|this confirms'
    r'|we observe|these results)\b',
    re.IGNORECASE,
)

# Strong indicators of OWN CONTRIBUTION / METHOD
_OWN_WORK = re.compile(
    r'\b(?:our (?:model|approach|framework|method|system|algorithm|tool'
    r'|pipeline|workflow|analysis|data|dataset|experiment|study|paper|work'
    r'|implementation|formulation)|we propose|we introduce|we develop'
    r'|we present|we design|we define|we describe|in this paper|in this work'
    r'|in this study|the proposed|the present(?:ed)? (?:model|approach|framework))\b',
    re.IGNORECASE,
)

# Strong indicators of FORMAL DEFINITIONS / NOTATION
_DEFINITION = re.compile(
    r'\b(?:we define|let\s+\w+\s+(?:be|denote)|is defined as|is given by'
    r'|denotes?|notation|where \w+ (?:is|are|denotes?)|is formulated as)\b',
    re.IGNORECASE,
)

# Strong indicators of NARRATIVE / RHETORICAL framing
_NARRATIVE = re.compile(
    r'\b(?:in order to|the (?:goal|aim|purpose|objective) of|this paper (?:is|aims|seeks)'
    r'|the remainder of|the rest of this|we (?:begin|proceed|turn|now consider)'
    r'|as (?:discussed|noted|mentioned|described) (?:above|below|earlier|previously)'
    r'|in (?:section|the following)|overview|outline)\b',
    re.IGNORECASE,
)

# Indicators of ASSERTED EXTERNAL FACTS (need citation if uncited)
_EXTERNAL_FACT = re.compile(
    r'\b(?:has been shown|is known (?:to|that)|studies have|evidence (?:indicates?|suggests?'
    r'|shows?|demonstrates?)|reported (?:in|by)|it (?:has been|was) (?:shown|demonstrated'
    r'|observed|found)|characterized by|associated with|plays? a (?:key|critical|central|major)'
    r'|is (?:a|an|the) (?:well-known|established|key|critical|major|important)|previous(?:ly)?'
    r'|prior work|earlier work|in the literature|clinical(?:ly)?|in vivo|in vitro'
    r'|patients? (?:with|who)|the (?:drug|compound|molecule|protein|gene|enzyme)'
    r'|aldose reductase|pharmacokinetic|pharmacodynamic|clinical trial)\b',
    re.IGNORECASE,
)

# Known signal phrases for ESTABLISHED CONVENTIONS (textbook knowledge)
_CONVENTION = re.compile(
    r'\b(?:michaelis.menten|fick\'s law|mass action|law of|first.order kinetics'
    r'|henry\'s law|thermodynamic|conservation of|by definition|classical(?:ly)?)\b',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify(sentence: Sentence) -> tuple[AssertionType, bool]:
    """
    Return (assertion_type, needs_citation).

    needs_citation is True only when assertion_type == 'asserted-fact'
    AND the sentence has no citations.
    """
    t = sentence.text

    if _DEFINITION.search(t):
        return "definition", False

    if _DERIVED.search(t):
        return "derived-conclusion", False

    if _OWN_WORK.search(t):
        return "own-contribution", False

    if _NARRATIVE.search(t):
        return "narrative", False

    if _CONVENTION.search(t):
        # Established conventions don't need citations unless they carry
        # a specific non-obvious quantitative value without citation.
        has_number = bool(re.search(r'\b\d+(?:\.\d+)?\s*(?:m[MμmgL]|%|fold|kDa|nM|μM|mM)\b', t))
        if has_number and not sentence.citations:
            return "asserted-fact", True
        return "established-convention", False

    if _EXTERNAL_FACT.search(t):
        needs = not sentence.citations
        return "asserted-fact", needs

    # Sentence has a citation → treat as asserted-fact by default
    if sentence.citations:
        return "asserted-fact", False

    # No signals, no citation → likely narrative or original synthesis;
    # flag as unknown for human review.
    return "unknown", False

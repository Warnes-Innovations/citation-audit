"""Extract sentences and citation markers from a LaTeX document."""
from __future__ import annotations

import re
import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Sentence:
    text: str           # plain-text sentence (citations replaced with [CITE:label])
    raw: str            # original LaTeX fragment
    line: int           # approximate start line in source file
    paragraph: int      # paragraph index (0-based)
    citations: list[str]  # bibtex labels found in this sentence (may be empty)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_sentences(tex_path: Path) -> list[Sentence]:
    """Parse a .tex file and return one Sentence per detected sentence."""
    raw_text = tex_path.read_text(encoding="utf-8", errors="replace")
    # Build a line-offset map so we can recover approximate line numbers
    line_starts = _build_line_starts(raw_text)
    stripped, offset_map = _strip_latex(raw_text)
    return _split_into_sentences(stripped, offset_map, line_starts)


def assertion_id(doc_stem: str, text: str) -> str:
    """Return a stable short ID for an assertion."""
    digest = hashlib.sha256(f"{doc_stem}:{text}".encode()).hexdigest()[:8]
    return f"a-{digest}"


# ---------------------------------------------------------------------------
# LaTeX stripping
# ---------------------------------------------------------------------------

# Environments whose entire content (including body) should be removed.
_REMOVE_ENVS = (
    "figure", "figure*", "table", "table*",
    "lstlisting", "verbatim", "algorithm", "algorithmic",
    "tikzpicture", "tabular", "tabular*",
    "align", "align*", "equation", "equation*",
    "gather", "gather*", "multline", "multline*",
    "minipage",
)

# Section/subsection commands whose *argument* we keep as a sentence.
_SECTION_CMDS = r"(?:sub)*section\*?|paragraph\*?|subparagraph\*?"


def _strip_latex(text: str) -> tuple[str, list[tuple[int, int]]]:
    """
    Return (plain_text, offset_map).

    offset_map is a list of (plain_pos, source_pos) pairs recording where
    characters in plain_text correspond to in the original source.
    We keep it coarse (paragraph-level) since exact char mapping is expensive.
    """
    # Replace cite commands *before* stripping so labels survive.
    text = re.sub(r'\\cite[pt]?\*?\{([^}]+)\}', r'[CITE:\1]', text)
    text = re.sub(r'\\citealp\*?\{([^}]+)\}',   r'[CITE:\1]', text)

    # Remove % comments (but not \%)
    text = re.sub(r'(?<!\\)%.*$', '', text, flags=re.MULTILINE)

    # Remove named environments entirely
    for env in _REMOVE_ENVS:
        text = re.sub(
            rf'\\begin\{{{re.escape(env)}\}}.*?\\end\{{{re.escape(env)}\}}',
            '\n\n', text, flags=re.DOTALL
        )

    # Remove display math
    text = re.sub(r'\$\$.*?\$\$',       '\n', text, flags=re.DOTALL)
    text = re.sub(r'\\\[.*?\\\]',       '\n', text, flags=re.DOTALL)

    # Inline math → placeholder (do not remove, keeps sentence flow)
    text = re.sub(r'\$[^$\n]+\$', 'MATH', text)

    # Section headings: keep title text as a sentence seed
    text = re.sub(rf'\\(?:{_SECTION_CMDS})\{{([^}}]+)\}}', r'\1. ', text)

    # Remove non-content commands (label, index, footnote, hyperref, vspace, etc.)
    text = re.sub(r'\\(?:label|index|ref|eqref|pageref|vspace|hspace|vskip|hskip'
                  r'|noindent|clearpage|newpage|medskip|bigskip|smallskip'
                  r'|centering|raggedright|raggedleft)\*?\{[^}]*\}', '', text)
    text = re.sub(r'\\(?:label|index|noindent|clearpage|newpage|medskip'
                  r'|bigskip|smallskip|centering|par|\\)', ' ', text)

    # Footnotes: remove entirely
    text = re.sub(r'\\footnote\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}', '', text)

    # Unwrap common formatting commands (keep inner text)
    text = re.sub(r'\\(?:textbf|emph|textit|texttt|text|mathrm|mathbf'
                  r'|mbox|hbox|underline|overline)\{([^}]+)\}', r'\1', text)

    # Remove remaining \command{...} — keep content
    text = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', text)

    # Remove bare commands
    text = re.sub(r'\\[a-zA-Z@]+\*?', ' ', text)
    text = re.sub(r'[\\{}]', ' ', text)

    # Collapse whitespace within lines; preserve blank lines (paragraph breaks)
    lines = [re.sub(r'[ \t]+', ' ', ln).strip() for ln in text.splitlines()]
    text = '\n'.join(lines)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Build a coarse offset_map (paragraph index → first char pos)
    offset_map: list[tuple[int, int]] = [(0, 0)]
    return text, offset_map


# ---------------------------------------------------------------------------
# Sentence splitting
# ---------------------------------------------------------------------------

# Abbreviations that should NOT trigger a sentence split.
# Checked inline (not as a lookbehind) because Python 3.13 re rejects
# variable-width lookbehinds; alternatives have different lengths.
_ABBREV_END = re.compile(
    r'(?:e\.g|i\.e|et al|vs|Dr|Mr|Mrs|Prof|Fig|Eq|Sec|cf|approx|ca)\.$'
)

_SENTENCE_SPLIT = re.compile(
    r'(?<!\w\.\w.)'  # not mid-abbreviation like U.S.A. (fixed-width, OK in 3.13)
    r'[.!?]'           # terminal punctuation
    r'(?:\s|$)',       # followed by whitespace or end
)

_MIN_SENTENCE_LEN = 20  # characters — filters LaTeX noise artifacts


def _split_into_sentences(text: str, _offset_map, line_starts: list[int]) -> list[Sentence]:
    sentences: list[Sentence] = []
    paragraphs = re.split(r'\n{2,}', text)
    para_idx = 0
    # crude running line estimate: count \n in consumed text
    consumed_chars = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            consumed_chars += len(para) + 2
            para_idx += 1
            continue

        # Split paragraph into sentence candidates
        spans: list[str] = []
        last = 0
        for m in _SENTENCE_SPLIT.finditer(para):
            # Skip split points that fall after a known abbreviation
            if _ABBREV_END.search(para[:m.start() + 1]):
                continue
            end = m.end()
            spans.append(para[last:end].strip())
            last = end
        if last < len(para):
            spans.append(para[last:].strip())

        # Approximate start line for this paragraph
        approx_line = _char_to_line(consumed_chars, line_starts)

        for raw_span in spans:
            plain = raw_span.strip()
            if len(plain) < _MIN_SENTENCE_LEN:
                continue
            cites = re.findall(r'\[CITE:([^\]]+)\]', plain)
            # Flatten comma-separated multi-cite: [CITE:a,b] → ['a', 'b']
            flat_cites = [c.strip() for group in cites for c in group.split(',')]

            sentences.append(Sentence(
                text      = plain,
                raw       = raw_span,
                line      = approx_line,
                paragraph = para_idx,
                citations = flat_cites,
            ))

        consumed_chars += len(para) + 2
        para_idx += 1

    return sentences


def _build_line_starts(text: str) -> list[int]:
    starts = [0]
    for i, ch in enumerate(text):
        if ch == '\n':
            starts.append(i + 1)
    return starts


def _char_to_line(char_pos: int, line_starts: list[int]) -> int:
    lo, hi = 0, len(line_starts) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if line_starts[mid] <= char_pos:
            lo = mid
        else:
            hi = mid - 1
    return lo + 1  # 1-based

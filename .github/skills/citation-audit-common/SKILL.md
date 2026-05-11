---
description: "Common logic and definitions for citation auditing, alternative source management, and audit artifact structure."
name: "Citation Audit Common"
---

# Citation Audit Common Skill

## Definitions
- `citing document`: The document being audited that contains citation references.
- `citing text`: The exact text in the citing document that contains or surrounds the citation.
- `source document`: The referenced publication or evidence source identified by a bibtex label.
- `source text`: The text from the source document that directly supports or contradicts the citing claim.
- `alternative source`: A publication or evidence source not originally cited, but identified as relevant and supportive for a claim where the original source is unavailable or unsupportive.
- `assertion`: Any sentence or passage in the document making a factual, analytical, or rhetorical claim, whether or not it carries a citation marker.
- `assertion_type`: A classification of what kind of claim an assertion is — determines whether it needs a citation (see Assertion Type Vocabulary below).

## Assertion Type Vocabulary

Every audited assertion (cited or uncited) must be assigned one of the following types and recorded in `index.json` under `assertions` (for uncited passages) or as `assertion_type` on the `CitationRecord` (for cited passages).

| assertion_type | Description | Needs citation? |
|---|---|---|
| `asserted-fact` | A claim about the external world stated as established knowledge (e.g. "Enzyme X has a Km of 70 mM") | **Yes — TARGET** |
| `original-synthesis` | The author's own reasoning, analysis, or interpretive contribution not derived directly from a single citable result | No — do not cite |
| `derived-conclusion` | A conclusion the author draws from results, data, or a model presented in this document ("This suggests…", "Therefore…") | No |
| `own-contribution` | Description of the paper's own model, method, framework, dataset, or experimental design | No |
| `definition` | Formal definition, variable introduction, mathematical notation | No |
| `established-convention` | Universally accepted textbook principle. Skip if purely qualitative. **Reclassify as `asserted-fact` if the claim contains any specific number, range, or unit measurement** (e.g. "half-life of 4 hours", "Km of 70 mM") — regardless of how well-known the underlying concept is. | Judgment call → `asserted-fact` if quantitative |
| `narrative` | Transitional sentences, scope statements, motivational framing with no factual content | No |
| `unknown` | Not yet classified; requires human review | Pending |

**Signal words for classification:**
- Exclude (derived-conclusion): "this suggests", "therefore", "thus", "we conclude", "our results show", "this implies", "we find", "as a result", "consequently".
- Exclude (own-contribution / original-synthesis): "our model", "our approach", "our framework", "we propose", "we introduce", "we present", "in this paper", "in this work".
- Exclude (definition): "we define", "let X denote", "is defined as", "where X is".
- Target (asserted-fact): "has been shown", "is known to", "studies have demonstrated", "evidence indicates", "reported in", specific quantitative values without citation, named phenomena attributed to prior work.

**Critical rule — original-synthesis vs. missing citation**: When a sentence is not derived from a single citable result but represents the author's own analytical contribution, classify it as `original-synthesis` and explicitly record this in `index.json`. This prevents auditors from incorrectly flagging it as a missing citation in future sessions.

## Audit Artifact Structure
- `.audit/<citing-document>/<bibtex-label>/` for each cited source or alternative source.
- `.audit/<citing-document>/assertions/<assertion-id>/` for each recorded uncited assertion.
- Each citation folder contains:
  - `publication.md`: bibliographic details, abstract, and for any local or downloaded source file, include:
    - file name
    - last modification date/time (ISO 8601)
    - content hash (e.g., SHA256)
    - agent version number (e.g., citation-auditor v1.1 or citation-alternatives v1.1)
    This enables the agent to skip reprocessing if the source file and agent version have not changed.
  - URL fields that **must** be populated whenever determinable (used to generate follow-up links in summaries):
    - `doi`: raw DOI string (e.g., `10.1080/13543784.2007.10008044`), extracted from `.bib` or looked up via Google Scholar
    - `doi_url`: `https://doi.org/<doi>` — publisher landing page (paywall or open access)
    - `pubmed_url`: `https://pubmed.ncbi.nlm.nih.gov/<PMID>/` if a PubMed ID is available
    - `scholar_url`: Google Scholar search URL, e.g. `https://scholar.google.com/scholar?q=<title+author+year+encoded>`
    - `open_access_url`: direct PDF link if an open-access version is found (e.g., PubMed Central, bioRxiv, institutional repo)
  - Validation fields that **must** be populated after Bibliographic Field Validation:
    - `confirmation_type`: one of `direct` (Crossref/PubMed/Google Books/WorldCat match with key fields confirmed), `indirect` (title found only in another paper's bibliography), `type_not_in_crossref` (source type — book, proceedings, etc. — not indexed in Crossref/PubMed; treat as neutral score 0 pending manual review), or `none` (no evidence of existence found)
    - `bib_doi_written`: `true` if a DOI was written back to the `.bib` file during this audit run; omit or set `false` otherwise
    - `doi_candidate`: candidate DOI string when validation was ambiguous and write-back was skipped (leave blank if not applicable)
  - Download fields populated after attempting Paper Download (see Paper Download section):
    - `source_file`: `source.pdf` or `source.txt` (omit if download failed)
    - `source_url`: the URL from which the file was downloaded
    - `source_type`: `open_access_pdf`, `pmc_pdf`, `preprint_pdf`, `publisher_text`, or `abstract_only`
    - `download_date`: ISO 8601 date of download
    - `file_sha256`: SHA-256 hash of the downloaded file (for change detection and deduplication)
    - `library_path`: relative path to the file in the shared paper library if deduplication applied (mutually exclusive with `source_file`)
  - `source.pdf` or `source.txt`: downloaded full text or extracted text of the referenced paper (see Paper Download)
  - `citation_<label>.md`: citing text, `assertion_type` of the citing claim, source text, support score, and notes
  - `summary.md`: summary for that source/citation
- Each uncited assertion folder (`.audit/<citing-document>/assertions/<id>/`) contains:
  - `assertion.md`: exact text, location, `assertion_type`, classification rationale, and any citation recommendation
- Document-scoped metadata in `.audit/<citing-document>/index.json` and `.audit/<citing-document>/summary.md`.
- Do not create global `.audit/index.json` or `.audit/summary.md` outside document folders.

## index.json Schema

The document-scoped `index.json` has two top-level keys:

```json
{
  "document":   "knowledge-system.tex",
  "audit_date": "2026-05-09",
  "citations": {
    "<bibtex-label>": {
      "bibtex_label":        "<label>",
      "reference_text":      "<formatted reference>",
      "confirmation_type":   "direct | indirect | none",
      "confirmation_source": "<URL or description>",
      "bib_mismatches":      ["field: old → new"],
      "score":               90,
      "score_reason":        "<explanation>",
      "assertion_type":      "<assertion_type of the citing claim>",
      "status":              "active | superseded"
    }
  },
  "assertions": {
    "a-<hash>": {
      "id":             "a-<hash>",
      "text":           "<exact sentence text>",
      "location":       "line ~1234 / Section 3.2",
      "assertion_type": "original-synthesis",
      "citation_label": null,
      "needs_citation": false,
      "notes":          "<rationale>"
    }
  }
}
```

Use the `citation-audit` CLI or MCP tool to read and write `index.json` atomically rather than editing it by hand.

Assertion IDs are stable hashes: `"a-" + sha256(f"{doc_stem}:{text}")[:8]` where `doc_stem` is the citing document filename without extension and `text` is the exact assertion sentence. Use the `compute_assertion_id` MCP tool to generate IDs consistently — do not compute them manually.

## Link Rendering in Outputs
Whenever a citation is listed in any agent output or summary, render it as a set of inline markdown links using the URL fields above. Include only links that are populated:
- `[DOI](doi_url)` — publisher page
- `[PubMed](pubmed_url)` — if available
- `[Scholar](scholar_url)` — Google Scholar search
- `[Open Access PDF](open_access_url)` — if found

Example for Oates 1999 (`doi = 10.1517/13543784.8.12.2095`; directly confirmed via Crossref):
> Oates and Mylari 1999 — [DOI](https://doi.org/10.1517/13543784.8.12.2095) [Scholar](https://scholar.google.com/scholar?q=Oates+Mylari+aldose+reductase+inhibitors+1999)

## Bibliographic Field Validation (Required for Every Citation)

Finding a title in another paper's bibliography is **not sufficient** to confirm a citation. Every citation audit **must** perform direct validation against an authoritative database before assigning any score above −100.

### Required validation steps (in order):
1. **If the `.bib` entry has a `doi`**: fetch `https://api.crossref.org/works/<doi>`. An HTTP 4xx/5xx response means the DOI is invalid — score ≤ −100 regardless of any other evidence.
2. **If the `.bib` entry has no `doi`**, or if step 1 fails: search Crossref (`https://api.crossref.org/works?query=<title>&query.author=<author>&rows=3`) and/or PubMed (`https://pubmed.ncbi.nlm.nih.gov/?term=<author>+<year>+<title-words>`) to locate the paper.
   - **2b. Non-journal sources** — if the `.bib` entry type is `book`, `incollection`, or `inproceedings`, Crossref and PubMed coverage is limited. In that case:
     - Try Google Books (`https://books.google.com/books?q=<isbn-or-title+author>`) or WorldCat (`https://www.worldcat.org/search?q=<title>`) as authoritative fallbacks. A confirmed match sets `confirmation_type: direct`.
     - If no database confirms the source, record `confirmation_type: type_not_in_crossref` and treat the score as neutral (0) pending manual review — do **not** score ≤ −100 solely because the source type is not indexed in Crossref.
3. **Cross-check ALL key fields** from the authoritative source against the `.bib` entry:
   - year, volume, number/issue, pages, journal name, author list
   - **Major mismatch** (author name, year, or journal name differs): the wrong paper was almost certainly cited — score ≤ −100 and record the discrepancy in `publication.md`.
   - **Minor variance** (page numbers, volume/issue, or title wording slightly differ but the paper is clearly the same): propose the corrected `.bib` field to the user and wait for explicit approval before writing it; record the correction in `publication.md` and apply no score penalty once approved.
4. **Indirect confirmation only** (title found in another paper's bibliography but no direct database match) is scored **≤ 0**, never positive. Record it as `confirmation_type: indirect` in `publication.md`.
5. **Direct confirmation** (Crossref, PubMed, Google Books, or WorldCat returns the source with matching key fields) is required for any score above 0.

> **Crossref polite pool**: Include `?mailto=<email>` in all Crossref API requests (e.g., `https://api.crossref.org/works/<doi>?mailto=user@example.com`). This places requests in the polite pool and avoids rate-limiting when auditing documents with many citations.

### Confirmation type vocabulary (record in `publication.md`):
- `confirmation_type: direct` — Crossref, PubMed, Google Books, or WorldCat returned the source with matching title, author, year, and journal/publisher
- `confirmation_type: indirect` — title found in another paper's bibliography or secondary source only
- `confirmation_type: type_not_in_crossref` — source type (book, proceedings, etc.) not covered by Crossref/PubMed; no authoritative database confirmed or denied it; treat as neutral (score 0) pending manual review
- `confirmation_type: none` — no evidence of existence found in any database

## Paper Download

Whenever a citation is confirmed (via Crossref, PubMed, or another authoritative database), attempt to retrieve and store the full text or PDF of the referenced paper. This enables support scoring from actual source text rather than title/abstract inference alone, and builds a persistent local library.

### Download attempt sequence (try in order):
1. **Unpaywall** — fetch `https://api.unpaywall.org/v2/<doi>?email=<email>`. If `best_oa_location.url_for_pdf` is non-null, download the PDF.
2. **PubMed Central** — if the PubMed API response includes a `pmcid`, fetch `https://www.ncbi.nlm.nih.gov/pmc/articles/<PMCID>/pdf/`.
3. **bioRxiv / medRxiv** — query `https://api.biorxiv.org/details/biorxiv/<doi>` for a preprint version.
4. **Semantic Scholar** — fetch `https://api.semanticscholar.org/graph/v1/paper/DOI:<doi>?fields=openAccessPdf`; use `openAccessPdf.url` if present.
5. **Publisher landing page** — as a last resort, fetch `doi_url` and extract any readable text (abstract + available body text). Save as `source.txt`.

### Skip download when:
- `confirmation_type` is `none` (paper does not exist — no file to fetch).
- `source.pdf` or `source.txt` already exists in the artifact folder **and** `file_sha256` in `publication.md` matches the file on disk — avoid re-downloading unchanged files.
- The file size exceeds **100 MB** — check `Content-Length` before downloading; if unavailable, abort and discard after the first 100 MB are received. Set `source_type: oversized` in `publication.md` and fall back to abstract-only.

### Storage:
- Save the file as `.audit/<citing-document>/<bibtex-label>/source.pdf` (binary PDF) or `.audit/<citing-document>/<bibtex-label>/source.txt` (extracted text).
- Record in `publication.md`: `source_file`, `source_url`, `source_type`, `download_date` (ISO 8601), and `file_sha256` (SHA-256 hex digest).
- If no file is downloadable, set `source_type: abstract_only` and record the abstract inline in `publication.md` under `abstract`.

### Shared library deduplication:
- The shared paper library lives in a separate private Git repository (default clone location: `~/.citation-papers`; override with the `PAPER_LIBRARY_PATH` environment variable).
- Before downloading any paper, call `get_library_entry(doi)`. If `found: true` and `local_path` is non-null, use the existing file and skip download.
- If not found or the file is absent, call `store_library_paper(doi, ...)` which runs the download sequence above and persists the result.
- After a citation is confirmed, call `record_citing_doc(doi, doc)` to register the citing document against the library entry.
- `citing_docs` entries use the **CitingRef** structure:
  ```json
  { "github": "Warnes-Innovations/multiscale-knowledge", "path": "knowledge-system.tex" }
  ```
  When no GitHub remote is detectable:
  ```json
  { "path": "knowledge-system.tex", "local_path": "/Users/warnes/src/project/knowledge-system.tex" }
  ```
  The `github` field takes the form `Owner/repo` matching the repository's GitHub remote. `path` is always the document path relative to the repository root.

### Scoring impact:
- When assigning the support score, prefer evidence drawn from the downloaded source text (introduction, results, discussion) over title-only inference.
- If only `source_type: abstract_only` is available, cap the score at +50 unless the abstract directly quotes or measures the claimed fact.

## Support Score Scale
- -100: explicitly contradicts / source does not exist / DOI resolves to wrong paper or 4xx / no relevant text found
- -75: strongly contradicts or source evidence is opposite of the claim
- -50: moderate contradiction; the source largely fails to support the claim or points in the opposite direction
- -25: weak contradiction or only tangential relevance; the source does not support the claim in a meaningful way
- 0: neutral or ambiguous evidence; OR paper existence only indirectly confirmed (not in Crossref/PubMed directly)
- +25: modest support; paper directly confirmed but claim support is partial
- +50: moderate support; paper directly confirmed and source supports the claim but with caveats or partial coverage
- +75: strong support; paper directly confirmed and source clearly supports the claim with relevant evidence
- +100: explicitly supports the claim; paper directly confirmed and source text is an exact match

## BibTeX Write-Back
If a `doi` is discovered or confirmed during auditing, write it back to the source `.bib` file **only when all of the following conditions are met**:
1. The Crossref API (`https://api.crossref.org/works/<doi>`) returned HTTP 200 during Bibliographic Field Validation step 1 — reuse that result; do not fetch `doi.org` again.
2. The Crossref response confirms the correct title and at least one author match the `.bib` entry.
3. The `.bib` entry does not already have a `doi` field.

When all conditions are met, add `doi = {<doi>}` as a new field to the matching entry in the `.bib` file. Record that the write-back was performed in `publication.md` (field: `bib_doi_written: true`).

If validation fails or is ambiguous, record the candidate DOI in `publication.md` under `doi_candidate` and leave the `.bib` file unchanged.

## Citing Document Edit Proposals

When an audit finding requires a change to the citing document (`.tex` or `.md`) — not just to `.bib` — **never apply it silently**. Always present a numbered proposal and wait for explicit approval before writing.

### Trigger conditions

| Condition | Proposed action |
|---|---|
| Over-attributed claim: citing text asserts something the confirmed source does not say | Propose (a) inserting an additional `\citep{}` for the specific sub-claim, (b) softening the sentence to match the source, or both |
| Missing citation on an `asserted-fact` sentence | Propose `\citep{<label>}` insertion after the relevant clause |
| Replacement citation found by `citation-alternatives` | Propose swapping the `\citep{}` label |
| BibTeX-only fix (field mismatch in `.bib`) | No citing-document edit needed — `.bib` write-back is separate |

### Proposal format

Present each proposed edit as a numbered block:

> **Proposed edit #N — `<label>` — `<one-line reason>`**
>
> **Old:** `…exact current source text including surrounding \citep{} context…`
> **New:** `…exact replacement text…`
> **Rationale:** one sentence explaining why.

List all proposals together at the end of the audit summary, after the score table and before "Citations Requiring User Review". Do not apply any edit until the user explicitly approves it (e.g. "yes", "apply", "apply #2", "apply all").

### Approval workflow
1. After completing the audit, collect all proposed edits and launch an `/obo` (`/OneByOne`) session with one edit per item.
2. Present each edit in the proposal format above. The user approves, skips, or rejects each item individually.
3. Apply each approved edit immediately with file-editing tools.
4. Record each applied edit under `citing_doc_edits` in `index.json` and append it to `summary.md` under "Changes Applied".

### `citing_doc_edits` schema (in `index.json`)

```json
"citing_doc_edits": [
  {
    "edit_date": "2026-05-11",
    "label": "<bibtex-label>",
    "reason": "<one-line>",
    "old_text": "…",
    "new_text": "…",
    "status": "applied | rejected | pending"
  }
]
```

### What not to change
- Do not rewrite author prose beyond what is needed to correct the citation marker or immediately surrounding clause.
- Do not add inline explanatory text, footnotes, or new sentences.
- Do not remove, reorder, or rename sections.
- Limit each proposed edit to ≤ 5 lines of the source file.

## LLM-Assisted Candidate Discovery

When primary database searches (Crossref, PubMed, Google Scholar) return fewer than 2 candidates that score ≥ +50 for an assertion, agents may query an available LLM to surface additional candidate papers.

### Recommended prompt
> "What peer-reviewed papers provide direct evidence for the following claim? Please give author(s), title, journal, year, and DOI for each: [exact assertion text]"

### Critical rules
- Treat **all** LLM-suggested citations as **unverified leads**. LLMs frequently hallucinate plausible-sounding but non-existent DOIs, author combinations, or journal names.
- **Every** suggestion must pass the full Bibliographic Field Validation sequence (Crossref DOI fetch → HTTP 200 + field match, or PubMed title+author search) before it may be scored or proposed.
- A suggestion that fails Crossref/PubMed validation must be discarded — do not record it in any artifact.
- **Expected yield**: roughly 1 in 3 LLM-suggested citations will be verifiable and usable. This is acceptable; treat the LLM as a brainstorming step, not an authoritative source.
- Record which candidates originated from an LLM query in `publication.md` under `discovery_method: llm-assisted` so future audits can distinguish them from database-sourced candidates.

### Suitable LLM query surfaces
- DuckDuckGo AI chat (free, no login required)
- Perplexity.ai
- Any chat model available in the current agent environment

### When to use
| Agent | Trigger |
|---|---|
| Citation Finder | Phase 2: primary Crossref/PubMed search returns < 2 candidates |
| Citation Alternatives | Step 4: Scholar search returns < 2 directly-confirmed candidates |
| Citation Auditor | Step 6: citation cannot be confirmed and Scholar also returns no match |

## Exclusion
- Any source or citation can be marked as "no longer cited". Excluded items must be omitted from audit summaries and indexes.

## citation-audit Tooling

A shared CLI and MCP server (`citation-audit`) implements the mechanical operations so agents do not spend tokens on them. **Prefer the tool over manual file I/O wherever possible.**

### CLI (`citation-audit`)
```
citation-audit extract <doc> [--only all|cited|uncited|needs-citation] [--format json|table]
citation-audit scaffold <doc> <label>
citation-audit scaffold-assertion <doc> <id> --text "..."
citation-audit update-citation <doc> <label> [--score N] [--confirmation TYPE]
    [--assertion-type TYPE] [--bib-mismatch "field: A → B"] [--score-reason "..."]
    [--status STATUS]
citation-audit tag-assertion <doc> <id> --type TYPE [--text "..."] [--notes "..."]
citation-audit list <doc> [--what citations|assertions|both] [--format json|table]
citation-audit report <doc> [--format markdown|json]
citation-audit library list [--format table|json]
citation-audit library get <doi> [--format json|text]
citation-audit library add <doi> [--title ...] [--authors ...] [--year N] [--doc <path>]
citation-audit library open <doi>
citation-audit library export-bib [-o <file>]
citation-audit library cite <doi> <doc>
```

### MCP tools (server name: `citation-audit`)
| Tool | Purpose |
|---|---|
| `extract_assertions` | Parse `.tex`/`.md` and return classified assertion list |
| `get_audit_status` | Return full index.json for a document |
| `scaffold_citation` | Create citation artifact stubs |
| `scaffold_assertion_artifact` | Create uncited-assertion artifact stub |
| `update_citation_record` | Patch citation fields in index.json |
| `tag_assertion` | Record or update assertion_type for an uncited passage |
| `list_assertions` | Filtered list of assertion records |
| `compute_assertion_id` | Return stable ID for a sentence |
| `get_library_entry` | Look up a paper by DOI in the shared library; returns file path if present |
| `store_library_paper` | Download and store a paper; enforces 100 MB cap; skips if already present |
| `record_citing_doc` | Append a CitingRef to a library entry (idempotent) |
| `list_library` | List all library entries as JSON or summary |

### When to use each
- **`extract_assertions`**: at the start of any citation-finder or assertion-audit session — replaces the agent reading the full source document itself.
- **`update_citation_record` / `tag_assertion`**: after completing a CrossRef/PubMed lookup or classifying an assertion — replaces manual JSON edits.
- **`get_audit_status`**: at the start of a session to restore prior state without re-auditing.
- **`scaffold_citation`**: immediately after identifying a new citation, before fetching source metadata.
- **`get_library_entry`**: call before any download attempt; if `found: true` with a `local_path`, use the existing file.
- **`store_library_paper`**: call after Bibliographic Field Validation succeeds (`confirmation_type: direct`) to download and register the paper.
- **`record_citing_doc`**: call whenever a citation is confirmed for a document, even if the paper was already in the library.

## Usage
- This skill is imported by citation-auditor, citation-alternatives, and citation-finder agents for consistent logic, definitions, and artifact structure.

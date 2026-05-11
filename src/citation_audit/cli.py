"""citation-audit CLI — extract, scaffold, update, and report on citation audits."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from .core import extractor, classifier, index as idx_mod, scaffold as scf_mod
from .core import library as lib_mod
from .core.library import CitingRef, LibraryEntry
from .core.schema import AssertionRecord, CitationRecord
from .core.extractor import assertion_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve(doc: str) -> Path:
    p = Path(doc).expanduser().resolve()
    if not p.exists():
        click.echo(f"error: file not found: {p}", err=True)
        sys.exit(1)
    return p


def _as_json(obj) -> str:
    return json.dumps(obj, indent=2)


# ---------------------------------------------------------------------------
# CLI root
# ---------------------------------------------------------------------------

@click.group()
@click.version_option()
def main():
    """citation-audit — CLI for citation auditing and assertion classification."""


# ---------------------------------------------------------------------------
# extract
# ---------------------------------------------------------------------------

@main.command("extract")
@click.argument("doc")
@click.option("--format", "fmt", type=click.Choice(["json", "table"]), default="json",
              show_default=True, help="Output format.")
@click.option("--only", type=click.Choice(["cited", "uncited", "needs-citation", "all"]),
              default="all", show_default=True)
def cmd_extract(doc: str, fmt: str, only: str):
    """
    Parse DOC (.tex or .md) and classify every sentence.

    Outputs structured assertion records.  Use --only to filter:
    cited        = sentences that already have a citation marker
    uncited      = sentences with no citation marker
    needs-citation = asserted-facts with no citation (ready for citation-finder)
    """
    p = _resolve(doc)
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
            "id":             assertion_id(p.stem, s.text),
            "text":           s.text,
            "location":       f"line ~{s.line}",
            "assertion_type": atype,
            "citation_label": s.citations[0] if len(s.citations) == 1 else (s.citations or None),
            "needs_citation": needs,
        })

    if fmt == "json":
        click.echo(_as_json(records))
    else:
        click.echo(f"{'ID':<12}  {'TYPE':<22}  {'CITE?':<6}  TEXT")
        click.echo("-" * 90)
        for r in records:
            label = r["citation_label"] or ""
            if isinstance(label, list):
                label = ",".join(label)
            snippet = str(r["text"])[:55].replace("\n", " ")
            click.echo(f"{r['id']:<12}  {r['assertion_type']:<22}  "
                       f"{'YES' if r['needs_citation'] else '':<6}  {snippet}")


# ---------------------------------------------------------------------------
# scaffold
# ---------------------------------------------------------------------------

@main.command("scaffold")
@click.argument("doc")
@click.argument("label")
def cmd_scaffold(doc: str, label: str):
    """Create .audit/<doc>/<label>/ stub artifact files."""
    p = _resolve(doc)
    folder = scf_mod.scaffold_citation(p, label)
    click.echo(f"scaffolded: {folder}")


@main.command("scaffold-assertion")
@click.argument("doc")
@click.argument("assertion_id_arg", metavar="ASSERTION_ID")
@click.option("--text", required=True, help="Exact assertion text.")
def cmd_scaffold_assertion(doc: str, assertion_id_arg: str, text: str):
    """Create .audit/<doc>/assertions/<id>/ stub for an uncited assertion."""
    p = _resolve(doc)
    folder = scf_mod.scaffold_assertion(p, assertion_id_arg, text)
    click.echo(f"scaffolded: {folder}")


# ---------------------------------------------------------------------------
# update-citation
# ---------------------------------------------------------------------------

@main.command("update-citation")
@click.argument("doc")
@click.argument("label")
@click.option("--score",            type=int,   default=None)
@click.option("--confirmation",     type=click.Choice(["direct", "indirect", "none"]), default=None)
@click.option("--assertion-type",   default=None,
              type=click.Choice(["asserted-fact", "original-synthesis", "derived-conclusion",
                                  "own-contribution", "definition",
                                  "established-convention", "narrative", "unknown"]))
@click.option("--bib-mismatch",     multiple=True,
              help="Repeat for each mismatch, e.g. \"journal: A → B\"")
@click.option("--score-reason",     default=None)
@click.option("--reference-text",   default=None)
@click.option("--confirmation-source", default=None)
def cmd_update_citation(doc, label, score, confirmation, assertion_type,
                        bib_mismatch, score_reason, reference_text, confirmation_source):
    """
    Patch one or more fields on a citation record in index.json.

    Creates the record if it does not yet exist.
    """
    p = _resolve(doc)
    idx = idx_mod.load(p)
    if label not in idx.citations:
        idx.citations[label] = CitationRecord(bibtex_label=label)
        idx_mod.save(p, idx)  # persist so patch_citation can reload it below

    fields = {}
    if score is not None:               fields["score"] = score
    if confirmation is not None:        fields["confirmation_type"] = confirmation
    if assertion_type is not None:      fields["assertion_type"] = assertion_type
    if bib_mismatch:                    fields["bib_mismatches"] = list(bib_mismatch)
    if score_reason is not None:        fields["score_reason"] = score_reason
    if reference_text is not None:      fields["reference_text"] = reference_text
    if confirmation_source is not None: fields["confirmation_source"] = confirmation_source

    rec = idx_mod.patch_citation(p, label, **fields)
    click.echo(_as_json(rec.to_dict()))


# ---------------------------------------------------------------------------
# tag-assertion
# ---------------------------------------------------------------------------

@main.command("tag-assertion")
@click.argument("doc")
@click.argument("assertion_id_arg", metavar="ASSERTION_ID")
@click.option("--type", "atype", required=True,
              type=click.Choice(["asserted-fact", "original-synthesis", "derived-conclusion",
                                  "own-contribution", "definition",
                                  "established-convention", "narrative", "unknown"]),
              help="Assertion type classification.")
@click.option("--text",  default=None, help="Assertion text (required for new assertions).")
@click.option("--location", default=None)
@click.option("--citation-label", default=None)
@click.option("--notes", default="")
def cmd_tag_assertion(doc, assertion_id_arg, atype, text, location, citation_label, notes):
    """
    Record or update the assertion_type for an assertion in index.json.

    Use this to mark uncited passages as original-synthesis, derived-conclusion, etc.
    """
    p = _resolve(doc)
    idx = idx_mod.load(p)

    if assertion_id_arg in idx.assertions:
        rec = idx_mod.patch_assertion(p, assertion_id_arg,
                                      assertion_type=atype,
                                      notes=notes or idx.assertions[assertion_id_arg].notes)
    else:
        if not text:
            click.echo("error: --text is required for new assertions", err=True)
            sys.exit(1)
        rec = AssertionRecord(
            id             = assertion_id_arg,
            text           = text,
            location       = location or "",
            assertion_type = atype,
            citation_label = citation_label,
            needs_citation = (atype == "asserted-fact"),
            notes          = notes,
        )
        idx_mod.upsert_assertion(p, rec)

    click.echo(_as_json(rec.to_dict()))


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

@main.command("list")
@click.argument("doc")
@click.option("--format", "fmt", type=click.Choice(["json", "table"]), default="table",
              show_default=True)
@click.option("--what", type=click.Choice(["citations", "assertions", "both"]),
              default="both", show_default=True)
def cmd_list(doc: str, fmt: str, what: str):
    """Show all citations and/or assertions recorded in index.json."""
    p = _resolve(doc)
    idx = idx_mod.load(p)

    if fmt == "json":
        out = {}
        if what in ("citations", "both"):
            out["citations"]  = {k: v.to_dict() for k, v in idx.citations.items()}
        if what in ("assertions", "both"):
            out["assertions"] = {k: v.to_dict() for k, v in idx.assertions.items()}
        click.echo(_as_json(out))
        return

    if what in ("citations", "both"):
        click.echo(f"\n{'LABEL':<38}  {'SCORE':>6}  {'CONF':<10}  {'ASSERTION TYPE'}")
        click.echo("-" * 80)
        for k, v in idx.citations.items():
            click.echo(f"{k:<38}  {v.score:>6}  {v.confirmation_type:<10}  {v.assertion_type}")

    if what in ("assertions", "both"):
        click.echo(f"\n{'ID':<14}  {'TYPE':<22}  {'CITE?':<6}  TEXT")
        click.echo("-" * 80)
        for aid, arec in idx.assertions.items():
            snippet = arec.text[:45].replace("\n", " ")
            click.echo(f"{aid:<14}  {arec.assertion_type:<22}  "
                       f"{'YES' if arec.needs_citation else '':<6}  {snippet}")


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

@main.command("report")
@click.argument("doc")
@click.option("--format", "fmt", type=click.Choice(["json", "markdown"]),
              default="markdown", show_default=True)
def cmd_report(doc: str, fmt: str):
    """Print a concise audit summary for DOC."""
    p = _resolve(doc)
    idx = idx_mod.load(p)

    if fmt == "json":
        click.echo(_as_json(idx.to_dict()))
        return

    scores = [v.score for v in idx.citations.values()]
    uncited_facts = [v for v in idx.assertions.values() if v.needs_citation]
    unknown_type  = [v for v in idx.assertions.values() if v.assertion_type == "unknown"]

    click.echo(f"# Audit Report — {idx.document}\n")
    click.echo(f"- **Audit date**: {idx.audit_date}")
    click.echo(f"- **Citations audited**: {len(idx.citations)}")
    click.echo(f"- **Assertions recorded**: {len(idx.assertions)}")
    if scores:
        click.echo(f"- **Min score**: {min(scores)}")
        click.echo(f"- **Mean score**: {sum(scores)//len(scores)}")
    if uncited_facts:
        click.echo(f"- **Uncited asserted-facts**: {len(uncited_facts)}")
    if unknown_type:
        click.echo(f"- **Unclassified assertions**: {len(unknown_type)}")

    click.echo("\n## Citations\n")
    click.echo("| Label | Score | Conf | Assertion Type |")
    click.echo("|---|---|---|---|")
    for k, v in sorted(idx.citations.items(), key=lambda x: x[1].score):
        click.echo(f"| `{k}` | {v.score} | {v.confirmation_type} | {v.assertion_type} |")

    if idx.assertions:
        click.echo("\n## Assertions\n")
        click.echo("| ID | Type | Needs Cite | Text |")
        click.echo("|---|---|---|---|")
        for aid, arec in idx.assertions.items():
            snippet = arec.text[:60].replace("|", "\\|").replace("\n", " ")
            click.echo(f"| `{aid}` | {arec.assertion_type} | {'yes' if arec.needs_citation else ''} | {snippet} |")


# ---------------------------------------------------------------------------
# library
# ---------------------------------------------------------------------------

@main.group("library")
def cmd_library():
    """Manage the shared paper library (~/.citation-papers or $PAPER_LIBRARY_PATH)."""


def _require_library_root() -> "Path":
    root = lib_mod.library_root()
    if root is None:
        click.echo(
            "error: paper library not found.\n"
            "Set PAPER_LIBRARY_PATH or clone citation-papers to ~/.citation-papers",
            err=True,
        )
        sys.exit(1)
    return root


@cmd_library.command("list")
@click.option("--format", "fmt", type=click.Choice(["table", "json"]),
              default="table", show_default=True)
def cmd_library_list(fmt: str):
    """List all papers in the library."""
    root = _require_library_root()
    entries = lib_mod.load_library(root)
    if fmt == "json":
        click.echo(_as_json([e.to_dict() for e in entries.values()]))
        return
    click.echo(f"{'DOI / KEY':<45}  {'YEAR':>4}  {'TYPE':<18}  TITLE")
    click.echo("-" * 100)
    for key, e in entries.items():
        title = (e.title or "")[:40]
        year = str(e.year) if e.year else ""
        click.echo(f"{key:<45}  {year:>4}  {e.source_type:<18}  {title}")


@cmd_library.command("get")
@click.argument("doi")
@click.option("--format", "fmt", type=click.Choice(["json", "text"]),
              default="json", show_default=True)
def cmd_library_get(doi: str, fmt: str):
    """Show the library entry for DOI."""
    root = _require_library_root()
    entry = lib_mod.get_entry(root, doi)
    if entry is None:
        click.echo(f"error: DOI '{doi}' not found in library", err=True)
        sys.exit(1)
    if fmt == "json":
        click.echo(_as_json(entry.to_dict()))
    else:
        click.echo(f"Title:   {entry.title}")
        click.echo(f"Authors: {'; '.join(entry.authors)}")
        click.echo(f"Year:    {entry.year}")
        click.echo(f"Journal: {entry.journal}")
        click.echo(f"DOI:     {entry.doi}")
        click.echo(f"File:    {entry.filename or '(none)'}")
        click.echo(f"Type:    {entry.source_type}")
        if entry.citing_docs:
            click.echo("Cited by:")
            for r in entry.citing_docs:
                loc = f"{r.github}/{r.path}" if r.github else (r.local_path or r.path)
                click.echo(f"  {loc}")


@cmd_library.command("add")
@click.argument("doi")
@click.option("--title",   default="", help="Paper title.")
@click.option("--authors", default="", help="Semicolon-separated author list.")
@click.option("--year",    type=int,   default=None)
@click.option("--journal", default="")
@click.option("--email",   default=None, help="E-mail for Unpaywall/Crossref polite pool.")
@click.option("--doc",     default=None,
              help="Citing document path; auto-detects GitHub remote.")
def cmd_library_add(doi: str, title: str, authors: str, year, journal: str,
                    email, doc):
    """Add a paper by DOI and attempt to download it."""
    root = _require_library_root()
    citing: list[CitingRef] = []
    if doc:
        citing.append(CitingRef.from_doc_path(Path(doc)))
    entry = LibraryEntry(
        doi         = doi,
        title       = title,
        authors     = [a.strip() for a in authors.split(";") if a.strip()],
        year        = year,
        journal     = journal,
        citing_docs = citing,
    )
    kw = {}
    if email:
        kw["email"] = email
    entry = lib_mod.store_paper(root, entry, **kw)
    click.echo(f"stored: {entry.filename or '(no file — ' + entry.source_type + ')'}")
    click.echo(f"sha256: {entry.sha256 or 'n/a'}")


@cmd_library.command("open")
@click.argument("doi")
def cmd_library_open(doi: str):
    """Print the local file path for DOI (or its doi_url if no local file)."""
    root = _require_library_root()
    entry = lib_mod.get_entry(root, doi)
    if entry is None:
        click.echo(f"error: DOI '{doi}' not found in library", err=True)
        sys.exit(1)
    if entry.filename:
        fpath = lib_mod.papers_dir(root) / entry.filename
        if fpath.exists():
            click.echo(str(fpath))
            return
    click.echo(f"https://doi.org/{doi}")


@cmd_library.command("export-bib")
@click.option("--output", "-o", default=None,
              help="Output .bib file path.  Prints to stdout if omitted.")
def cmd_library_export_bib(output):
    """Export all library entries as a BibTeX file."""
    root = _require_library_root()
    entries = lib_mod.load_library(root)
    lines: list[str] = []
    for key, e in entries.items():
        bkey = lib_mod.doi_slug(e.doi) if e.doi else key.replace("sha256:", "sha256_")
        lines.append(f"@article{{{bkey},")
        if e.title:   lines.append(f"  title   = {{{e.title}}},")
        if e.authors: lines.append(f"  author  = {{{' and '.join(e.authors)}}},")
        if e.year:    lines.append(f"  year    = {{{e.year}}},")
        if e.journal: lines.append(f"  journal = {{{e.journal}}},")
        if e.doi:     lines.append(f"  doi     = {{{e.doi}}},")
        if e.pmid:    lines.append(f"  pmid    = {{{e.pmid}}},")
        lines.append("}\n")
    bib_text = "\n".join(lines)
    if output:
        Path(output).write_text(bib_text)
        click.echo(f"written: {output}")
    else:
        click.echo(bib_text)


@cmd_library.command("cite")
@click.argument("doi")
@click.argument("doc")
def cmd_library_cite(doi: str, doc: str):
    """Record that DOC cites the paper identified by DOI."""
    root = _require_library_root()
    ref = CitingRef.from_doc_path(Path(doc))
    try:
        lib_mod.add_citing_doc(root, doi, ref)
        click.echo(f"recorded citing reference: {ref.path}")
    except KeyError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)

---
applyTo: "**"
---

# citation-audit — Project Instructions

## What this repo is

A Python CLI, MCP server, VS Code Copilot agents, and shared skill for auditing
citations in LaTeX and Markdown documents.

Entry points:
- `citation-audit` — Click CLI
- `citation-audit-mcp` — FastMCP server for use with VS Code / Claude / Cline

Agents (auto-discovered by VS Code when this repo is in the workspace):
- `.github/agents/citation-auditor.agent.md`
- `.github/agents/citation-alternatives.agent.md`
- `.github/agents/citation-finder.agent.md`

Shared skill (linked into `~/.codex/skills/` and `~/.copilot/skills/` by `install.sh`):
- `.github/skills/citation-audit-common/SKILL.md`

## Build & test

```bash
# Install editable with dev deps (requires uv)
uv sync --extra dev

# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=citation_audit --cov-report=term-missing
```

## Package layout

```
src/citation_audit/
    __init__.py
    cli.py              # Click CLI entry point
    mcp_server.py       # FastMCP server entry point
    core/
        schema.py       # AssertionRecord, CitationRecord, AuditIndex dataclasses
        index.py        # Atomic read/write of .audit/<doc>/index.json
        scaffold.py     # Create .audit/<doc>/<label>/ stub files
        extractor.py    # Parse .tex/.md → list[Sentence]
        classifier.py   # classify(Sentence) → (AssertionType, needs_citation)
tests/
    conftest.py         # Shared fixtures (tmp_tex, tmp_cite_tex, tmp_doc_with_index)
    test_schema.py
    test_index.py
    test_scaffold.py
    test_extractor.py
    test_classifier.py
    test_cli.py         # Uses click.testing.CliRunner
    test_mcp_tools.py   # Calls MCP tool functions directly (no transport)
.github/
    agents/
        citation-auditor.agent.md       # validates citations, scores support
        citation-alternatives.agent.md  # finds replacement sources
        citation-finder.agent.md        # discovers uncited assertions
    skills/
        citation-audit-common/
            SKILL.md    # shared definitions, scoring scale, artifact schema
```

## Conventions

- Python ≥ 3.11, `from __future__ import annotations` in every module
- All public functions use type hints
- No external HTTP calls in this package — callers (agents) do HTTP themselves
- `.audit/` directories are created relative to the source document's parent
- `index.json` is written atomically via `tempfile + os.replace`
- Assertion IDs are `"a-" + sha256(f"{doc_stem}:{text}")[:8]`

## Do not

- Add new dependencies without updating `pyproject.toml`
- Make HTTP requests from within this package
- Write to `.audit/` outside the functions in `core/scaffold.py` and `core/index.py`
- Change the `assertion_id()` hash scheme (breaks existing IDs in audit artifacts)

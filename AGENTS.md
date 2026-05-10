# AGENTS.md — citation-audit

## What this repo is

Python CLI, MCP server, VS Code Copilot agents, and shared skill for auditing
LaTeX citations and classifying assertions.

## Build & test commands

```bash
uv sync --extra dev          # install editable with dev deps
uv run pytest                # run all 121 tests
uv run pytest --tb=short -q  # quick summary
```

## Key files

- `src/citation_audit/core/schema.py` — `AssertionRecord`, `CitationRecord`, `AuditIndex`
- `src/citation_audit/core/index.py` — atomic `index.json` read/write
- `src/citation_audit/core/scaffold.py` — stub artifact folder creation
- `src/citation_audit/core/extractor.py` — `.tex` parser → `list[Sentence]`
- `src/citation_audit/core/classifier.py` — signal-word heuristic classifier
- `src/citation_audit/cli.py` — Click CLI (`citation-audit`)
- `src/citation_audit/mcp_server.py` — FastMCP server (`citation-audit-mcp`)
- `.github/agents/citation-auditor.agent.md` — validates citations, scores support
- `.github/agents/citation-alternatives.agent.md` — finds replacement sources
- `.github/agents/citation-finder.agent.md` — discovers uncited assertions, proposes citations
- `.github/skills/citation-audit-common/SKILL.md` — shared definitions, scoring, artifact schema

## Conventions

- Python ≥ 3.11 with `from __future__ import annotations`
- All functions fully type-annotated
- No HTTP calls inside this package
- Assertion IDs are `"a-" + sha256(f"{doc_stem}:{text}")[:8]` — do not change
- `.audit/` lives beside the `.tex` file; `index.json` is written atomically

## Do not

- Add HTTP/network calls to any `core/` module
- Change assertion ID hash scheme
- Break existing CLI surface without updating tests

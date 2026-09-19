# AGENTS.md — citation-audit

## What this repo is

Python CLI, MCP server, VS Code Copilot agents, and shared skill for auditing
LaTeX and Markdown citations and classifying assertions.

## Build & test commands

```bash
uv sync --extra dev          # install editable with dev deps
uv run pytest                # run all 136 tests
uv run pytest --tb=short -q  # quick summary
```

## Key files

- `src/citation_audit/core/schema.py` — `AssertionRecord`, `CitationRecord`, `AuditIndex`
- `src/citation_audit/core/index.py` — atomic `index.json` read/write
- `src/citation_audit/core/scaffold.py` — stub artifact folder creation
- `src/citation_audit/core/extractor.py` — `.tex`/`.md` parser → `list[Sentence]`
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
- `.audit/` lives beside the source document; `index.json` is written atomically

## Do not

- Add HTTP/network calls to any `core/` module
- Change assertion ID hash scheme
- Break existing CLI surface without updating tests

# BEGIN managed-by-agent-config
## MANDATORY: Read project instructions first

At the start of every task, read `.github/copilot-instructions.md` in full.

## Answer Self-Test (MANDATORY — run before sending every response)

1. If the reader sees only my first sentence, do they do the right next thing?
2. Which claims did I verify, which did I infer, which did I assume — and can the reader tell the difference?
3. What single claim, if wrong, sinks this answer — and did I re-derive it, or just recognize it?
4. What did I do because the words said so that the person wouldn't actually want?
5. If this is wrong, do they find out from me, now — or from the failure, later?

If any answer is uncomfortable, the response isn't ready.
Full rationale and procedures: `~/src/agent-config/docs/OPERATING_MANUAL.md`

## Available Skills

User-level shared skills live in `~/src/agent-config/.github/skills/`.
Examples include review workflows such as `duckflow` and Codex bridge skills such as `flush-codex`.

To read a skill: `read_file` on `SKILL.md` inside the relevant directory.

## Available Slash Command Prompts

Prompt files live in `~/src/agent-config/prompts/`.
Examples include workflow prompts such as `/duckflow` and `/flush`.
When the user invokes a slash command, read the corresponding `.prompt.md` file.

## MCP Tools available in Cline

- Prefer the 'oboe-mcp' MCP tools for OBO session state.
- Do not edit .github/oboe_sessions/*.json directly or use 'obo_helper.py' when 'oboe-mcp' can perform the operation. Fall back to 'oboe-cli' when the MCP server is unavailable.
- **oboe-mcp**: `oboe_list_sessions`, `oboe_create`, `oboe_session_status`, `oboe_next`, `oboe_list_items`, `oboe_get_item`, `oboe_mark_blocked`, `oboe_mark_complete`, `oboe_mark_in_progress`, `oboe_mark_skip`, `oboe_set_approval`, `oboe_complete_session`, `oboe_create_child_session`, `oboe_complete_child_session`, `oboe_merge_items`, `oboe_update_field`
- **oboe-cli fallback** (when MCP unavailable): all session-scoped commands take `--session SESSION [--base-dir DIR]`
  - sessions/status/next/complete-session/list/show/in-progress/block/complete/skip/approve/update/merge/create-child/complete-child
  - `create` and `merge` require `--input-file items.json` (items as a JSON array)
  - Example: `oboe-cli --base-dir . --session SESSION.json complete ITEM_ID "resolution text"`
- **markitdown**: Convert documents/URLs to Markdown for reading.
# END managed-by-agent-config

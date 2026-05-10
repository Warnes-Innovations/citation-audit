# CLAUDE.md — citation-audit

## What this repo is

Python CLI, MCP server, VS Code Copilot agents, and shared skill for auditing
LaTeX citations and classifying assertions by type (asserted-fact,
original-synthesis, derived-conclusion, own-contribution, definition,
established-convention, narrative, unknown).

Agent definitions: `.github/agents/citation-{auditor,alternatives,finder}.agent.md`  
Shared skill: `.github/skills/citation-audit-common/SKILL.md`

## Build & test

```bash
uv sync --extra dev    # install editable + dev deps
uv run pytest          # run all tests
```

## Important invariants

1. **Assertion IDs** are stable hashes: `"a-" + sha256(f"{doc_stem}:{text}")[:8]`
   Do not change this scheme — existing audit artifacts depend on it.

2. **Atomic writes**: `core/index.py:save()` uses `tempfile + os.replace`.
   Always use `save()` — never write `index.json` directly.

3. **No HTTP**: This package has no network calls. Agents make HTTP requests;
   this package only manages local artifact files and classification logic.

4. **`.audit/` layout**:
   ```
   <doc_parent>/.audit/<doc_stem>/<bibtex_label>/publication.md
   <doc_parent>/.audit/<doc_stem>/<bibtex_label>/citation_<label>.md
   <doc_parent>/.audit/<doc_stem>/<bibtex_label>/summary.md
   <doc_parent>/.audit/<doc_stem>/assertions/<id>/assertion.md
   <doc_parent>/.audit/<doc_stem>/index.json
   ```

## Installation

`install.sh` installs the editable package and links the shared skill:

```bash
./install.sh           # sync deps, link ~/.codex/skills/ and ~/.copilot/skills/
./install.sh --no-test # skip test run
./install.sh --tool    # also install as a global uv tool
```

Running `~/src/vscode-config/setup.sh` has the same effect for the skill links.

## Slash commands

Prompt files from vscode-config are linked into `.claude/commands/` by `setup.sh`.

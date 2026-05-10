# citation-audit

CLI, MCP server, coding agents, and shared skill for auditing citations in LaTeX documents.

Extracts and classifies every sentence by assertion type, manages `.audit/` artifact
folders per citation, and maintains an `index.json` audit record. Ships the
`citation-auditor`, `citation-finder`, and `citation-alternatives` agents and the
`citation-audit-common` skill that they share.

## Agents

| Agent | Description |
|---|---|
| `citation-auditor` | Validates citations against authoritative databases, scores support, maintains `.audit/` artifacts |
| `citation-alternatives` | Finds replacement sources for unsupportive or unavailable citations |
| `citation-finder` | Identifies uncited factual assertions, searches Crossref/PubMed, presents candidates via `/obo` |

Agent definitions live in `.github/agents/`. VS Code Copilot discovers them automatically
when this repo is open as a workspace folder. They share the `citation-audit-common` skill
at `.github/skills/citation-audit-common/SKILL.md`.

## Tools

### CLI (`citation-audit`)

| Command | Description |
|---|---|
| `extract DOC` | Parse `.tex`, classify every sentence, output JSON |
| `scaffold DOC LABEL` | Create `.audit/<doc>/<label>/` stub files |
| `scaffold-assertion DOC ID --text TEXT` | Create `.audit/<doc>/assertions/<id>/` stub |
| `update-citation DOC LABEL [options]` | Patch citation record in `index.json` |
| `tag-assertion DOC ID --type TYPE` | Record or update assertion_type in `index.json` |
| `list DOC` | Show all citations and assertions from `index.json` |
| `report DOC` | Print audit summary (markdown or JSON) |

### MCP Server (`citation-audit-mcp`)

| Tool | Description |
|---|---|
| `extract_assertions` | Parse `.tex` and classify sentences |
| `get_audit_status` | Return full `index.json` for a document |
| `scaffold_citation` | Create citation stub artifacts |
| `scaffold_assertion_artifact` | Create uncited assertion stub |
| `update_citation_record` | Insert or patch citation record |
| `tag_assertion` | Record or update assertion classification |
| `list_assertions` | Return assertion records with optional filters |
| `compute_assertion_id` | Return stable hash-based ID for a sentence |

## Install

### As a `uvx` tool (recommended)

```bash
uvx --from git+https://github.com/Warnes-Innovations/citation-audit.git citation-audit --help
```

### MCP server config (VS Code / Claude / Cline)

```json
"citation-audit": {
    "type": "stdio",
    "command": "uvx",
    "args": [
        "--from",
        "git+https://github.com/Warnes-Innovations/citation-audit.git",
        "citation-audit-mcp"
    ]
}
```

### Local development

```bash
cd ~/src/citation-audit
./install.sh          # creates .venv, installs editable + dev deps, links skill
uv run pytest         # run all tests
```

`install.sh` also links `.github/skills/citation-audit-common/` into
`~/.codex/skills/` and `~/.copilot/skills/`. Running
`~/src/vscode-config/setup.sh` achieves the same effect.

## Assertion Type Vocabulary

| Type | Description |
|---|---|
| `asserted-fact` | External claim that needs a citation |
| `original-synthesis` | Author's own reasoning / analytical contribution |
| `derived-conclusion` | Conclusion drawn from results in this document |
| `own-contribution` | Description of the paper's own method / model |
| `definition` | Formal definition, variable introduction, notation |
| `established-convention` | Universally accepted textbook principle |
| `narrative` | Transitional, motivational, or rhetorical framing |
| `unknown` | Not yet classified |

## License

MIT

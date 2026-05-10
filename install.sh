#!/usr/bin/env bash
# install.sh — Set up citation-audit for local development
#
# Usage:
#   ./install.sh              # install editable + dev deps, run tests
#   ./install.sh --no-test    # skip test run
#   ./install.sh --tool       # also install as a global uv tool
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_TESTS=true
INSTALL_TOOL=false

for arg in "$@"; do
    case "$arg" in
        --no-test)   RUN_TESTS=false ;;
        --tool)      INSTALL_TOOL=true ;;
        -h|--help)
            echo "Usage: $0 [--no-test] [--tool]"
            echo "  --no-test   Skip running the test suite"
            echo "  --tool      Also install citation-audit as a global uv tool"
            exit 0
            ;;
    esac
done

echo "==> citation-audit install"
echo "    Source: $SCRIPT_DIR"
echo ""

# ------------------------------------------------------------------
# 1. Install editable package + dev dependencies
# ------------------------------------------------------------------
echo "--> uv sync --extra dev"
cd "$SCRIPT_DIR"
uv sync --extra dev
echo ""

# ------------------------------------------------------------------
# 2. Optionally run the test suite
# ------------------------------------------------------------------
if $RUN_TESTS; then
    echo "--> uv run pytest"
    uv run pytest
    echo ""
fi

# ------------------------------------------------------------------
# 3. Optionally install as a global uv tool
#    (makes 'citation-audit' and 'citation-audit-mcp' available globally)
# ------------------------------------------------------------------
if $INSTALL_TOOL; then
    echo "--> uv tool install --editable ."
    uv tool install --editable .
    echo ""
fi

# ------------------------------------------------------------------
# 4. Link skill into canonical Codex skills directory (~/.codex/skills/)
#    VS Code Copilot discovers agents automatically from .github/agents/
#    in any open workspace folder — no extra linking needed for agents.
# ------------------------------------------------------------------
SKILL_SRC="$SCRIPT_DIR/.github/skills/citation-audit-common"

CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
echo "--> Linking citation-audit-common skill into $CODEX_HOME/skills/"
mkdir -p "$CODEX_HOME/skills"
ln -sfn "$SKILL_SRC" "$CODEX_HOME/skills/citation-audit-common"
echo "    Linked $CODEX_HOME/skills/citation-audit-common → $SKILL_SRC"
echo ""

# ------------------------------------------------------------------
# 5. Link skill into canonical Copilot skills directory (~/.copilot/skills/)
# ------------------------------------------------------------------
COPILOT_HOME="${COPILOT_HOME:-$HOME/.copilot}"
echo "--> Linking citation-audit-common skill into $COPILOT_HOME/skills/"
mkdir -p "$COPILOT_HOME/skills"
ln -sfn "$SKILL_SRC" "$COPILOT_HOME/skills/citation-audit-common"
echo "    Linked $COPILOT_HOME/skills/citation-audit-common → $SKILL_SRC"
echo ""

# ------------------------------------------------------------------
# 6. Remind user about MCP config
# ------------------------------------------------------------------
echo "==> Done."
echo ""
echo "MCP server config for VS Code / Claude / Cline:"
echo ""
echo '    "citation-audit": {'
echo '        "type": "stdio",'
echo '        "command": "uvx",'
echo '        "args": ['
echo '            "--from",'
echo '            "git+https://github.com/Warnes-Innovations/citation-audit.git",'
echo '            "citation-audit-mcp"'
echo '        ]'
echo '    }'
echo ""
echo "For local development, use the local path instead:"
echo ""
echo "    \"--from\", \"$SCRIPT_DIR\","

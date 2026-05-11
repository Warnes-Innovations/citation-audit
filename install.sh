#!/usr/bin/env bash
# install.sh — Set up citation-audit
#
# Usage:
#   ./install.sh              # install editable + dev deps, run tests, link skills;
#                             #   if MCP was on dev, prompts to switch to published
#   ./install.sh --no-test    # skip test run
#   ./install.sh --tool       # also install as a global uv tool
#   ./install.sh --dev        # local-dev mode (no prompt):
#                             #   • install as editable uv tool (CLI on PATH)
#                             #   • patch user-level mcp.json to use local repo
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_TESTS=true
INSTALL_TOOL=false
SETUP_DEV=false
SWITCH_TO_PUBLISHED=false

VSCODE_USER_MCP="$HOME/Library/Application Support/Code/User/mcp.json"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-test)   RUN_TESTS=false ;;
        --tool)      INSTALL_TOOL=true ;;
        --dev)       SETUP_DEV=true ;;
        --from)
            # Legacy alias: ./install.sh --from <path>  →  treated as --dev
            SETUP_DEV=true
            shift  # consume the (ignored) path argument
            ;;
        -h|--help)
            echo "Usage: $0 [--no-test] [--tool] [--dev]"
            echo "  --no-test   Skip running the test suite"
            echo "  --tool      Also install citation-audit as a global uv tool"
            echo "  --dev       Install as editable uv tool and patch user mcp.json"
            echo "              to use this local repo instead of the git URL"
            echo "              (if MCP is on dev and --dev is omitted, prompts to revert)"
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 1
            ;;
    esac
    shift
done

# ------------------------------------------------------------------
# If MCP is currently on dev and no flag was given, confirm revert
# ------------------------------------------------------------------
if ! $SETUP_DEV; then
    CURRENT_MODE="$(python3 - "$VSCODE_USER_MCP" <<'PYEOF'
import json, os, sys
path = os.path.realpath(sys.argv[1]) if os.path.exists(sys.argv[1]) else ""
if not path:
    print("unknown")
    sys.exit(0)
try:
    cfg = json.load(open(path))
    entry = cfg.get("servers", {}).get("citation-audit", {})
    print("dev" if entry.get("command") == "uv" else "published")
except Exception:
    print("unknown")
PYEOF
    )"

    if [[ "$CURRENT_MODE" == "dev" ]]; then
        echo "MCP is currently configured for local dev."
        read -r -p "Switch to published (uvx from GitHub)? [y/N]: " MCP_CHOICE
        case "$(echo "$MCP_CHOICE" | tr '[:upper:]' '[:lower:]')" in
            y|yes)  SWITCH_TO_PUBLISHED=true ;;
            *)      ;;
        esac
    fi
fi

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
# 3. Global uv tool install (also implied by --dev)
# ------------------------------------------------------------------
if $INSTALL_TOOL || $SETUP_DEV; then
    echo "--> uv tool install --editable ."
    uv tool install --editable .
    echo "    citation-audit and citation-audit-mcp are now on PATH"
    echo ""
fi

# ------------------------------------------------------------------
# 4. Patch the user-level mcp.json
#
#    VS Code's user mcp.json may be a symlink; resolve to the real file
#    before editing so we don't replace a symlink with a plain file.
# ------------------------------------------------------------------

_patch_mcp() {
    local mode="$1"   # "dev" or "restore"
    local mcp_real
    mcp_real="$(python3 -c "import os,sys; p=sys.argv[1]; print(os.path.realpath(p))" "$VSCODE_USER_MCP" 2>/dev/null || echo "")"

    if [[ -z "$mcp_real" || ! -f "$mcp_real" ]]; then
        echo "    warning: could not locate user mcp.json — skipping MCP patch" >&2
        return
    fi

    echo "--> Patching $mcp_real (mode: $mode)"

    python3 - "$mcp_real" "$mode" "$SCRIPT_DIR" <<'PYEOF'
import json, sys, os, tempfile

path, mode, script_dir = sys.argv[1], sys.argv[2], sys.argv[3]

with open(path) as f:
    cfg = json.load(f)

servers = cfg.setdefault("servers", {})

if mode == "dev":
    servers["citation-audit"] = {
        "type":    "stdio",
        "command": "uv",
        "args":    ["run", "--directory", script_dir, "citation-audit-mcp"],
    }
    print(f"    citation-audit MCP → uv run --directory {script_dir} citation-audit-mcp")
else:  # restore
    servers["citation-audit"] = {
        "type":    "stdio",
        "command": "uvx",
        "args":    [
            "--from",
            "git+https://github.com/Warnes-Innovations/citation-audit.git",
            "citation-audit-mcp",
        ],
    }
    print("    citation-audit MCP → uvx --from git+https://github.com/Warnes-Innovations/citation-audit.git")

data = json.dumps(cfg, indent="\t") + "\n"
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".mcp-", suffix=".json")
try:
    os.write(fd, data.encode())
    os.close(fd)
    os.replace(tmp, path)
except Exception:
    try: os.close(fd)
    except OSError: pass
    try: os.unlink(tmp)
    except OSError: pass
    raise
PYEOF
    echo ""
}

if $SETUP_DEV; then
    _patch_mcp "dev"
fi

if $SWITCH_TO_PUBLISHED; then
    _patch_mcp "restore"
fi

# ------------------------------------------------------------------
# 5. Link skill into Codex skills directory (~/.codex/skills/)
# ------------------------------------------------------------------
SKILL_SRC="$SCRIPT_DIR/.github/skills/citation-audit-common"

CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
echo "--> Linking citation-audit-common skill into $CODEX_HOME/skills/"
mkdir -p "$CODEX_HOME/skills"
ln -sfn "$SKILL_SRC" "$CODEX_HOME/skills/citation-audit-common"
echo "    Linked $CODEX_HOME/skills/citation-audit-common → $SKILL_SRC"
echo ""

# ------------------------------------------------------------------
# 6. Link skill into Copilot skills directory (~/.copilot/skills/)
# ------------------------------------------------------------------
COPILOT_HOME="${COPILOT_HOME:-$HOME/.copilot}"
echo "--> Linking citation-audit-common skill into $COPILOT_HOME/skills/"
mkdir -p "$COPILOT_HOME/skills"
ln -sfn "$SKILL_SRC" "$COPILOT_HOME/skills/citation-audit-common"
echo "    Linked $COPILOT_HOME/skills/citation-audit-common → $SKILL_SRC"
echo ""

# ------------------------------------------------------------------
# 7. Symlink agent files into vscode-config agents directory
# ------------------------------------------------------------------
VSCODE_CONFIG="${VSCODE_CONFIG:-$HOME/src/vscode-config}"
AGENTS_SRC="$SCRIPT_DIR/.github/agents"
AGENTS_DST="$VSCODE_CONFIG/agents"

if [[ -d "$VSCODE_CONFIG" ]]; then
    echo "--> Symlinking agent files into $AGENTS_DST/"
    mkdir -p "$AGENTS_DST"
    for agent_file in "$AGENTS_SRC"/*.agent.md; do
        base="$(basename "$agent_file")"
        ln -sfn "$agent_file" "$AGENTS_DST/$base"
        echo "    Linked $AGENTS_DST/$base → $agent_file"
    done
    echo ""
else
    echo "    note: $VSCODE_CONFIG not found — skipping agent symlinks" >&2
    echo "    Set VSCODE_CONFIG=/path/to/vscode-config to enable." >&2
    echo ""
fi

# ------------------------------------------------------------------
# 8. Done
# ------------------------------------------------------------------
echo "==> Done."

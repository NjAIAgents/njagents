#!/usr/bin/env bash
# package-plugin.sh
# Packages a Claude plugin directory into a ready-to-upload ZIP.
# Usage: ./package-plugin.sh <Category/plugin-name>
#   e.g. ./package-plugin.sh operations/bug-triage-agent

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $# -ge 1 ]]; then
  PLUGIN_PATH="$1"
else
  echo ""
  read -rp "Plugin path (e.g. operations/bug-triage-agent): " PLUGIN_PATH
fi

PLUGIN_PATH="${PLUGIN_PATH%/}"
PLUGIN_DIR="$SCRIPT_DIR/$PLUGIN_PATH"
PLUGIN_NAME="$(basename "$PLUGIN_PATH")"

if [[ ! -d "$PLUGIN_DIR" ]]; then
  echo "ERROR: Directory not found: $PLUGIN_DIR"
  exit 1
fi

if [[ ! -f "$PLUGIN_DIR/.claude-plugin/plugin.json" ]]; then
  echo "ERROR: No .claude-plugin/plugin.json in $PLUGIN_DIR"
  exit 1
fi

# Repository-wide pre-flight. The constitution is only worth something if
# something checks it.
if [[ -f "$SCRIPT_DIR/scripts/check_constitution.py" ]]; then
  echo "Checking constitution..."
  python3 "$SCRIPT_DIR/scripts/check_constitution.py" || {
    echo ""
    echo "ERROR: constitution violation. Fix it, or add a reasoned entry to"
    echo "       .constitution-allow. See .specify/memory/constitution.md"
    exit 1
  }
fi

# Plugin-specific pre-flight. A plugin that ships a validator must pass it
# before it can be packaged.
if [[ -f "$PLUGIN_DIR/scripts/validate_config.py" ]]; then
  echo "Running plugin validator..."
  ( cd "$PLUGIN_DIR" && python3 scripts/validate_config.py --all ) || {
    echo ""
    echo "ERROR: validator failed. Fix the reported issues before packaging."
    exit 1
  }
fi

STAGING_DIR="$(mktemp -d)"
STAGING_PLUGIN="$STAGING_DIR/$PLUGIN_NAME"

echo "Staging plugin..."
cp -R "$PLUGIN_DIR" "$STAGING_PLUGIN"

# Spec Kit and agent state live at the repo root, never inside a plugin. Strip
# them defensively in case someone initialises them inside a plugin directory:
# shipping them would put spec-kit skills inside an installed plugin.
rm -rf "$STAGING_PLUGIN/.specify" "$STAGING_PLUGIN/.claude" "$STAGING_PLUGIN/.git"

# Runtime output is not distributable.
find "$STAGING_PLUGIN" -name "*.jsonl" -delete

# Filled-in local team configs may carry site hosts and instance ids.
if [[ -d "$STAGING_PLUGIN/teams" ]]; then
  find "$STAGING_PLUGIN/teams" -name "local-*.json" -delete
fi

# OS noise and stray archives
find "$STAGING_PLUGIN" -name ".DS_Store" -delete
find "$STAGING_PLUGIN" -name "Thumbs.db" -delete
find "$STAGING_PLUGIN" -name "*.zip" -delete

OUTPUT_ZIP="$SCRIPT_DIR/${PLUGIN_NAME}.zip"
rm -f "$OUTPUT_ZIP"
(cd "$STAGING_DIR" && zip -r "$OUTPUT_ZIP" "$PLUGIN_NAME" --quiet)
rm -rf "$STAGING_DIR"

echo ""
echo "Done. Plugin packaged at:"
echo "  $OUTPUT_ZIP"
echo ""
echo "Upload via Claude Cowork > Customize > Browse plugins > Upload custom plugin."

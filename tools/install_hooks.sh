#!/usr/bin/env bash
# install_hooks.sh — Install Cornerstone git hooks into .git/hooks/
#
# Run once after cloning or generating the project:
#   bash tools/install_hooks.sh
#
# Hooks installed:
#   pre-commit  — ADR gate: blocks commits that modify library source
#                 code without a new ADR file staged alongside.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"
HOOKS_DIR="$REPO_ROOT/.git/hooks"

if [[ ! -d "$HOOKS_DIR" ]]; then
  echo "[cornerstone:hooks] ERROR: .git/hooks not found. Is this a git repository?" >&2
  exit 1
fi

# ── pre-commit framework ──────────────────────────────────────────────────────
if command -v pre-commit &> /dev/null; then
    pre-commit install || true
    echo "[cornerstone:hooks] Installed pre-commit framework hooks."
fi

# ── commit-msg (ADR gate) ─────────────────────────────────────────────────────
COMMIT_MSG_HOOK="$HOOKS_DIR/commit-msg"

CORNERSTONE_BANNER="# cornerstone:adr-gate"

HOOK_BODY='#!/usr/bin/env bash
# cornerstone:adr-gate — ADR gate commit-msg hook (DO NOT REMOVE THIS LINE)
# Blocks commits that modify guarded library source without a new ADR staged.
# Installed by tools/install_hooks.sh — re-run to update.
set -euo pipefail

COMMIT_MSG_FILE=$1
STAGED=$(git diff --cached --name-only 2>/dev/null || true)
NEW_FILES=$(git diff --cached --name-only --diff-filter=A 2>/dev/null || true)
COMMIT_MSG=""
if [[ -n "${COMMIT_MSG_FILE:-}" ]] && [[ -f "$COMMIT_MSG_FILE" ]]; then
  COMMIT_MSG=$(cat "$COMMIT_MSG_FILE")
fi

cornerstone adr-gate \
  --changed-files "$STAGED" \
  --new-files     "$NEW_FILES" \
  --commit-message "$COMMIT_MSG"'

if [[ -f "$COMMIT_MSG_HOOK" ]]; then
  if grep -q "cornerstone:adr-gate" "$COMMIT_MSG_HOOK" 2>/dev/null; then
    # Already installed by Cornerstone — overwrite safely (update in place)
    echo "$HOOK_BODY" > "$COMMIT_MSG_HOOK"
    chmod +x "$COMMIT_MSG_HOOK"
    echo "[cornerstone:hooks] Updated existing Cornerstone hook: $COMMIT_MSG_HOOK"
  else
    # A non-Cornerstone hook exists — append a call rather than overwriting
    echo "" >> "$COMMIT_MSG_HOOK"
    echo "# --- BEGIN cornerstone:adr-gate (appended by install_hooks.sh) ---" >> "$COMMIT_MSG_HOOK"
    echo 'COMMIT_MSG_FILE=$1' >> "$COMMIT_MSG_HOOK"
    echo 'STAGED=$(git diff --cached --name-only 2>/dev/null || true)' >> "$COMMIT_MSG_HOOK"
    echo 'NEW_FILES=$(git diff --cached --name-only --diff-filter=A 2>/dev/null || true)' >> "$COMMIT_MSG_HOOK"
    echo 'COMMIT_MSG=""' >> "$COMMIT_MSG_HOOK"
    echo 'if [[ -n "${COMMIT_MSG_FILE:-}" ]] && [[ -f "$COMMIT_MSG_FILE" ]]; then COMMIT_MSG=$(cat "$COMMIT_MSG_FILE"); fi' >> "$COMMIT_MSG_HOOK"
    echo 'cornerstone adr-gate --changed-files "$STAGED" --new-files "$NEW_FILES" --commit-message "$COMMIT_MSG"' >> "$COMMIT_MSG_HOOK"
    echo "# --- END cornerstone:adr-gate ---" >> "$COMMIT_MSG_HOOK"
    echo "[cornerstone:hooks] Appended ADR gate to existing hook: $COMMIT_MSG_HOOK"
    echo "[cornerstone:hooks] WARNING: existing hook was preserved — verify merged behavior."
  fi
else
  echo "$HOOK_BODY" > "$COMMIT_MSG_HOOK"
  chmod +x "$COMMIT_MSG_HOOK"
  echo "[cornerstone:hooks] Installed: $COMMIT_MSG_HOOK"
fi

echo "[cornerstone:hooks] ADR gate will run on every commit."

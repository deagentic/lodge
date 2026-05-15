#!/usr/bin/env bash
# sync_agents.sh — Cornerstone skill & tool sync
#
# Pulls the latest skills and tools from deagentic/cornerstone into this
# project's .agents/skills/ directory.
#
# Runs automatically at session start via the UserPromptSubmit hook in
# .claude/settings.json. Throttled to once per 24 hours via a timestamp
# file at .agents/.last_sync.
#
# Requirements:
#   - gh CLI installed and authenticated (gh auth login)
#
# To force a sync regardless of the timestamp:
#   bash tools/sync_agents.sh --force

set -euo pipefail

SKILLS_DIR="$(cd "$(dirname "$0")/.." && pwd)/.agents/skills"
LAST_SYNC_FILE="$(cd "$(dirname "$0")/.." && pwd)/.agents/.last_sync"
TEMPLATE_REPO="deagentic/cornerstone"  # source of truth for shared skills/tools
PROJECT_SLUG="lodge"
FORCE=false

# Parse flags
for arg in "$@"; do
  [[ "$arg" == "--force" ]] && FORCE=true
done

# --- Throttle check (skip if < 24h since last sync) ---
if [[ "$FORCE" == false && -f "$LAST_SYNC_FILE" ]]; then
  last_sync=$(cat "$LAST_SYNC_FILE")
  now=$(date +%s)
  age=$(( now - last_sync ))
  if (( age < 86400 )); then
    exit 0  # silent skip — synced recently
  fi
fi

# --- Prerequisite: gh CLI authenticated ---
if ! command -v gh &>/dev/null; then
  echo "[cornerstone:sync] WARNING: gh CLI not found. Skipping sync." >&2
  exit 0
fi

if ! gh auth status &>/dev/null; then
  echo "[cornerstone:sync] WARNING: Not authenticated with gh. Run: gh auth login" >&2
  exit 0
fi

# --- Sync ---
echo "[cornerstone:sync] Syncing skills and tools from $TEMPLATE_REPO..." >&2

TMPDIR_SYNC=$(mktemp -d)
trap 'rm -rf "$TMPDIR_SYNC"' EXIT

# Clone only the relevant directories (sparse checkout for speed)
cd "$TMPDIR_SYNC"
gh repo clone "$TEMPLATE_REPO" repo -- --depth=1 --quiet 2>/dev/null

if [[ ! -d "$TMPDIR_SYNC/repo/$PROJECT_SLUG/.agents/skills" ]]; then
  echo "[cornerstone:sync] WARNING: Could not locate skills in template repo. Skipping." >&2
  exit 0
fi

# --- Snapshot current skill versions BEFORE overwriting (requires bash 4+) ---
declare -A _pre_versions
if [[ "${BASH_VERSINFO[0]}" -ge 4 ]]; then
  while IFS= read -r -d '' skill_file; do
    rel="${skill_file#"$SKILLS_DIR/"}"
    ver=$(awk '/^---$/{f++} f==1 && /^version:/{gsub(/[" ]/, "", $2); print $2; exit}' "$skill_file" 2>/dev/null || true)
    _pre_versions["$rel"]="${ver:-}"
  done < <(find "$SKILLS_DIR" -name "SKILL.md" -print0 2>/dev/null)
else
  echo "[cornerstone:sync] WARNING: bash 4+ required for skill version tracking. Skipping version diff." >&2
fi

# Rsync skills — preserve local-only files, overwrite shared ones
rsync -a --delete \
  "$TMPDIR_SYNC/repo/$PROJECT_SLUG/.agents/skills/" \
  "$SKILLS_DIR/" \
  --exclude=".last_sync" \
  2>/dev/null

# --- Compare versions AFTER rsync and warn on changes ---
if [[ "${BASH_VERSINFO[0]}" -ge 4 ]]; then
  while IFS= read -r -d '' skill_file; do
    rel="${skill_file#"$SKILLS_DIR/"}"
    new_ver=$(awk '/^---$/{f++} f==1 && /^version:/{gsub(/[" ]/, "", $2); print $2; exit}' "$skill_file" 2>/dev/null || true)
    old_ver="${_pre_versions[$rel]:-}"
    if [[ -n "$old_ver" && -n "$new_ver" && "$old_ver" != "$new_ver" ]]; then
      echo "[cornerstone:sync] SKILL UPDATED: ${rel%/SKILL.md}  ${old_ver} → ${new_ver}" >&2
      echo "[cornerstone:sync]   Review the changelog and check for new tool dependencies." >&2
    elif [[ -z "$old_ver" && -n "$new_ver" ]]; then
      echo "[cornerstone:sync] SKILL ADDED: ${rel%/SKILL.md}  (version ${new_ver})" >&2
    fi
  done < <(find "$SKILLS_DIR" -name "SKILL.md" -print0 2>/dev/null)
fi

# Write timestamp
date +%s > "$LAST_SYNC_FILE"

echo "[cornerstone:sync] Skills synced successfully." >&2

#!/usr/bin/env bash
# Sync agent skills from the canonical Agents repo into this project's .claude/skills/.
# The Agents repo is the source of truth — never edit the synced files here; improve them
# upstream and re-run this script. Commit the synced result so sandboxed environments
# (e.g. Claude Code on the web) have the skills without network access.
set -euo pipefail

REPO="${AGENTS_REPO:-https://github.com/Joost-Maker/Agents.git}"
REF="${AGENTS_REF:-main}"
DEST=".claude/skills"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

git clone --quiet --depth 1 --branch "$REF" "$REPO" "$tmp"
commit="$(git -C "$tmp" rev-parse --short HEAD)"

rm -rf "$DEST"
mkdir -p "$DEST"
cp -R "$tmp/skills/." "$DEST/"
printf 'synced from %s@%s on %s\nDO NOT EDIT — improve upstream and re-sync.\n' \
  "$REPO" "$commit" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$DEST/.synced"

echo "Skills synced from $REPO@$commit into $DEST — review 'git diff' and commit."

#!/usr/bin/env bash
#
# Install the task-observer skill for Claude Code on this machine.
#
# Claude Code reads skills from two places:
#   ~/.claude/skills/<name>/          personal — every project you open
#   <repo>/.claude/skills/<name>/     project  — only that repo
#
# This installs the personal copy, so task-observer is active in Claude Code
# everywhere. The project copy in this repo is already committed and needs
# nothing.
#
# Claude desktop chat and Cowork do NOT read these folders — they use skills
# uploaded to your Claude account. See dist/README.md for that step.
#
# Usage:
#   ./scripts/install-task-observer.sh            install / update
#   ./scripts/install-task-observer.sh --check    show what is installed
#
# Skill by Eoghan Henn / rebelytics.com, CC BY 4.0.
# https://github.com/rebelytics/one-skill-to-rule-them-all

set -euo pipefail

UPSTREAM="https://github.com/rebelytics/one-skill-to-rule-them-all"
DEST="${HOME}/.claude/skills/task-observer"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${REPO_ROOT}/.claude/skills/task-observer"

if [ "${1:-}" = "--check" ]; then
  if [ -f "${DEST}/SKILL.md" ]; then
    echo "installed: ${DEST}"
    find "${DEST}" -type f | sort | sed 's/^/  /'
  else
    echo "not installed: ${DEST}"
  fi
  exit 0
fi

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  sed -n '3,21p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit 0
fi

CLEANUP=""
trap '[ -n "${CLEANUP}" ] && rm -rf "${CLEANUP}"' EXIT

# Prefer the copy committed in this repo; fall back to a fresh upstream clone
# so the script also works when run on its own.
if [ ! -f "${SRC}/SKILL.md" ]; then
  echo "No local copy at ${SRC} — cloning upstream..."
  CLEANUP="$(mktemp -d)"
  git clone --depth 1 --quiet "${UPSTREAM}" "${CLEANUP}/upstream"
  SRC="${CLEANUP}/upstream"
fi

if [ ! -f "${SRC}/references/environments.md" ]; then
  echo "error: ${SRC} is missing references/ — the skill runs degraded without it." >&2
  exit 1
fi

mkdir -p "${DEST}"
rm -rf "${DEST}/references"
cp "${SRC}/SKILL.md" "${DEST}/SKILL.md"
cp -R "${SRC}/references" "${DEST}/references"
[ -f "${SRC}/LICENSE.txt" ] && cp "${SRC}/LICENSE.txt" "${DEST}/LICENSE.txt"

echo "Installed task-observer to ${DEST}"
find "${DEST}" -type f | sort | sed 's/^/  /'
cat <<'EOF'

Next steps:
  1. Restart Claude Code (or start a new session) to pick the skill up.
  2. For desktop chat and Cowork, upload dist/task-observer.zip via
     Claude -> Settings -> Capabilities -> Skills. Those surfaces read your
     account's skills, not this machine's folders.
  3. Add the activation block from this repo's CLAUDE.md to any other project
     whose sessions should invoke the observer automatically.
EOF

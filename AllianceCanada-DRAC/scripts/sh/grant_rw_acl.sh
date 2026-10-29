#!/bin/bash
# NOT TESTED !!!! 
# NEW VERSION from claude.ai on 2026-10-29. Much faster. 
# Grant (or revoke) read-write ACL access for ONE user on a project folder.
#
# Usage:
#   bash grant_rw_acl.sh <PI> <folder> <target_user> [jobs]
#   bash grant_rw_acl.sh --revoke <PI> <folder> <target_user> [jobs]
#
# Examples:
#   bash grant_rw_acl.sh elalib sharing antocg
#   bash grant_rw_acl.sh elalib sharing/tree_ssl hugobaud 4
#   bash grant_rw_acl.sh --revoke elalib sharing antocg
#
# Run inside tmux for large trees. Safe to re-run (idempotent).
# jobs = number of top-level subfolders processed in parallel (default 6, keep 4-8).

set -uo pipefail

MODE="grant"
if [ "${1:-}" = "--revoke" ]; then MODE="revoke"; shift; fi

if [ "$#" -lt 3 ] || [ "$#" -gt 4 ]; then
  sed -n '2,13p' "$0"; exit 1
fi

PI="$1"; FOLDER="$2"; TARGET="$3"; JOBS="${4:-6}"
BASE="/project/def-${PI}/${FOLDER}"
LOG="$HOME/acl_${MODE}_${TARGET}_$(date +%Y%m%d_%H%M%S).log"

# --- Sanity checks ---
id "$TARGET" >/dev/null 2>&1 || { echo "Error: user '$TARGET' does not exist."; exit 1; }
[ -d "$BASE" ] || { echo "Error: '$BASE' is not a directory."; exit 1; }
if [ "$MODE" = "grant" ] && ! id -nG "$TARGET" | grep -qw "def-${PI}"; then
  echo "Warning: '$TARGET' is not in group def-${PI}; they may not be able to reach '$BASE'."
fi

# --- ACL spec ---
# X = execute only on directories and already-executable files.
# d: entries are applied to directories only (files are skipped automatically).
if [ "$MODE" = "grant" ]; then
  OPT="-m"; SPEC="u:${TARGET}:rwX,d:u:${TARGET}:rwX,m:rwX,d:m:rwX"
else
  OPT="-x"; SPEC="u:${TARGET},d:u:${TARGET}"
fi

echo "${MODE^}ing read-write access for '${TARGET}' on '${BASE}' (${JOBS} parallel jobs)"
SECONDS=0

# 1. Top folder only (not recursive)
setfacl "$OPT" "$SPEC" "$BASE" 2>>"$LOG"

# 2. Each top-level entry in parallel, one recursive pass each
find "$BASE" -mindepth 1 -maxdepth 1 -print0 | \
  xargs -0 -r -P "$JOBS" -I{} setfacl -R "$OPT" "$SPEC" {} 2>>"$LOG"

# --- Report ---
echo "Finished in $((SECONDS / 60)) min $((SECONDS % 60)) s."
if [ -s "$LOG" ]; then
  echo "$(wc -l < "$LOG") error(s) logged in $LOG"
  echo "(Usually files owned by other users: their owners must run this, or chmod g+w.)"
else
  rm -f "$LOG"
  echo "No errors."
fi

echo "--- Check on top folder ---"
getfacl -p "$BASE" 2>/dev/null | grep -E "${TARGET}|mask" || echo "(no entries for ${TARGET})"

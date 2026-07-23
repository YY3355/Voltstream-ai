#!/bin/bash
# ---------------------------------------------------------------------------
# dart_auto_commit_launcher.sh — the executable inside DartAutoCommit.app.
#
# WHY A .app: macOS TCC blocks a launchd-spawned process from reading ~/Documents
# (git/python against the repo fail "Operation not permitted"). The fix is a targeted
# Full Disk Access grant — but the FDA picker will NOT accept a bare .sh. So this
# script is installed as the executable of a minimal .app bundle:
#   ~/Library/Application Support/VoltStream/DartAutoCommit.app/Contents/MacOS/dart_auto_commit
# A .app selects normally in the FDA picker, and (run directly by launchd, not via
# /bin/bash) macOS attributes the grant to the bundle's identity alone — not all of bash.
#
# It just sources the versioned logic from the repo, keeping a single source of truth
# (scripts/auto_commit.sh, no copy to drift). The source read succeeds because THIS
# process holds Full Disk Access via the .app grant.
#
# Build/refresh the bundle with: scripts/install_dartcommit_app.sh
# ---------------------------------------------------------------------------
source "$HOME/Documents/voltstream-ai/scripts/auto_commit.sh"

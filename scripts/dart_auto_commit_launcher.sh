#!/bin/bash
# ---------------------------------------------------------------------------
# dart_auto_commit_launcher.sh — FDA-granted launcher for the DART auto-commit.
#
# WHY THIS FILE EXISTS: macOS TCC blocks any launchd-spawned process from reading
# ~/Documents (git/python against the repo fail with "Operation not permitted").
# The fix is a targeted Full Disk Access grant. This launcher lives OUTSIDE
# ~/Documents so launchd can exec it, and because the launchd job runs it DIRECTLY
# (ProgramArguments = [this file], not [/bin/bash, this file]) TCC attributes the
# FDA grant to THIS launcher — so only this one file gets disk access, not all of bash.
#
# It just sources the versioned logic from the repo, keeping a single source of
# truth (scripts/auto_commit.sh) with no copy to drift. The source read succeeds
# because THIS process holds Full Disk Access.
#
# INSTALL (canonical copy lives at):
#   ~/Library/Application Support/VoltStream/dart_auto_commit_launcher.sh
# Re-install after editing this file:
#   cp scripts/dart_auto_commit_launcher.sh "$HOME/Library/Application Support/VoltStream/"
#   chmod +x "$HOME/Library/Application Support/VoltStream/dart_auto_commit_launcher.sh"
# Then grant it Full Disk Access: System Settings > Privacy & Security > Full Disk
# Access > + > (Cmd+Shift+G) ~/Library/Application Support/VoltStream/  > select it.
# ---------------------------------------------------------------------------
source "$HOME/Documents/voltstream-ai/scripts/auto_commit.sh"

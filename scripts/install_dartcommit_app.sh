#!/bin/bash
# ---------------------------------------------------------------------------
# install_dartcommit_app.sh — (re)build the DartAutoCommit.app wrapper in ~/Library.
#
# macOS Full Disk Access won't accept a bare .sh, AND a shell-script bundle executable
# is attributed to /bin/bash (so the .app's FDA grant wouldn't apply). So the bundle's
# executable is a COMPILED Mach-O stub (scripts/dartcommit_stub.c) that just runs
# /bin/bash scripts/auto_commit.sh — a real binary gets the bundle's grant, and the
# bash/git/python it spawns inherit it. The bundle is ad-hoc signed so TCC has a code
# identity to bind the grant to.
#
# NOTE: re-signing changes the bundle's cdhash, which INVALIDATES an existing Full Disk
# Access grant. After (re)building you must (re)grant FDA to the .app. Editing only
# scripts/auto_commit.sh needs NO rebuild (the stub runs it live) and keeps the grant.
#
# After running this:
#   1. Grant the .app Full Disk Access (remove any stale entry first, then re-add):
#        System Settings > Privacy & Security > Full Disk Access > + >
#        ~/Library/Application Support/VoltStream/DartAutoCommit.app
#   2. (Re)load the launchd agent:
#        launchctl bootout   gui/$(id -u)/com.voltstream.dartcommit 2>/dev/null
#        launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.voltstream.dartcommit.plist
# ---------------------------------------------------------------------------
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
APP="$HOME/Library/Application Support/VoltStream/DartAutoCommit.app"
MACOS="$APP/Contents/MacOS"

# clean rebuild so no stale files break the signature
rm -rf "$APP"
mkdir -p "$MACOS"
cp "$HERE/DartAutoCommit-Info.plist" "$APP/Contents/Info.plist"

# compile the stub as the bundle executable (must match CFBundleExecutable = dart_auto_commit)
cc -O2 -o "$MACOS/dart_auto_commit" "$HERE/dartcommit_stub.c"

# ad-hoc sign the whole bundle so the FDA grant binds to a code identity
codesign --force --sign - "$APP"
codesign --verify --strict "$APP" && echo "signed + verified: $APP"

file "$MACOS/dart_auto_commit"
echo "built: $APP"
echo "executable: $MACOS/dart_auto_commit"
echo "NEXT: (re)grant Full Disk Access to the .app, then reload the launchd agent."

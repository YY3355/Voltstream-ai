#!/bin/bash
# ---------------------------------------------------------------------------
# install_dartcommit_app.sh — (re)build the DartAutoCommit.app wrapper in ~/Library.
#
# macOS Full Disk Access won't accept a bare .sh, so the DART auto-commit runs as the
# executable of a minimal .app bundle (which the FDA picker accepts). This assembles that
# bundle from the repo sources and ad-hoc signs it so TCC has a stable identity for the grant.
#
# After running this:
#   1. Grant the .app Full Disk Access:
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

mkdir -p "$MACOS"
cp "$HERE/DartAutoCommit-Info.plist" "$APP/Contents/Info.plist"
cp "$HERE/dart_auto_commit_launcher.sh" "$MACOS/dart_auto_commit"
chmod +x "$MACOS/dart_auto_commit"

# Ad-hoc sign so the FDA grant binds to a stable code identity (unsigned still works, but the
# grant can drop if the bundle changes). Non-fatal if codesign is unavailable.
if codesign --force --sign - "$APP" 2>/dev/null; then
  echo "signed (ad-hoc): $APP"
else
  echo "warn: codesign unavailable/failed — app is unsigned (FDA still works)"
fi

echo "built: $APP"
echo "executable: $MACOS/dart_auto_commit"

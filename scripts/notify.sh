#!/bin/bash
# ---------------------------------------------------------------------------
# notify.sh — one-line push notification via ntfy.sh. Best-effort: ALWAYS exits 0 (a
# notification failure must never fail the job that called it).
#
#   Usage: notify.sh <priority> <title> <message>
#     priority: default | high   (failures use high)
#
#   NTFY_TOPIC unset/empty -> silent no-op (nothing sent).   [the default until Mike sets a topic]
#   DRY_RUN=1              -> print what WOULD be sent, send nothing (tests always use this).
#   else                  -> POST to https://ntfy.sh/$NTFY_TOPIC
# ---------------------------------------------------------------------------
PRIORITY="${1:-default}"
TITLE="${2:-VoltStream}"
MESSAGE="${3:-}"

if [ "${DRY_RUN:-}" = "1" ]; then
  printf '[notify DRY_RUN] topic=%s priority=%s title=%q message=%q\n' \
    "${NTFY_TOPIC:-<unset>}" "$PRIORITY" "$TITLE" "$MESSAGE"
  exit 0
fi

[ -z "${NTFY_TOPIC:-}" ] && exit 0   # silent no-op until a topic is configured

/usr/bin/curl -s --max-time 10 \
  -H "Title: $TITLE" \
  -H "Priority: $PRIORITY" \
  -d "$MESSAGE" \
  "https://ntfy.sh/${NTFY_TOPIC}" >/dev/null 2>&1
exit 0

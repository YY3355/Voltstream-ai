#!/bin/bash
# ---------------------------------------------------------------------------
# joblog.sh — shared helper for the DART daily-rhythm jobs (commit / settle / watchdog).
# Source it. It provides emit_job_row + json_escape and nothing else (no side effects).
#
# Every job appends ONE line to journal/jobs.jsonl (append-only, gitignored):
#   {job, asof_date, started, ended, status, error, commit_sha}
# started/ended are local ISO-8601 WITH numeric offset (e.g. 2026-07-25T16:00:00-0400) — one field
# that encodes BOTH local wall-time AND UTC (via the offset), per the "UTC + local" logging rule.
# ---------------------------------------------------------------------------

# minimal JSON string escaping (backslash, double-quote, and whitespace control chars)
json_escape() {
  local s=${1//\\/\\\\}
  s=${s//\"/\\\"}
  s=${s//$'\n'/ }
  s=${s//$'\r'/ }
  s=${s//$'\t'/ }
  printf '%s' "$s"
}

# emit_job_row <jobs_log> <job> <asof_date> <started> <status> <error> <commit_sha>
emit_job_row() {
  local log="$1" job="$2" asof="$3" started="$4" status="$5" error="$6" sha="$7"
  local ended; ended="$(date +%FT%T%z)"
  printf '{"job":"%s","asof_date":"%s","started":"%s","ended":"%s","status":"%s","error":"%s","commit_sha":"%s"}\n' \
    "$job" "$asof" "$started" "$ended" "$status" "$(json_escape "$error")" "$sha" >> "$log"
}

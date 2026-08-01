"""
digest.py  —  the evening daily digest: top energy headlines + forecast-capture health, as one
templated push (ntfy). Read-only + TEMPLATED — NO LLM in the compose path (constraint 3). An
optional labeled LLM tag/summary may ride ALONGSIDE each headline (news_store.enrich), never
replacing it; the digest always carries the source + link.

Capture health is read from the SAME sources the rhythm already writes:
  * journal/jobs.jsonl  — the latest `capture` job row (status + when)
  * the forecast manifest — docs captured "today" (UTC) + any unknown-vintage today (a red flag:
    unknown vintage = a parse gap = degraded training data, surfaced loudly)

Used by auto_digest.sh (JOB=digest, ~17:30 ET). Pure Python, no network here (the news poll happens
in the shell leg before this runs); import-safe for a unit/DRY_RUN test.
"""
import glob
import json
import os
from datetime import datetime, timezone

import news_store


def _capture_health(jobs_path, manifest_conn, today_utc):
    """(status_line, unknown_today) from jobs.jsonl (latest capture row) + the manifest."""
    last = None
    if os.path.exists(jobs_path):
        for line in open(jobs_path):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("job") == "capture":
                last = r
    captured_today = unknown_today = 0
    if manifest_conn is not None:
        captured_today = manifest_conn.execute(
            "SELECT COUNT(*) FROM captures WHERE captured_at_utc LIKE ?", (today_utc + "%",)).fetchone()[0]
        unknown_today = manifest_conn.execute(
            "SELECT COUNT(*) FROM captures WHERE captured_at_utc LIKE ? AND vintage_status='unknown'",
            (today_utc + "%",)).fetchone()[0]
    if last is None:
        status = "capture: no run recorded yet"
    else:
        status = f"capture: {last.get('status')} ({last.get('asof_date')})"
    status += f" | {captured_today} docs today"
    if unknown_today:
        status += f" | (!) {unknown_today} UNKNOWN-vintage"       # loud: a parse gap = bad training data
    return status, unknown_today


def compose_digest(news_n=5, manifest_conn=None, jobs_path=None):
    """Build the digest as {title, body, unknown_today}. Templated headlines (source + age + link
    kept adjacent) + one capture-health line. No LLM, no network."""
    jobs_path = jobs_path or os.path.join(os.environ.get("JOURNAL_DIR", "journal"), "jobs.jsonl")
    now = datetime.now(timezone.utc)
    today_utc = now.strftime("%Y-%m-%d")
    items = news_store.recent(news_n, conn=None)
    lines = []
    for it in items:
        pub = it.get("published_utc")
        age = ""
        if pub:
            try:
                hrs = (now - datetime.fromisoformat(pub)).total_seconds() / 3600
                age = f"{int(hrs)}h ago" if hrs < 48 else f"{int(hrs / 24)}d ago"
            except Exception:
                age = ""
        tag = f" [{it['tags']}]" if it.get("tags") else ""       # optional LABELED enrichment, if present
        lines.append(f"- {it['title']}{tag} - {it['source']}"    # ASCII only (clean across ntfy clients)
                     + (f", {age}" if age else "") + f"\n  {it['url']}")
    health, unknown_today = _capture_health(jobs_path, manifest_conn, today_utc)
    body = health + "\n\n" + ("\n".join(lines) if lines else "(no headlines stored yet)")
    return {"title": f"VoltStream daily {today_utc}", "body": body, "unknown_today": unknown_today}


if __name__ == "__main__":
    import forecast_store
    conn = forecast_store._connect()
    d = compose_digest(manifest_conn=conn)
    conn.close()
    # line 1 = ntfy priority (high if any unknown-vintage today), line 2 = title, rest = body
    print("high" if d["unknown_today"] else "default")
    print(d["title"])
    print(d["body"])

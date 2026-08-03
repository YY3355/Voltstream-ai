"""
capture_latest.py — Kardashev-eval Task 5: the daily WITNESS capture.

Fetches Kardashev's /forecast/spread/latest once a day and stores the raw bytes with dual vintage:
THEIR published-at (`issued_at`, in the data) + OUR capture UTC (in the witness log). Committed daily by
auto_kardashev.sh, so from today forward the git history is an immutable, independently-witnessed record
of what their API served on each date — any FUTURE scoring is attestable by us, not resting on their API
history. Append-only + idempotent: one file per capture-date; re-running a day is a no-op.

Stored under research/kardashev_eval/witness/:
    latest_<capture-date>.json   raw /latest bytes
    witness_log.jsonl            one row/day: captured_at_utc, their issued_at set, sha256, n, nodes
"""
import hashlib
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

BASE = "https://data.kardashevlabs.org"
UA = "VoltStream-audit/1.0 (independent scoring; contact mikeoc)"
WITNESS = os.path.join(os.path.dirname(__file__), "witness")


def capture_latest(dry_run=False):
    cap = datetime.now(timezone.utc)
    os.makedirs(WITNESS, exist_ok=True)
    fn = os.path.join(WITNESS, f"latest_{cap.strftime('%Y-%m-%d')}.json")
    if os.path.exists(fn):                              # append-only: never overwrite a witnessed day
        return {"status": "already-captured", "file": os.path.basename(fn)}
    if dry_run:
        return {"status": "dry-run", "would_write": os.path.basename(fn)}
    req = urllib.request.Request(f"{BASE}/forecast/spread/latest", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
    data = json.loads(body)                             # parse only to summarize; raw bytes are the record
    with open(fn, "wb") as f:
        f.write(body)
    entry = {"captured_at_utc": cap.isoformat(timespec="seconds"),
             "file": os.path.basename(fn),
             "sha256": hashlib.sha256(body).hexdigest(),
             "n_records": len(data),
             "their_issued_at": sorted(set(r["issued_at"] for r in data)),
             "nodes": sorted(set(r["node_id"] for r in data)),
             "attestation": "Kardashev /forecast/spread/latest AS SERVED; vintage = their issued_at "
                            "(published-at) + our captured_at_utc. Committed daily = immutable witness."}
    with open(os.path.join(WITNESS, "witness_log.jsonl"), "a") as f:
        f.write(json.dumps(entry) + "\n")
    return {"status": "captured", **entry}


if __name__ == "__main__":
    print(json.dumps(capture_latest(dry_run="--dry" in sys.argv), indent=2))

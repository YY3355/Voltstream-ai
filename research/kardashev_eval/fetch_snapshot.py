"""
fetch_snapshot.py — FETCH ONCE, FREEZE (Kardashev-eval Task 1, constraint 3).

Pulls Kardashev Labs' published spread forecasts from their public API and freezes the RAW bytes as a
committed artifact. All scoring runs on the frozen copy — never a live re-fetch. We attest ONLY to what
their API served on the fetch date (recorded in manifest.json), no stronger.

  base      https://data.kardashevlabs.org   (public, per Ashutosh; no auth)
  endpoints /forecast/spread/history?node_id=<id>&days=<n>   (per-node history)
            /forecast/spread/latest                          (current issuance, all nodes)

Polite: sequential, one request at a time, a short sleep between requests, an identifying User-Agent.
Idempotent-ish: writes into snapshot_<fetch-date>/; re-running the same day overwrites that day's freeze.
"""
import hashlib
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

BASE = "https://data.kardashevlabs.org"
UA = "VoltStream-audit/1.0 (independent scoring; contact mikeoc)"
DAYS = 90                           # the API's max; the real history is ~25 days, so this is the full span
SLEEP = 1.5                         # be kind to their API
NODES = ["HB_BUSAVG", "HB_HOUSTON", "HB_HUBAVG", "HB_NORTH", "HB_PAN", "HB_SOUTH", "HB_WEST",
         "LZ_AEN", "LZ_CPS", "LZ_HOUSTON", "LZ_LCRA", "LZ_NORTH", "LZ_RAYBN", "LZ_SOUTH", "LZ_WEST"]


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.status, r.read()


def main():
    fetch_dt = datetime.now(timezone.utc)
    outdir = os.path.join(os.path.dirname(__file__), f"snapshot_{fetch_dt.strftime('%Y-%m-%d')}")
    os.makedirs(outdir, exist_ok=True)
    manifest = {"fetched_at_utc": fetch_dt.isoformat(timespec="seconds"), "base": BASE,
                "user_agent": UA, "days_param": DAYS, "attestation":
                "raw forecasts AS SERVED BY the Kardashev API on the fetch date; no independent "
                "verification of their values — we score them against OUR settlement record.",
                "files": []}

    # per-node history
    for node in NODES:
        url = f"{BASE}/forecast/spread/history?node_id={node}&days={DAYS}"
        status, body = _get(url)
        fn = f"history_{node}.json"
        open(os.path.join(outdir, fn), "wb").write(body)
        rec = {"file": fn, "url": url, "http_status": status, "bytes": len(body),
               "sha256": hashlib.sha256(body).hexdigest()}
        try:
            d = json.loads(body)
            ts = sorted(r["ts"] for r in d)
            rec.update(n_records=len(d), ts_first=ts[0], ts_last=ts[-1],
                       n_issuances=len(set(r["issued_at"] for r in d)),
                       models=sorted(set(r["model"] for r in d)))
        except Exception as e:
            rec["parse_error"] = str(e)[:120]
        manifest["files"].append(rec)
        print(f"  {node}: {status} {len(body)}B "
              f"{rec.get('n_records','?')} recs {rec.get('ts_first','')[:10]}..{rec.get('ts_last','')[:10]}",
              flush=True)
        time.sleep(SLEEP)

    # latest (all nodes, current issuance)
    status, body = _get(f"{BASE}/forecast/spread/latest")
    open(os.path.join(outdir, "latest.json"), "wb").write(body)
    manifest["files"].append({"file": "latest.json", "url": f"{BASE}/forecast/spread/latest",
                              "http_status": status, "bytes": len(body),
                              "sha256": hashlib.sha256(body).hexdigest()})
    # openapi (the param contract, for the record)
    try:
        status, body = _get(f"{BASE}/openapi.json")
        open(os.path.join(outdir, "openapi.json"), "wb").write(body)
        manifest["files"].append({"file": "openapi.json", "http_status": status, "bytes": len(body),
                                  "sha256": hashlib.sha256(body).hexdigest()})
    except Exception as e:
        manifest["openapi_error"] = str(e)[:120]

    json.dump(manifest, open(os.path.join(outdir, "manifest.json"), "w"), indent=2)
    print("froze ->", outdir)


if __name__ == "__main__":
    main()

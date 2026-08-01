"""
forecast_store.py  —  vintage-stamped, append-only capture of ERCOT's expiring forecast &
outage products (the future training data for the decision-time-clean feature loop).

Builds directly on ercot_archiver's throttled/authed archive path:
    list_archive_docs(emil, day)  ->  each archive doc (postDatetime = ERCOT's publish/vintage)
    _get(href)                    ->  the raw zipped-CSV bytes

THE WHOLE POINT IS VINTAGE. Every captured doc records four things (constraint 1):
  * product id            — the EMIL (directory + manifest column)
  * forecast TARGET period — min/max target timestamp parsed from the file's rows (best-effort,
                             status-flagged; a snapshot product with no forecast horizon = "none")
  * publish/post time     — the doc's `postDatetime` AS REPORTED BY ERCOT (the vintage). If ERCOT
                             gives none, it is stored as vintage_status="unknown" and COUNTED —
                             never synthesized, backdated, or inferred.
  * our capture timestamp — UTC, stamped once at first capture.

APPEND-ONLY + IDEMPOTENT (constraint 2). One archive doc = one file on disk, named by
(postDatetime, docId). A doc already in the manifest is skipped — never re-downloaded, never
overwritten, never mutated. A later revision of the same product/period arrives as a NEW docId =
an additional vintage file. Re-running a capture produces a byte-identical archive.

NO LLM anywhere in this path (constraint 3).

Storage (all under ARCHIVE_DIR, default data_archive/ — gitignored; the launchd rhythm runs
locally so the archive + manifest live on the Mac, like dart_cache/):
    data_archive/forecasts/<EMIL>/<post-date>/<postDatetimeCompact>__<docId>.{zip,csv}
    data_archive/forecasts/manifest.db     — SQLite index (rebuildable from files via `reindex`)

CLI:
    python forecast_store.py capture NP4-732-CD 2026-07-31   # capture one product's post-day
    python forecast_store.py recent  NP4-732-CD              # capture the most recent post-day
    python forecast_store.py capture-all HIGH               # capture the tier's most recent day
    python forecast_store.py status                          # manifest summary per product
    python forecast_store.py reindex                         # rebuild manifest from files on disk
"""
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import zipfile
from datetime import datetime, timezone

import pandas as pd

from ercot_archiver import _get, list_archive_docs, most_recent_day

# ----------------------------- the confirmed capture set -----------------------------
# HIGH-8 = the decision-time feature ingredients (>=2yr archive retention; ongoing + full backfill).
# PERISHABLE-3 = intra-hour, <1yr retention — the ONLY truly perishable ones. Backfill everything
#   reachable now; ongoing capture is a DAILY batch of the prior day's postings (never 5-min polling).
PRODUCTS = {
    "NP4-732-CD": {"name": "Wind Power Production - Hourly Actual & Forecast (system)",
                   "family": "wind",   "cadence": "hourly",    "lag_days": 0, "tier": "HIGH"},
    "NP4-742-CD": {"name": "Wind Power Production - Hourly Actual & Forecast by Region",
                   "family": "wind",   "cadence": "hourly",    "lag_days": 0, "tier": "HIGH"},
    "NP4-737-CD": {"name": "Solar Power Production - Hourly Actual & Forecast (system)",
                   "family": "solar",  "cadence": "hourly",    "lag_days": 0, "tier": "HIGH"},
    "NP4-745-CD": {"name": "Solar Power Production - Hourly Actual & Forecast by Region",
                   "family": "solar",  "cadence": "hourly",    "lag_days": 0, "tier": "HIGH"},
    "NP3-560-CD": {"name": "Seven-Day Load Forecast by Forecast Zone",
                   "family": "load",   "cadence": "hourly",    "lag_days": 0, "tier": "HIGH"},
    "NP3-565-CD": {"name": "Seven-Day Load Forecast by Model and Weather Zone",
                   "family": "load",   "cadence": "hourly",    "lag_days": 0, "tier": "HIGH"},
    "NP3-233-CD": {"name": "Hourly Resource Outage Capacity",
                   "family": "outage", "cadence": "hourly",    "lag_days": 0, "tier": "HIGH"},
    # NP1-346 is a LAGGED snapshot (posted ~3 days after the outages it reports). lag_days=3 is
    # recorded prominently so the feature loop's available_at gate treats it correctly later —
    # it is a lagged input, NEVER a forward forecast.
    "NP1-346-ER": {"name": "Unplanned Resource Outages Report",
                   "family": "outage", "cadence": "daily",     "lag_days": 3, "tier": "HIGH"},
    "NP4-751-CD": {"name": "Intra-Hour Wind Power Forecast by Geographical Region",
                   "family": "wind",   "cadence": "intrahour", "lag_days": 0, "tier": "PERISHABLE"},
    "NP4-752-CD": {"name": "Intra-Hour Solar Power Forecast by Geographical Region",
                   "family": "solar",  "cadence": "intrahour", "lag_days": 0, "tier": "PERISHABLE"},
    "NP3-562-CD": {"name": "Intra-Hour Load Forecast by Weather Zone",
                   "family": "load",   "cadence": "intrahour", "lag_days": 0, "tier": "PERISHABLE"},
}

# MED — same generic archive code path, zero bespoke handling. Not in the default capture set
# (Mike: "no heroics for MED"); opt in explicitly via `capture-all MED` if the disk is acceptable.
MED_PRODUCTS = {
    "NP4-442-CD": {"name": "Hourly System-wide & Regional Wind Forecasts by Model",
                   "family": "wind",   "cadence": "hourly", "lag_days": 0, "tier": "MED"},
    "NP4-443-CD": {"name": "Hourly System-wide & Regional Solar Forecasts by Model",
                   "family": "solar",  "cadence": "hourly", "lag_days": 0, "tier": "MED"},
    "NP3-561-CD": {"name": "Seven-Day Load Forecast by Weather Zone",
                   "family": "load",   "cadence": "hourly", "lag_days": 0, "tier": "MED"},
    "NP3-566-CD": {"name": "Seven-Day Load Forecast by Model and Study Area",
                   "family": "load",   "cadence": "hourly", "lag_days": 0, "tier": "MED"},
    "NP3-161-CD": {"name": "Available Resource Planned Outage Capacity Margin - 7-Day-Plus",
                   "family": "outage", "cadence": "daily",  "lag_days": 0, "tier": "MED"},
    "NP3-162-CD": {"name": "Available Resource Planned Outage Capacity Margin - 7-Day",
                   "family": "outage", "cadence": "hourly", "lag_days": 0, "tier": "MED"},
}

ALL_PRODUCTS = {**PRODUCTS, **MED_PRODUCTS}


def _meta(emil):
    return ALL_PRODUCTS.get(emil, {})


def products_for(tier):
    """EMILs for a tier: HIGH, PERISHABLE, MED, or ALL (HIGH+PERISHABLE, the default capture set)."""
    if tier == "ALL":
        return [e for e, m in PRODUCTS.items()]                       # HIGH + PERISHABLE
    src = ALL_PRODUCTS
    return [e for e, m in src.items() if m.get("tier") == tier]


# ----------------------------- storage roots -----------------------------
def forecast_root():
    return os.path.join(os.environ.get("ARCHIVE_DIR", "data_archive"), "forecasts")


def manifest_path():
    return os.path.join(forecast_root(), "manifest.db")


# ----------------------------- manifest (SQLite index, rebuildable from files) -----------------------------
def _connect():
    os.makedirs(forecast_root(), exist_ok=True)
    conn = sqlite3.connect(manifest_path())
    conn.execute("""CREATE TABLE IF NOT EXISTS captures (
        doc_id           TEXT PRIMARY KEY,
        emil             TEXT NOT NULL,
        post_datetime    TEXT,
        vintage_status   TEXT NOT NULL,         -- 'ok' | 'unknown' (postDatetime missing, counted)
        target_start     TEXT,
        target_end       TEXT,
        target_status    TEXT,                  -- 'ok' | 'none' | 'empty'
        captured_at_utc  TEXT NOT NULL,
        rel_path         TEXT NOT NULL,
        sha256           TEXT NOT NULL,
        n_bytes          INTEGER,
        n_rows           INTEGER,
        source_lag_days  INTEGER,
        product_name     TEXT,
        family           TEXT
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_captures_emil ON captures(emil)")
    conn.commit()
    return conn


def _seen_docids(conn, emil):
    return {r[0] for r in conn.execute("SELECT doc_id FROM captures WHERE emil=?", (emil,))}


# ----------------------------- download + parse (raw stored, parsed only for metadata) -----------------------------
def _download_raw(doc):
    """The exact bytes ERCOT serves for this doc — stored verbatim for a faithful, byte-identical
    append-only archive."""
    href = doc["_links"]["endpoint"]["href"]
    return _get(href, timeout=120).content


def _parse_raw(raw):
    """raw bytes -> DataFrame (unzip if needed), for metadata extraction ONLY. None if unparseable.
    ERCOT CSVs are a mix of UTF-8 and Latin-1 (e.g. NP1-346), so both encodings are tried."""
    def _read(data):
        for enc in ("utf-8", "latin-1"):
            try:
                return pd.read_csv(io.BytesIO(data), encoding=enc)
            except UnicodeDecodeError:
                continue
            except Exception:
                return None
        return None
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
        return _read(zf.read(zf.namelist()[0]))
    except zipfile.BadZipFile:
        return _read(raw)
    except Exception:
        return None


# Target-date/hour columns vary by product in casing & underscores (DeliveryDate vs DELIVERY_DATE,
# HourEnding vs HOUR_ENDING). Match on a normalized key (lowercased, alphanumerics only).
def _norm(c):
    return re.sub(r"[^a-z0-9]", "", str(c).lower())


_DATE_KEYS = {"deliverydate", "operday", "operatingdate", "date"}
_HOUR_KEYS = {"hourending", "hourbeginning", "hourend", "hour"}


def _find_col(df, keys):
    return next((c for c in df.columns if _norm(c) in keys), None)


def _extract_target_span(df):
    """Best-effort (start_iso, end_iso, status) of the forecast TARGET period from the file's rows.
    status: 'ok' (parsed), 'none' (no recognizable target column — e.g. a snapshot report),
    'empty' (no rows). Never guesses a vintage; this is only the *target* horizon, data-carried."""
    if df is None:
        return (None, None, "none")
    if not len(df):
        return (None, None, "empty")
    dcol = _find_col(df, _DATE_KEYS)
    if not dcol:
        return (None, None, "none")
    dates = pd.to_datetime(df[dcol], errors="coerce")
    hcol = _find_col(df, _HOUR_KEYS)
    if hcol is not None:
        hr = pd.to_numeric(df[hcol].astype(str).str.extract(r"(\d{1,2})")[0], errors="coerce")
        ts = dates + pd.to_timedelta(hr.fillna(0), unit="h")
    else:
        ts = dates
    ts = ts.dropna()
    if not len(ts):
        return (None, None, "none")
    return (ts.min().isoformat(), ts.max().isoformat(), "ok")


# ----------------------------- file naming (vintage-stamped) -----------------------------
def _doc_target(root, emil, doc, ext):
    """(abs_path, vintage_status). Path embeds the vintage: <post-date>/<postDtCompact>__<docId>."""
    post = doc.get("postDatetime")
    docid = re.sub(r"[^0-9A-Za-z_-]", "", str(doc.get("docId", "nodoc"))) or "nodoc"
    if post:
        day = str(post)[:10]
        stamp = re.sub(r"[^0-9T]", "", str(post))[:15]                # 20260731T145500
        vint = "ok"
    else:
        day, stamp, vint = "novintage", "NOVINTAGE", "unknown"
    path = os.path.join(root, emil, day, f"{stamp}__{docid}{ext}")
    return path, vint


# ----------------------------- capture -----------------------------
def capture_product(emil, day=None, dry_run=False, conn=None):
    """Capture every archive doc posted on `day` (YYYY-MM-DD, default = most recent) for `emil`,
    append-only + idempotent. Returns a summary dict."""
    own = conn is None
    conn = conn or _connect()
    root = forecast_root()
    if day is None:
        day = most_recent_day(emil)
    res = {"emil": emil, "day": day, "listed": 0, "new": 0, "skipped": 0,
           "unknown_vintage": 0, "errors": 0}
    if not day:
        if own:
            conn.close()
        return res
    docs = list_archive_docs(emil, day)
    res["listed"] = len(docs)
    seen = _seen_docids(conn, emil)
    for doc in docs:
        docid = str(doc.get("docId", ""))
        if docid and docid in seen:                     # idempotent: never re-fetch/overwrite
            res["skipped"] += 1
            continue
        try:
            raw = _download_raw(doc)
        except Exception:
            res["errors"] += 1
            continue
        ext = ".zip" if raw[:2] == b"PK" else ".csv"
        path, vint = _doc_target(root, emil, doc, ext)
        if vint == "unknown":
            res["unknown_vintage"] += 1
        df = _parse_raw(raw)
        tstart, tend, tstatus = _extract_target_span(df)
        if dry_run:
            res["new"] += 1
            seen.add(docid)
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):                    # append-only: never overwrite a vintage
            with open(path, "wb") as f:
                f.write(raw)
        conn.execute(
            """INSERT OR IGNORE INTO captures
               (doc_id, emil, post_datetime, vintage_status, target_start, target_end,
                target_status, captured_at_utc, rel_path, sha256, n_bytes, n_rows,
                source_lag_days, product_name, family)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (docid, emil, doc.get("postDatetime"), vint, tstart, tend, tstatus,
             datetime.now(timezone.utc).isoformat(timespec="seconds"),
             os.path.relpath(path, root), hashlib.sha256(raw).hexdigest(), len(raw),
             (len(df) if df is not None else None), _meta(emil).get("lag_days", 0),
             _meta(emil).get("name", ""), _meta(emil).get("family", "")))
        conn.commit()
        seen.add(docid)
        res["new"] += 1
    if own:
        conn.close()
    return res


def capture_all(tier="ALL", day=None, dry_run=False):
    """Capture the most recent post-day for every product in `tier`. Returns list of summaries."""
    conn = _connect()
    out = [capture_product(e, day=day, dry_run=dry_run, conn=conn) for e in products_for(tier)]
    conn.close()
    return out


# ----------------------------- backfill (staged, resumable, heartbeat) -----------------------------
# A completed past day is immutable, so once fully captured it is recorded in <root>/<EMIL>/
# .backfilled.json and skipped WITHOUT a network call on resume — a re-run continues where it
# stopped (e.g. after a laptop sleep) instead of restarting. Idempotency still holds doc-by-doc.
def _done_path(emil):
    return os.path.join(forecast_root(), emil, ".backfilled.json")


def _load_done(emil):
    p = _done_path(emil)
    if os.path.exists(p):
        try:
            return set(json.load(open(p)))
        except Exception:
            return set()
    return set()


def _mark_done(emil, day):
    os.makedirs(os.path.dirname(_done_path(emil)), exist_ok=True)
    d = _load_done(emil)
    d.add(day)
    json.dump(sorted(d), open(_done_path(emil), "w"))


def backfill_product(emil, days=730, end=None, conn=None, heartbeat=True):
    """Backfill `days` of complete post-days for `emil`, OLDEST-first (grab the rolling-off edge
    first). Resumable: days already fully captured are skipped without a network call. Prints a
    `progress: <emil> <day> ...` heartbeat so a resumed run shows where it stands. Returns totals."""
    own = conn is None
    conn = conn or _connect()
    end = (pd.Timestamp(end).normalize() if end else pd.Timestamp.now().normalize())
    today = pd.Timestamp.now().normalize().strftime("%Y-%m-%d")
    done = _load_done(emil)
    day_list = [(end - pd.Timedelta(days=k)).strftime("%Y-%m-%d") for k in range(days, -1, -1)]
    tot = {"emil": emil, "days_total": len(day_list), "days_captured": 0, "days_skipped_done": 0,
           "new": 0, "skipped_docs": 0, "unknown_vintage": 0, "errors": 0, "no_doc_days": 0}
    for i, day in enumerate(day_list, 1):
        if day in done:
            tot["days_skipped_done"] += 1
            continue
        r = capture_product(emil, day=day, conn=conn)
        tot["new"] += r["new"]
        tot["skipped_docs"] += r["skipped"]
        tot["unknown_vintage"] += r["unknown_vintage"]
        tot["errors"] += r["errors"]
        tot["days_captured"] += 1
        if r["listed"] == 0:
            tot["no_doc_days"] += 1
        # mark a COMPLETE past day done only if no doc errored (so a partial day is retried later)
        if r["errors"] == 0 and day < today:
            _mark_done(emil, day)
            done.add(day)
        if heartbeat:
            print(f"progress: {emil} {day} new={r['new']} skip={r['skipped']} "
                  f"listed={r['listed']} err={r['errors']} ({i}/{len(day_list)})", flush=True)
    if own:
        conn.close()
    return tot


def backfill_staged(trio_days=400, high_days=730):
    """The Task-3 run: STAGE 1 = the perishable intra-hour trio (backfill everything reachable, they
    roll off a <1yr cliff), then STAGE 2 = HIGH-8 at full 730d. One resumable pass over one conn."""
    conn = _connect()
    print(f"=== STAGE 1: intra-hour trio (perishable, {trio_days}d reach) ===", flush=True)
    for e in products_for("PERISHABLE"):
        print(f"--- {e} ---", flush=True)
        print("TOTAL", backfill_product(e, trio_days, conn=conn), flush=True)
    print(f"=== STAGE 2: HIGH-8 @ {high_days}d ===", flush=True)
    for e in products_for("HIGH"):
        print(f"--- {e} ---", flush=True)
        print("TOTAL", backfill_product(e, high_days, conn=conn), flush=True)
    conn.close()
    print("=== BACKFILL COMPLETE ===", flush=True)


# ----------------------------- reindex + status -----------------------------
def reindex():
    """Rebuild the manifest from the files on disk (the files are the source of truth). Preserves
    each file's original capture time via its mtime. Idempotent."""
    root = forecast_root()
    conn = _connect()
    conn.execute("DELETE FROM captures")
    n = 0
    for dirpath, _, files in os.walk(root):
        for fn in files:
            if fn == "manifest.db" or not re.search(r"__.+\.(zip|csv)$", fn):
                continue
            path = os.path.join(dirpath, fn)
            emil = os.path.basename(os.path.dirname(os.path.dirname(path)))
            raw = open(path, "rb").read()
            df = _parse_raw(raw)
            tstart, tend, tstatus = _extract_target_span(df)
            stamp, docid = fn.rsplit(".", 1)[0].split("__", 1)
            vint = "unknown" if stamp == "NOVINTAGE" else "ok"
            post = None if vint == "unknown" else _stamp_to_iso(stamp)
            cap = datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).isoformat(timespec="seconds")
            conn.execute(
                """INSERT OR IGNORE INTO captures
                   (doc_id, emil, post_datetime, vintage_status, target_start, target_end,
                    target_status, captured_at_utc, rel_path, sha256, n_bytes, n_rows,
                    source_lag_days, product_name, family)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (docid, emil, post, vint, tstart, tend, tstatus, cap,
                 os.path.relpath(path, root), hashlib.sha256(raw).hexdigest(), len(raw),
                 (len(df) if df is not None else None), _meta(emil).get("lag_days", 0),
                 _meta(emil).get("name", ""), _meta(emil).get("family", "")))
            n += 1
    conn.commit()
    conn.close()
    return n


def _stamp_to_iso(stamp):
    """'20260731T145500' -> '2026-07-31T14:55:00' (best-effort; for reindex only)."""
    m = re.match(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})", stamp)
    return f"{m[1]}-{m[2]}-{m[3]}T{m[4]}:{m[5]}:{m[6]}" if m else None


def status():
    """Per-product manifest summary: files, vintage span, unknown-vintage count, earliest vintage."""
    conn = _connect()
    rows = conn.execute(
        """SELECT emil, COUNT(*), MIN(post_datetime), MAX(post_datetime),
                  SUM(vintage_status='unknown'), MIN(target_start), MAX(target_end)
           FROM captures GROUP BY emil ORDER BY emil""").fetchall()
    conn.close()
    return rows


def report():
    """Task-3 deliverable, per product: files, EARLIEST reachable vintage (the training-span floor
    the feature loop inherits), vintage span, disk, unknown-vintage count, lag_days."""
    conn = _connect()
    root = forecast_root()
    rows = conn.execute(
        """SELECT emil, COUNT(*), MIN(post_datetime), MAX(post_datetime), SUM(n_bytes),
                  SUM(vintage_status='unknown'), MIN(source_lag_days)
           FROM captures GROUP BY emil ORDER BY emil""").fetchall()
    conn.close()
    out = []
    for emil, n, pmin, pmax, nbytes, unk, lag in rows:
        out.append({"emil": emil, "files": n, "earliest_vintage": str(pmin)[:10],
                    "latest_vintage": str(pmax)[:10], "disk_mb": round((nbytes or 0) / 1e6, 1),
                    "unknown_vintage": unk or 0, "lag_days": lag or 0,
                    "name": _meta(emil).get("name", "")})
    return out


# ----------------------------- CLI -----------------------------
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    dry = os.environ.get("DRY_RUN") == "1"
    if cmd == "capture":
        emil = sys.argv[2]
        day = sys.argv[3] if len(sys.argv) > 3 else None
        print(capture_product(emil, day=day, dry_run=dry))
    elif cmd == "recent":
        print(capture_product(sys.argv[2], day=None, dry_run=dry))
    elif cmd == "capture-all":
        tier = sys.argv[2] if len(sys.argv) > 2 else "ALL"
        for r in capture_all(tier, dry_run=dry):
            print(r)
    elif cmd == "backfill":
        emil = sys.argv[2]
        days = int(sys.argv[3]) if len(sys.argv) > 3 else 730
        print(backfill_product(emil, days))
    elif cmd == "backfill-staged":
        trio = int(sys.argv[2]) if len(sys.argv) > 2 else 400
        high = int(sys.argv[3]) if len(sys.argv) > 3 else 730
        backfill_staged(trio, high)
    elif cmd == "report":
        for r in report():
            print(f"{r['emil']:12} files={r['files']:>6} earliest={r['earliest_vintage']} "
                  f"latest={r['latest_vintage']} disk={r['disk_mb']:>7}MB unk={r['unknown_vintage']} "
                  f"lag={r['lag_days']}d  {r['name'][:40]}")
    elif cmd == "reindex":
        print(f"reindexed {reindex()} files")
    elif cmd == "status":
        print(f"{'EMIL':12} {'files':>6} {'unk':>4}  vintage span                        target span")
        for emil, n, pmin, pmax, unk, tmin, tmax in status():
            print(f"{emil:12} {n:6d} {unk or 0:4d}  {str(pmin)[:19]} .. {str(pmax)[:19]}  {str(tmin)[:16]} .. {str(tmax)[:16]}")
    else:
        print(__doc__)

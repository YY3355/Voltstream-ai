"""
ercot_archiver.py  —  one reusable puller for ERCOT's official Public API archive products.

Pattern (works for ANY archive product — NP6-86-CD SCED shadow prices, NP6-905-CD settlement
point prices, ...):

    auth (ROPC, reused from ercot_catalog)
      -> archive listing  GET /archive/{EMIL}?postDatetimeFrom&postDatetimeTo   (paginated)
      -> download each day's docs  ?download={docId}  (zipped CSV)
      -> assemble -> per-day pickle cache under data_archive/archive_cache/{EMIL}_{day}.pkl

Design decisions:
  * Complete past days are immutable -> cached forever. A day with no archived docs is
    remembered in {EMIL}_missing.json so we never re-scan it (known-missing-day memory).
  * Schema-tolerant: whatever columns the product's CSV carries pass straight through; two
    provenance columns (_docId, _postDatetime) are added.
  * One OAuth token per run, auto-refreshed once on a 401 (backfills can outlive a token).

Auth env vars (from apiexplorer.ercot.com, free): ERCOT_API_USERNAME, ERCOT_API_PASSWORD,
ERCOT_API_SUBSCRIPTION_KEY. Nothing is written to disk except the product data itself.

CLI:
    python ercot_archiver.py recent   NP6-86-CD        # pull the most recent day, summarize
    python ercot_archiver.py backfill NP6-905-CD 30    # ensure last 30 days are cached
"""
import io
import json
import os
import sys
import time
import zipfile

import pandas as pd
import requests

from ercot_catalog import get_token, BASE

CACHE_DIR = os.path.join(os.environ.get("ARCHIVE_DIR", "data_archive"), "archive_cache")
PAGE_SIZE = 1000
MIN_INTERVAL = float(os.environ.get("ERCOT_API_MIN_INTERVAL", "0.3"))  # throttle: be kind to the API
MAX_RETRIES = 6

_token = {"val": None}
_last = {"t": 0.0}


# ----------------------------- auth + request plumbing -----------------------------
def _auth_headers(refresh=False):
    if refresh or not _token["val"]:
        _token["val"] = get_token()
    key = os.environ.get("ERCOT_API_SUBSCRIPTION_KEY")
    if not key:
        raise SystemExit("Missing ERCOT_API_SUBSCRIPTION_KEY env var (from apiexplorer.ercot.com).")
    return {"Authorization": f"Bearer {_token['val']}", "Ocp-Apim-Subscription-Key": key}


def _get(url, **kw):
    """GET with subscription key + bearer token. Throttled, with a refresh-once on 401 and
    exponential backoff on 429 (rate limit) — high-frequency products post ~288 docs/day."""
    timeout = kw.pop("timeout", 60)
    for attempt in range(MAX_RETRIES):
        gap = time.time() - _last["t"]
        if gap < MIN_INTERVAL:
            time.sleep(MIN_INTERVAL - gap)
        r = requests.get(url, headers=_auth_headers(), timeout=timeout, **kw)
        _last["t"] = time.time()
        if r.status_code == 401:          # token expired -> refresh and retry
            _auth_headers(refresh=True)
            continue
        if r.status_code == 429:          # rate limited -> honor Retry-After / back off
            time.sleep(float(r.headers.get("Retry-After", min(2 ** attempt, 30))))
            continue
        r.raise_for_status()
        return r
    r.raise_for_status()
    return r


# ----------------------------- cache paths + missing memory -----------------------------
def _day_path(emil, day):
    return os.path.join(CACHE_DIR, f"{emil}_{day}.pkl")


def _missing_path(emil):
    return os.path.join(CACHE_DIR, f"{emil}_missing.json")


def _load_missing(emil):
    p = _missing_path(emil)
    if os.path.exists(p):
        try:
            return set(json.load(open(p)))
        except Exception:
            return set()
    return set()


def _remember_missing(emil, day):
    os.makedirs(CACHE_DIR, exist_ok=True)
    miss = _load_missing(emil)
    miss.add(day)
    json.dump(sorted(miss), open(_missing_path(emil), "w"))


# ----------------------------- archive listing + download -----------------------------
def list_archive_docs(emil, day):
    """Every archive doc whose postDatetime falls on `day` (YYYY-MM-DD), across all pages."""
    frm = f"{day}T00:00:00"
    to = (pd.Timestamp(day) + pd.Timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")
    docs, page = [], 1
    while True:
        p = _get(f"{BASE}/archive/{emil}",
                 params={"size": PAGE_SIZE, "page": page,
                         "postDatetimeFrom": frm, "postDatetimeTo": to}).json()
        docs += (p.get("archives") or [])
        meta = p.get("_meta") or {}
        if page >= (meta.get("totalPages") or 1):
            break
        page += 1
    return docs


def download_doc(doc):
    """Download one archive doc (?download=docId), unzip, parse its CSV -> DataFrame."""
    href = doc["_links"]["endpoint"]["href"]
    raw = _get(href, timeout=120).content
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
        df = pd.read_csv(zf.open(zf.namelist()[0]))
    except zipfile.BadZipFile:
        df = pd.read_csv(io.BytesIO(raw))
    df["_docId"] = doc.get("docId")
    df["_postDatetime"] = doc.get("postDatetime")
    return df


def most_recent_day(emil):
    """The date (YYYY-MM-DD) of the newest archived doc for this product."""
    p = _get(f"{BASE}/archive/{emil}", params={"size": 1, "page": 1}).json()
    arch = p.get("archives") or []
    return str(arch[0]["postDatetime"])[:10] if arch else None


# ----------------------------- fast query-endpoint price backfill -----------------------------
# Some products expose a queryable data artifact that returns filtered tabular rows in one
# paginated call — vastly faster than per-interval archive downloads for a single point.
def fetch_prices_query(days=30, hub="HB_HOUSTON", emil="NP6-905-CD", artifact="spp_node_zone_hub"):
    """Pull the last `days` of one settlement point's RT SPP via the query data endpoint.
    Returns a DataFrame in the download_doc/archive CSV schema (so _api_frame_to_series reads it)."""
    end = pd.Timestamp.now().normalize()
    frm = (end - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    to = end.strftime("%Y-%m-%d")
    url = f"{BASE}/{emil.lower()}/{artifact}"
    rows, fields, page = [], None, 1
    while True:
        p = _get(url, params={"deliveryDateFrom": frm, "deliveryDateTo": to,
                              "settlementPoint": hub, "size": 1000, "page": page}).json()
        fields = fields or [f["name"] for f in (p.get("fields") or [])]
        rows += (p.get("data") or [])
        meta = p.get("_meta") or {}
        if page >= (meta.get("totalPages") or 1):
            break
        page += 1
    df = pd.DataFrame(rows, columns=fields)
    return df.rename(columns={"deliveryDate": "DeliveryDate", "deliveryHour": "DeliveryHour",
                              "deliveryInterval": "DeliveryInterval", "settlementPoint": "SettlementPointName",
                              "settlementPointPrice": "SettlementPointPrice"})


def backfill_prices_to_cache(days=30, hub="HB_HOUSTON", emil="NP6-905-CD"):
    """Fast backfill: query the range once, write per-COMPLETE-day pkls into the archive cache
    in the schema price_store._api_frame_to_series expects. Returns the days written."""
    df = fetch_prices_query(days, hub, emil)
    if not len(df):
        return []
    df["_postDatetime"] = ""  # query returns final settled values; no repost ambiguity
    os.makedirs(CACHE_DIR, exist_ok=True)
    today = pd.Timestamp.now().normalize().strftime("%Y-%m-%d")
    written = []
    for day, g in df.groupby(df["DeliveryDate"].astype(str)):
        d = day[:10]
        if d >= today:
            continue  # today is still filling — skip
        g.to_pickle(_day_path(emil, d))
        written.append(d)
    return sorted(written)


def list_bundles(emil="NP6-905-CD"):
    """List the monthly archive bundles for a product (newest-first source, returned sorted by
    name). Each bundle is a whole month's data as one downloadable zip — far cheaper than the
    per-interval archive docs for deep history. Returns [{name, date, href}]."""
    out, page = [], 1
    while True:
        p = _get(f"{BASE}/bundle/{emil}", params={"size": 1000, "page": page}).json()
        for b in (p.get("bundles") or []):
            out.append({"name": b["friendlyName"], "date": str(b["postDatetime"])[:10],
                        "href": b["_links"]["endpoint"]["href"]})
        if page >= (p.get("_meta", {}).get("totalPages") or 1):
            break
        page += 1
    return sorted(out, key=lambda x: x["name"])


def bundle_to_hub_series(zip_bytes, hub="HB_HOUSTON"):
    """Parse a monthly SPP bundle (zip of per-interval nested zips, each a 1-line-per-point CSV)
    into a 15-min price series for one hub. Timestamp = DeliveryDate + (DeliveryHour-1)h +
    (DeliveryInterval-1)*15min (verified to the cent vs gridstatus last session). Fast string
    scan (no pandas per inner file — a month is ~2700 tiny CSVs)."""
    key = f",{hub.upper()},"
    ts_list, px_list = [], []
    outer = zipfile.ZipFile(io.BytesIO(zip_bytes))
    for name in outer.namelist():
        try:
            izf = zipfile.ZipFile(io.BytesIO(outer.read(name)))
            csv_txt = izf.read(izf.namelist()[0]).decode("utf-8", "ignore")
        except Exception:
            continue
        for line in csv_txt.splitlines():
            if key in line:                                # DeliveryDate,H,I,HUB,HU,price,DST
                f = line.split(",")
                try:
                    ts = pd.Timestamp(f[0]) + pd.Timedelta(minutes=(int(f[1]) - 1) * 60 + (int(f[2]) - 1) * 15)
                    ts_list.append(ts); px_list.append(float(f[5]))
                except Exception:
                    pass
                break
    s = pd.Series(px_list, index=pd.DatetimeIndex(ts_list)).sort_index()
    return s[~s.index.duplicated(keep="last")]


def backfill_decade_hub(hub="HB_HOUSTON", emil="NP6-905-CD", out_dir=None, verbose=True):
    """Download every monthly SPP bundle, parse the hub's 15-min series, and cache one pickle
    per YEAR under out_dir (default data_archive/decade/{year}.pkl, gitignored). Returns
    {year: n_points}. ~102 month-downloads for the full ERCOT history reachable via bundles."""
    out_dir = out_dir or os.path.join(os.environ.get("ARCHIVE_DIR", "data_archive"), "decade")
    os.makedirs(out_dir, exist_ok=True)
    by_year = {}
    for b in list_bundles(emil):
        try:
            s = bundle_to_hub_series(_get(b["href"], timeout=180).content, hub)
        except Exception as e:
            if verbose:
                print(f"decade: {b['name']} FAILED ({e})", flush=True)
            continue
        if not len(s):
            continue
        for yr, g in s.groupby(s.index.year):
            by_year.setdefault(int(yr), []).append(g)
        if verbose:
            print(f"decade: {b['name']} -> {len(s)} pts", flush=True)
    counts = {}
    for yr, parts in by_year.items():
        ser = pd.concat(parts).sort_index()
        ser = ser[~ser.index.duplicated(keep="last")]
        ser.name = f"{hub}_rt_spp"
        ser.to_pickle(os.path.join(out_dir, f"{yr}.pkl"))
        counts[yr] = len(ser)
    return counts


def fetch_constraints_query(days=14, emil="NP6-86-CD", artifact="shdw_prices_bnd_trns_const"):
    """Pull the last `days` of SCED binding-constraint shadow prices via the query endpoint.
    Returns a DataFrame in the download_doc CSV schema (ConstraintName/ShadowPrice/...)."""
    end = pd.Timestamp.now().normalize()
    frm = (end - pd.Timedelta(days=days)).strftime("%Y-%m-%dT00:00:00")
    to = end.strftime("%Y-%m-%dT00:00:00")
    url = f"{BASE}/{emil.lower()}/{artifact}"
    rows, fields, page = [], None, 1
    while True:
        p = _get(url, params={"SCEDTimestampFrom": frm, "SCEDTimestampTo": to, "size": 1000, "page": page}).json()
        fields = fields or [f["name"] for f in (p.get("fields") or [])]
        rows += (p.get("data") or [])
        meta = p.get("_meta") or {}
        if page >= (meta.get("totalPages") or 1):
            break
        page += 1
    df = pd.DataFrame(rows, columns=fields)
    return df.rename(columns={"SCEDTimestamp": "SCEDTimeStamp", "constraintName": "ConstraintName",
                              "contingencyName": "ContingencyName", "shadowPrice": "ShadowPrice"})


def backfill_constraints_to_cache(days=14, emil="NP6-86-CD"):
    """Fast backfill of recent SCED constraint days (query endpoint) for the bind-frequency
    counts. Writes per-COMPLETE-day pkls in the schema /api/constraints reads. Returns days."""
    df = fetch_constraints_query(days, emil)
    if not len(df) or "SCEDTimeStamp" not in df.columns:
        return []
    df["_day"] = pd.to_datetime(df["SCEDTimeStamp"]).dt.strftime("%Y-%m-%d")
    os.makedirs(CACHE_DIR, exist_ok=True)
    today = pd.Timestamp.now().normalize().strftime("%Y-%m-%d")
    written = []
    for day, g in df.groupby("_day"):
        if day >= today:
            continue
        g.drop(columns=["_day"]).to_pickle(_day_path(emil, day))
        written.append(day)
    return sorted(written)


# ----------------------------- per-day fetch + cache (the archiver) -----------------------------
def fetch_day(emil, day):
    """Assemble all archived docs for one operating day into one DataFrame (uncached)."""
    docs = list_archive_docs(emil, day)
    frames = [download_doc(d) for d in docs]
    frames = [f for f in frames if len(f)]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def ensure_day(emil, day, fetch=True):
    """Cached day DataFrame; fetch + cache on a miss. Empty days are remembered, not re-scanned."""
    p = _day_path(emil, day)
    if os.path.exists(p):
        return pd.read_pickle(p)
    if day in _load_missing(emil):
        return pd.DataFrame()
    if not fetch:
        return pd.DataFrame()
    df = fetch_day(emil, day)
    os.makedirs(CACHE_DIR, exist_ok=True)
    if len(df):
        df.to_pickle(p)
    else:
        _remember_missing(emil, day)
    return df


def ensure_days(emil, n_days=30, end=None, fetch=True):
    """Ensure the last n complete days for `emil` are cached. Returns (have, fetched, missing)."""
    end = pd.Timestamp(end).normalize() if end else pd.Timestamp.now().normalize()
    days = [(end - pd.Timedelta(days=k)).strftime("%Y-%m-%d") for k in range(n_days, 0, -1)]
    known = _load_missing(emil)
    have, fetched, missing = [], [], []
    for day in days:
        if os.path.exists(_day_path(emil, day)):
            have.append(day)
            continue
        if day in known or not fetch:
            missing.append(day)
            continue
        df = ensure_day(emil, day, fetch=True)
        if len(df):
            have.append(day)
            fetched.append(day)
        else:
            missing.append(day)
    return have, fetched, missing


def cached_days(emil):
    if not os.path.isdir(CACHE_DIR):
        return []
    pre, suf = f"{emil}_", ".pkl"
    return sorted(f[len(pre):-len(suf)] for f in os.listdir(CACHE_DIR)
                  if f.startswith(pre) and f.endswith(suf))


# ----------------------------- CLI -----------------------------
def _summarize(emil, day, df):
    print(f"{emil} {day}: {len(df)} rows, {df['_docId'].nunique()} SCED runs/docs")
    print("columns:", list(c for c in df.columns if not c.startswith("_")))
    if "ConstraintName" in df.columns and "ShadowPrice" in df.columns:
        sp = df.copy()
        sp["ShadowPrice"] = pd.to_numeric(sp["ShadowPrice"], errors="coerce")
        binding = sp[sp["ShadowPrice"] > 0]
        top = (binding.groupby("ConstraintName")
               .agg(max_shadow=("ShadowPrice", "max"),
                    mean_shadow=("ShadowPrice", "mean"),
                    intervals=("ShadowPrice", "size"))
               .sort_values("max_shadow", ascending=False).head(12))
        print(f"\nbinding constraints (ShadowPrice > 0): {binding['ConstraintName'].nunique()} distinct")
        with pd.option_context("display.width", 200):
            print(top.round(2).to_string())
    else:
        spc = next((c for c in df.columns if c.lower() in ("settlementpoint", "settlementpointname")), None)
        pc = next((c for c in df.columns if "price" in c.lower()), None)
        if spc and pc:
            v = df.copy()
            v[pc] = pd.to_numeric(v[pc], errors="coerce")
            print(f"\nsettlement points: {v[spc].nunique()} | price col: {pc}")
            print(v.groupby(spc)[pc].mean().sort_values(ascending=False).head(8).round(2).to_string())


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "recent"
    emil = sys.argv[2] if len(sys.argv) > 2 else "NP6-86-CD"
    if cmd == "recent":
        day = most_recent_day(emil)
        if not day:
            raise SystemExit(f"no archived docs for {emil}")
        df = ensure_day(emil, day)
        _summarize(emil, day, df)
    elif cmd == "backfill":
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 30
        have, fetched, missing = ensure_days(emil, n)
        print(f"{emil}: {len(have)} cached ({len(fetched)} fetched now), {len(missing)} missing")
        print("range:", (cached_days(emil)[0], cached_days(emil)[-1]) if cached_days(emil) else None)
    else:
        print(__doc__)

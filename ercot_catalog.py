"""
ercot_catalog.py  —  ingest ERCOT's product catalog into a queryable table.

Calls the official ERCOT Public API root listing (GET /api/public-reports), which
enumerates every public data product, and saves each product's:
    product name · EMIL ID · endpoint · description · archive URL
into a SQLite table `ercot_products` (data_archive/ercot.db), plus a CSV mirror and
the raw JSON (so nothing is lost if ERCOT's schema differs from what we parse).

This catalog is EMIL-in-a-table: the front door for every future archiver dataset.
    python ercot_catalog.py fetch            # pull the live catalog (needs API creds)
    python ercot_catalog.py search shadow    # find e.g. SCED/DAM shadow-price products
    python ercot_catalog.py show             # summary of what's stored

AUTH (official ERCOT Public API): set these env vars, from your apiexplorer.ercot.com
account (free registration):
    ERCOT_API_USERNAME, ERCOT_API_PASSWORD, ERCOT_API_SUBSCRIPTION_KEY

HONEST NOTES: the parser is schema-tolerant (ERCOT's exact field names are verified on
first live run, not assumed); raw JSON is always saved verbatim; the token flow below is
the documented ROPC flow ERCOT's public API uses — if ERCOT changes it, the script prints
the server's actual response for debugging instead of guessing.
"""
import json
import os
import sqlite3
import sys

import pandas as pd

BASE = "https://api.ercot.com/api/public-reports"
AUTH_URL = ("https://ercotb2c.b2clogin.com/ercotb2c.onmicrosoft.com/"
            "B2C_1_PUBAPI-ROPC-FLOW/oauth2/v2.0/token")
CLIENT_ID = "fec253ea-0d06-4272-a5e6-b478baeecd70"   # ERCOT's published public client id
OUT_DIR = "data_archive"
DB = os.path.join(OUT_DIR, "ercot.db")
RAW = os.path.join(OUT_DIR, "ercot_products_raw.json")
CSV = os.path.join(OUT_DIR, "ercot_products.csv")


# ----------------------------- auth + fetch (live, Mac) -----------------------------
def get_token():
    import requests
    user = os.environ.get("ERCOT_API_USERNAME")
    pw = os.environ.get("ERCOT_API_PASSWORD")
    if not user or not pw:
        raise SystemExit("Missing ERCOT_API_USERNAME / ERCOT_API_PASSWORD env vars.\n"
                         "Register (free) at apiexplorer.ercot.com, then export them in ~/.zshrc.")
    r = requests.post(AUTH_URL, data={
        "grant_type": "password", "username": user, "password": pw,
        "scope": f"openid {CLIENT_ID} offline_access",
        "client_id": CLIENT_ID, "response_type": "id_token",
    }, timeout=30)
    if r.status_code != 200 or "id_token" not in r.json():
        raise SystemExit(f"ERCOT auth failed (HTTP {r.status_code}). Server said:\n{r.text[:600]}")
    return r.json()["id_token"]


def fetch_catalog():
    import requests
    key = os.environ.get("ERCOT_API_SUBSCRIPTION_KEY")
    if not key:
        raise SystemExit("Missing ERCOT_API_SUBSCRIPTION_KEY env var (from apiexplorer.ercot.com).")
    headers = {"Authorization": f"Bearer {get_token()}", "Ocp-Apim-Subscription-Key": key}
    pages, url, params = [], BASE, {"size": 1000, "page": 1}
    while True:
        r = requests.get(url, headers=headers, params=params, timeout=60)
        if r.status_code != 200:
            raise SystemExit(f"GET {url} -> HTTP {r.status_code}. Server said:\n{r.text[:600]}")
        payload = r.json()
        pages.append(payload)
        meta = payload.get("_meta") or {}
        total = meta.get("totalPages") or 1
        if params["page"] >= total:
            break
        params["page"] += 1
    return pages


# ----------------------------- schema-tolerant parsing -----------------------------
_NAME_KEYS = ("reportName", "productName", "name", "reportDisplayName", "title")
_ID_KEYS = ("emilId", "reportTypeId", "productId", "id")
_DESC_KEYS = ("description", "reportDescription", "summary")
_EP_KEYS = ("endpoint", "url", "href", "path")


def _first(d: dict, keys):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return str(d[k])
    return None


def _find_product_list(payload):
    """Locate the list of product dicts wherever ERCOT nests it."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        # common containers first, then any list of dicts that looks product-shaped
        for k in ("products", "reports", "data", "items", "publicReports", "_embedded"):
            if k in payload:
                found = _find_product_list(payload[k])
                if found:
                    return found
        for v in payload.values():
            if isinstance(v, list) and v and isinstance(v[0], dict) and _first(v[0], _ID_KEYS + _NAME_KEYS):
                return v
        for v in payload.values():
            if isinstance(v, (dict, list)):
                found = _find_product_list(v)
                if found:
                    return found
    return []


def parse_products(pages):
    rows, seen = [], set()
    for payload in pages:
        for p in _find_product_list(payload):
            if not isinstance(p, dict):
                continue
            emil = _first(p, _ID_KEYS)
            name = _first(p, _NAME_KEYS)
            if not emil and not name:
                continue
            if emil in seen:
                continue
            seen.add(emil)
            endpoint = _first(p, _EP_KEYS)
            if not endpoint and isinstance(p.get("_links"), dict):
                link = p["_links"].get("self") or {}
                endpoint = link.get("href") if isinstance(link, dict) else None
            if not endpoint and emil:
                endpoint = f"{BASE}/{emil}"
            rows.append({
                "product_name": name or "",
                "emil_id": emil or "",
                "endpoint": endpoint or "",
                "description": _first(p, _DESC_KEYS) or "",
                "archive_url": f"{BASE}/archive/{emil}" if emil else "",
            })
    return pd.DataFrame(rows)


# ----------------------------- storage -----------------------------
def save_products(df: pd.DataFrame, raw_pages=None):
    os.makedirs(OUT_DIR, exist_ok=True)
    con = sqlite3.connect(DB)
    df.to_sql("ercot_products", con, if_exists="replace", index=False)
    con.execute("CREATE INDEX IF NOT EXISTS idx_emil ON ercot_products(emil_id)")
    con.commit(); con.close()
    df.to_csv(CSV, index=False)
    if raw_pages is not None:
        with open(RAW, "w") as f:
            json.dump(raw_pages, f)
    return DB


def search(term: str):
    con = sqlite3.connect(DB)
    q = f"%{term}%"
    df = pd.read_sql("SELECT emil_id, product_name, description FROM ercot_products "
                     "WHERE product_name LIKE ? OR description LIKE ? OR emil_id LIKE ?",
                     con, params=(q, q, q))
    con.close()
    return df


# ----------------------------- CLI -----------------------------
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if cmd == "fetch":
        pages = fetch_catalog()
        df = parse_products(pages)
        if df.empty:
            with open(RAW + ".debug", "w") as f:
                json.dump(pages, f)
            raise SystemExit("Catalog fetched but parser found 0 products — raw JSON saved to "
                             f"{RAW}.debug; send me the top-level keys and I'll adapt the parser.")
        save_products(df, pages)
        print(f"saved {len(df)} products -> {DB} (table ercot_products), {CSV}, raw JSON kept")
        print(df.head(8).to_string(index=False, max_colwidth=48))
    elif cmd == "search":
        term = " ".join(sys.argv[2:]) or "shadow"
        df = search(term)
        print(df.to_string(index=False, max_colwidth=60) if len(df) else f"no products match '{term}'")
    elif cmd == "show":
        con = sqlite3.connect(DB)
        n = con.execute("SELECT COUNT(*) FROM ercot_products").fetchone()[0]
        print(f"{n} products in ercot_products ({DB})")
        con.close()
    else:
        # fixture self-test: plausible + hostile payload shapes -> parse -> sqlite roundtrip
        fixture = [{"_meta": {"totalPages": 1}, "products": [
            {"emilId": "NP6-86-CD", "reportName": "SCED Shadow Prices and Binding Transmission Constraints",
             "description": "Binding constraints w/ shadow prices", "endpoint": f"{BASE}/np6-86-cd"},
            {"emilId": "NP4-191-CD", "reportName": "DAM Shadow Prices"},
            {"weird": "row without id or name"},
            {"emilId": "NP6-86-CD", "reportName": "duplicate to drop"},
        ]}]
        nested = [{"_embedded": {"reports": [{"reportTypeId": "NP4-183-CD",
                   "name": "DAM Hourly LMPs", "_links": {"self": {"href": f"{BASE}/np4-183-cd"}}}]}}]
        df = parse_products(fixture + nested)
        assert len(df) == 3, f"expected 3 parsed products, got {len(df)}"
        assert set(df.emil_id) == {"NP6-86-CD", "NP4-191-CD", "NP4-183-CD"}
        assert df[df.emil_id == "NP4-191-CD"].iloc[0].endpoint == f"{BASE}/NP4-191-CD"  # constructed
        assert df[df.emil_id == "NP4-191-CD"].iloc[0].archive_url == f"{BASE}/archive/NP4-191-CD"
        globals()["DB"] = os.path.join(OUT_DIR, "test_ercot.db")
        save_products(df)
        hits = search("shadow")
        assert len(hits) == 2, f"search 'shadow' should hit 2, got {len(hits)}"
        os.remove(globals()["DB"])
        print("fixture self-test PASSED — parse (2 payload shapes, dedup, junk rows), sqlite, search OK")
        print("live run on the Mac:  python ercot_catalog.py fetch   (needs API env vars)")

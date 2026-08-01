"""
news_store.py  —  honest energy-news ingestion for the VoltStream "right now" sidebar + digest.

CONSTRAINT 3 (honesty) is the whole design:
  * The STORE path is pure: each item is headline + source + timestamp + link, deduped by GUID/URL.
    NO LLM anywhere in fetch/parse/store — a headline is never paraphrased on the way in.
  * An OPTIONAL, clearly-LABELED enrichment pass (enrich()) may add a <=1-line summary and/or
    relevance tags, written to SEPARATE columns with the enriching model recorded (llm_model). The
    UI always renders the summary/tags WITH the original headline + link adjacent — the source is
    never more than one click away, never shown as if it were the source's own words.

Stdlib only (no feedparser in the volt env): urllib + xml.etree parse both RSS 2.0 and Atom.

Storage: data_archive/news.db (gitignored) table `news`. Read-only surface = /api/news + recent().

CLI:
    python news_store.py poll                 # fetch all sources, store new items (no LLM)
    python news_store.py poll-file <src> <f>  # ingest a saved feed file (offline test)
    python news_store.py recent [n]           # print the latest n stored items
    python news_store.py sources              # list configured sources
"""
import os
import re
import sqlite3
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

# Configured sources. kind=rss handles RSS 2.0 AND Atom (auto-detected). URLs are confirmed at
# enablement (the live poll is deferred while the forecast backfill owns the network budget); the
# EIA feed is a known-stable public RSS used to validate the pipeline.
SOURCES = [
    {"key": "eia", "kind": "rss", "label": "EIA Today in Energy",
     "url": "https://www.eia.gov/rss/todayinenergy.xml"},
    {"key": "ercot", "kind": "rss", "label": "ERCOT Notices",
     "url": "https://www.ercot.com/rss/notices"},          # confirm exact URL at enablement
]

USER_AGENT = "VoltStream-news/1.0 (+dashboard; contact mikeoc)"
_TAG = re.compile(r"^\{[^}]+\}")            # strip an XML namespace: {ns}tag -> tag


def news_db_path():
    return os.path.join(os.environ.get("ARCHIVE_DIR", "data_archive"), "news.db")


def _connect():
    os.makedirs(os.path.dirname(news_db_path()), exist_ok=True)
    conn = sqlite3.connect(news_db_path())
    conn.execute("""CREATE TABLE IF NOT EXISTS news (
        guid          TEXT PRIMARY KEY,     -- GUID/id, or the URL if the feed gives no guid
        source        TEXT NOT NULL,
        title         TEXT NOT NULL,
        url           TEXT NOT NULL,
        published_utc TEXT,                 -- NULL if the feed's date was unparseable (flagged, kept)
        published_raw TEXT,                 -- the feed's original date string, verbatim
        fetched_utc   TEXT NOT NULL,
        summary       TEXT,                 -- OPTIONAL, LLM enrichment only (never from the store path)
        tags          TEXT,                 -- OPTIONAL, LLM enrichment only
        llm_model     TEXT                  -- provenance of the enrichment (NULL = no LLM touched this row)
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_news_pub ON news(published_utc)")
    conn.commit()
    return conn


def _localname(tag):
    return _TAG.sub("", tag or "")


def _text(el):
    return (el.text or "").strip() if el is not None else ""


def _find(parent, name):
    return next((c for c in parent if _localname(c.tag) == name), None)


def _findall(root, name):
    return [c for c in root.iter() if _localname(c.tag) == name]


def _parse_date(s):
    """(iso_utc | None, raw). Tries RFC-822 (RSS pubDate) then ISO-8601 (Atom). Never fabricates."""
    s = (s or "").strip()
    if not s:
        return None, ""
    for parse in (lambda x: parsedate_to_datetime(x),
                  lambda x: datetime.fromisoformat(x.replace("Z", "+00:00"))):
        try:
            dt = parse(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat(timespec="seconds"), s
        except Exception:
            continue
    return None, s          # unparseable -> keep raw, flag published_utc NULL


def parse_feed(xml_bytes, source_label):
    """Parse RSS 2.0 or Atom bytes -> list of dicts (guid, source, title, url, published_utc,
    published_raw). Pure parsing, NO LLM, no network."""
    root = ET.fromstring(xml_bytes)
    items, out = _findall(root, "item"), []          # RSS <item>
    if not items:
        items = _findall(root, "entry")              # Atom <entry>
    for it in items:
        title = _text(_find(it, "title"))
        link_el = _find(it, "link")
        # RSS: <link>text</link>; Atom: <link href="..."/>
        url = _text(link_el) or (link_el.get("href") if link_el is not None else "")
        guid = _text(_find(it, "guid")) or _text(_find(it, "id")) or url
        date_raw = (_text(_find(it, "pubDate")) or _text(_find(it, "published"))
                    or _text(_find(it, "updated")))
        pub_iso, pub_raw = _parse_date(date_raw)
        if not (title and url):
            continue                                 # skip a malformed entry rather than store junk
        out.append({"guid": guid or url, "source": source_label, "title": title, "url": url,
                    "published_utc": pub_iso, "published_raw": pub_raw})
    return out


def store(items, conn=None):
    """Insert items append-only, deduped by guid (PRIMARY KEY + INSERT OR IGNORE). NO LLM.
    Returns (new, skipped)."""
    own = conn is None
    conn = conn or _connect()
    fetched = datetime.now(timezone.utc).isoformat(timespec="seconds")
    new = 0
    for it in items:
        cur = conn.execute(
            """INSERT OR IGNORE INTO news
               (guid, source, title, url, published_utc, published_raw, fetched_utc)
               VALUES (?,?,?,?,?,?,?)""",
            (it["guid"], it["source"], it["title"], it["url"],
             it.get("published_utc"), it.get("published_raw", ""), fetched))
        new += cur.rowcount
    conn.commit()
    if own:
        conn.close()
    return new, len(items) - new


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def poll(conn=None):
    """Fetch every configured source, store new items. Per-source errors are isolated (one dead
    feed never blocks the others). Returns a per-source summary. NO LLM."""
    own = conn is None
    conn = conn or _connect()
    out = []
    for s in SOURCES:
        try:
            items = parse_feed(_fetch(s["url"]), s["label"])
            new, skipped = store(items, conn=conn)
            out.append({"source": s["key"], "items": len(items), "new": new, "skipped": skipped})
        except Exception as e:
            out.append({"source": s["key"], "error": f"{type(e).__name__}: {e}"[:120]})
    if own:
        conn.close()
    return out


def recent(n=6, conn=None):
    """Read-only: the latest n stored items (newest published first; unknown-date last). The exact
    shape /api/news returns — headline + source + age + link + optional LLM summary/tags."""
    own = conn is None
    conn = conn or _connect()
    rows = conn.execute(
        """SELECT title, source, url, published_utc, summary, tags, llm_model
           FROM news ORDER BY (published_utc IS NULL), published_utc DESC LIMIT ?""", (n,)).fetchall()
    if own:
        conn.close()
    return [{"title": t, "source": src, "url": u, "published_utc": p,
             "summary": summ, "tags": tg, "llm_model": lm}
            for (t, src, u, p, summ, tg, lm) in rows]


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "recent"
    if cmd == "poll":
        for r in poll():
            print(r)
    elif cmd == "poll-file":                          # offline: ingest a saved feed file
        label = sys.argv[2]
        items = parse_feed(open(sys.argv[3], "rb").read(), label)
        print("parsed", len(items), "-> stored", store(items))
    elif cmd == "recent":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
        for r in recent(n):
            print(f"[{r['source']}] {str(r['published_utc'])[:16]}  {r['title'][:70]}  {r['url'][:50]}")
    elif cmd == "sources":
        for s in SOURCES:
            print(f"{s['key']:8} {s['kind']:5} {s['label']:24} {s['url']}")
    else:
        print(__doc__)
